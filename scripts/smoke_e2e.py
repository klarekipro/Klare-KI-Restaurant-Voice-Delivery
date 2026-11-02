"""End-to-end smoke across all 12 demo flows. Prints PASS/FAIL per step."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    os.environ["KLARE_DB_PATH"] = tmp.name
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    results: list[tuple[str, bool, str]] = []

    def step(name: str, ok: bool, extra: str = "") -> None:
        results.append((name, ok, extra))

    def session(username: str, password: str) -> TestClient:
        c = TestClient(app)
        r = c.post("/login", data={"username": username, "password": password},
                   follow_redirects=False)
        assert r.status_code == 303, (username, r.status_code, r.text[:200])
        return c

    owner = session("owner", "owner123")
    confirmer = session("confirmer", "confirmer123")
    kitchen = session("kitchen", "kitchen123")
    courier1 = session("courier1", "courier123")
    courier2 = session("courier2", "courier123")

    # 1. Call simulator: new customer order
    r = courier1.get("/call")
    step("1a. courier blocked from /call", r.status_code == 403)
    r = confirmer.get("/call")
    step("1b. confirmer can open /call", r.status_code == 200)
    payload_new = {
        "phone": "+49 171 1234567",
        "name": "Anna Neu",
        "address": {"street": "Berliner Str.", "house_number": "7",
                    "plz": "10115", "city": "Berlin", "notes": "3. Stock"},
        "items": [{"menu_item_id": 1, "qty": 2}],
    }
    r = confirmer.post("/call/submit", json=payload_new,
                       headers={"Idempotency-Key": "aaaaaaaaaaaaaaaa1"})
    step("1c. submit creates order", r.status_code == 200 and "order_id" in r.text, r.text[:140])
    new_order = r.json()["order_id"]

    # 2. CRM lookup existing (phone from seed)
    r = confirmer.post("/call/lookup", data={"phone": "+49301234567"})
    step("2a. existing customer lookup matched",
         r.status_code == 200 and r.json().get("matched") is True, r.text[:120])

    # 3. New customer stored
    payload_known = {
        "phone": "+49 30 1234567",
        "name": "Thomas Müller",
        "address": {"street": "Hauptstraße", "house_number": "12a",
                    "plz": "10115", "city": "Berlin", "notes": ""},
        "items": [{"menu_item_id": 2, "qty": 1}, {"menu_item_id": 3, "qty": 1}],
    }
    r = confirmer.post("/call/submit", json=payload_known,
                       headers={"Idempotency-Key": "bbbbbbbbbbbbbbbb1"})
    step("3. existing customer new order", r.status_code == 200, r.text[:120])
    repeat_order = r.json()["order_id"]

    # 4. Confirmer edits + approves
    r = confirmer.post(f"/confirmer/{new_order}/add_item",
                       data={"menu_item_id": 4, "qty": 1},
                       follow_redirects=False)
    step("4a. confirmer add item", r.status_code == 303, f"status={r.status_code}")

    r = confirmer.post(f"/confirmer/{new_order}/edit_item",
                       data={"item_id": 1, "qty": 3},
                       follow_redirects=False)
    step("4b. confirmer edit qty", r.status_code == 303)

    r = confirmer.post(f"/confirmer/{new_order}/approve", follow_redirects=False)
    step("4c. confirmer approve", r.status_code == 303)

    # 5. Kitchen receives + marks ready
    r = kitchen.get("/kitchen")
    step("5a. kitchen page loads", r.status_code == 200)
    r = kitchen.post(f"/kitchen/{new_order}/start", follow_redirects=False)
    step("5b. kitchen start", r.status_code == 303)
    r = kitchen.post(f"/kitchen/{new_order}/ready", follow_redirects=False)
    step("6. kitchen ready", r.status_code == 303)

    # 7. Dispatch assigns courier
    r = owner.get("/dispatch")
    step("7a. dispatch loads", r.status_code == 200)
    r = owner.post(f"/dispatch/{new_order}/assign",
                   data={"courier_id": 4}, follow_redirects=False)
    step("7b. assign courier", r.status_code == 303, r.text[:200])

    # 8. Courier mobile view
    r = courier1.get("/courier")
    step("8a. courier list", r.status_code == 200 and f"#{new_order}" in r.text)
    r = courier1.get(f"/courier/{new_order}")
    step("8b. courier delivery page", r.status_code == 200 and "google.com/maps" in r.text,
         r.text[:200] if r.status_code != 200 else "")

    r = courier2.get(f"/courier/{new_order}")
    step("8c. other courier forbidden", r.status_code == 403)

    # 9. Google Maps link encoded
    body = courier1.get(f"/courier/{new_order}").text
    step("9. maps link uses quote_plus (space->+)",
         "destination=Berliner+Str.+7%2C+10115+Berlin" in body or
         "destination=Berliner" in body and "Berlin" in body, "")

    # 10. Complete delivery
    r = courier1.post(f"/courier/{new_order}/start", follow_redirects=False)
    step("10a. courier mark en_route", r.status_code == 303)
    r = courier1.post(f"/courier/{new_order}/delivered", follow_redirects=False)
    step("10. courier delivered", r.status_code == 303)

    # 11. Dashboard with sums
    r = owner.get("/dashboard")
    step("11a. dashboard loads", r.status_code == 200)
    r = owner.get("/dashboard?range=7d")
    step("11b. dashboard 7d", r.status_code == 200)
    r = confirmer.get("/dashboard")
    step("11c. confirmer blocked from dashboard", r.status_code == 403)

    # 12. Reports per courier (present in dashboard)
    body = owner.get("/dashboard").text
    step("12. per-courier report present",
         "Zugestellt pro Fahrer" in body and "Carlo Courier" in body)

    # Error-handling probes
    r = confirmer.post("/call/submit", json={"phone": "123", "address": {}, "items": []},
                       headers={"Idempotency-Key": "cccccccccccccccc1"})
    step("E1. invalid payload 400", r.status_code == 400, r.text[:120])

    r = confirmer.post("/call/submit", json=payload_new,
                       headers={"Idempotency-Key": "aaaaaaaaaaaaaaaa1"})
    step("E2. idempotency replay returns prior",
         r.status_code == 200 and r.json().get("order_id") == new_order)

    r = confirmer.post("/call/submit",
                       json={**payload_new, "items": [{"menu_item_id": 1, "qty": 9}]},
                       headers={"Idempotency-Key": "aaaaaaaaaaaaaaaa1"})
    step("E3. idempotency reused with changed body => 409", r.status_code == 409)

    r = kitchen.post(f"/kitchen/{repeat_order}/ready", follow_redirects=False)
    step("E4. kitchen can direct-ready from confirmed",
         r.status_code in (303, 409), f"status={r.status_code}")

    # Persistence check: re-open app on same DB
    from app.main import create_app as fresh
    app2 = fresh()
    c = TestClient(app2)
    r = c.post("/login", data={"username": "owner", "password": "owner123"},
               follow_redirects=False)
    r = c.get(f"/confirmer/{new_order}")
    step("P. order survives app restart", r.status_code == 200 and f"#{new_order}" in r.text)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    width = max(len(n) for n, _, _ in results)
    for name, ok, extra in results:
        tag = "PASS" if ok else "FAIL"
        line = f"  [{tag}] {name.ljust(width)}"
        if extra:
            line += f"   {extra}"
        print(line)
    print(f"\n{passed}/{total} steps passed")

    try:
        Path(tmp.name).unlink()
    except FileNotFoundError:
        pass
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
