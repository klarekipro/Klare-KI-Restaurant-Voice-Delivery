"""End-to-end flow: new caller + repeat caller through the full lifecycle."""
from __future__ import annotations

from .conftest import login, logout


def _sample_items(client):
    # Pull menu via DB directly for stable ids; TestClient reuses the same DB.
    from app import db
    conn = db.connect()
    try:
        rows = conn.execute("SELECT id, name FROM menu_items ORDER BY id LIMIT 3").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _submit_call(client, phone, name, items):
    payload = {
        "phone": phone,
        "name": name,
        "address": {
            "street": "Teststraße",
            "house_number": "7",
            "plz": "10115",
            "city": "Berlin",
            "notes": "",
        },
        "items": [{"menu_item_id": i["id"], "qty": 1} for i in items],
    }
    r = client.post("/call/submit", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_full_lifecycle_new_customer(client):
    menu = _sample_items(client)

    # Confirmer starts a call for a brand-new customer and submits order.
    login(client, "confirmer", "confirmer123")
    res = _submit_call(client, phone="+493099990001", name="Max Neukunde", items=menu[:2])
    order_id = res["order_id"]
    assert res["crm_match_status"] == "unmatched"
    logout(client)

    # Confirmer approves the order.
    login(client, "confirmer", "confirmer123")
    r = client.post(f"/confirmer/{order_id}/approve", follow_redirects=False)
    assert r.status_code == 303
    # Edit item should NOT be possible after confirm.
    r_edit = client.post(f"/confirmer/{order_id}/add_item",
                         data={"menu_item_id": menu[2]["id"], "qty": 1},
                         follow_redirects=False)
    assert r_edit.status_code == 409
    logout(client)

    # Kitchen marks ready.
    login(client, "kitchen", "kitchen123")
    r = client.post(f"/kitchen/{order_id}/ready", follow_redirects=False)
    assert r.status_code == 303
    logout(client)

    # Confirmer assigns courier1.
    login(client, "confirmer", "confirmer123")
    # Find courier1 id
    from app import db
    conn = db.connect()
    try:
        courier = conn.execute(
            "SELECT id FROM users WHERE username='courier1'"
        ).fetchone()
    finally:
        conn.close()
    r = client.post(
        f"/dispatch/{order_id}/assign",
        data={"courier_id": courier["id"]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    logout(client)

    # Courier starts and delivers.
    login(client, "courier1", "courier123")
    r = client.get("/courier")
    assert r.status_code == 200 and f"#{order_id}" in r.text
    r = client.post(f"/courier/{order_id}/start", follow_redirects=False)
    assert r.status_code == 303
    # Reveal phone — must emit an audit event.
    r = client.post(f"/courier/{order_id}/reveal_phone",
                    data={"reason": "customer_not_at_door"})
    assert r.status_code == 200 and r.json()["phone"].startswith("+")
    r = client.post(f"/courier/{order_id}/delivered", follow_redirects=False)
    assert r.status_code == 303
    logout(client)

    # Owner dashboard sees delivery for this courier.
    login(client, "owner", "owner123")
    r = client.get("/dashboard?range=today")
    assert r.status_code == 200
    assert "Zugestellt pro Fahrer" in r.text
    assert "Carlo Courier" in r.text
    # order appears in the per-courier breakdown (count or sum)
    logout(client)

    # Verify order state is closed and audit log has reveal_phone.
    from app import db
    conn = db.connect()
    try:
        o = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
        assert o["status"] == "closed"
        audit = conn.execute(
            "SELECT * FROM access_log WHERE action = 'reveal_phone' AND object_id = ?",
            (str(order_id),),
        ).fetchone()
        assert audit is not None
    finally:
        conn.close()


def test_repeat_customer_crm_match(client):
    menu = _sample_items(client)
    login(client, "confirmer", "confirmer123")

    # Seeded Thomas Müller is a trusted repeat customer.
    r = client.post("/call/lookup", data={"phone": "+49 30 1234567"})
    assert r.status_code == 200
    data = r.json()
    assert data["matched"] is True
    assert data["customer"]["name"].startswith("Thomas")
    assert data["customer"]["trusted"] is True

    res = _submit_call(client, phone="+49 30 1234567", name="Thomas Müller", items=menu[:1])
    assert res["crm_match_status"] == "matched"
    assert res["total_cents"] > 0
    logout(client)


def test_role_based_access(client):
    # Courier cannot access confirmer queue.
    login(client, "courier1", "courier123")
    r = client.get("/confirmer", follow_redirects=False)
    assert r.status_code in (401, 403)
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code in (401, 403)
    logout(client)

    # Kitchen cannot see customers list.
    login(client, "kitchen", "kitchen123")
    r = client.get("/customers", follow_redirects=False)
    assert r.status_code in (401, 403)
    logout(client)

    # Anonymous call simulator access blocked.
    r = client.get("/call", follow_redirects=False)
    assert r.status_code in (401, 403)


def test_reject_flow_blocks_kitchen(client):
    menu = _sample_items(client)
    login(client, "confirmer", "confirmer123")
    res = _submit_call(client, phone="+493099990002", name="Rika Reject", items=menu[:1])
    oid = res["order_id"]
    r = client.post(f"/confirmer/{oid}/reject",
                    data={"reason": "address outside delivery zone"},
                    follow_redirects=False)
    assert r.status_code == 303
    logout(client)

    login(client, "kitchen", "kitchen123")
    r = client.post(f"/kitchen/{oid}/ready", follow_redirects=False)
    assert r.status_code == 409
    logout(client)

    from app import db
    conn = db.connect()
    try:
        row = conn.execute("SELECT status FROM orders WHERE id = ?", (oid,)).fetchone()
        assert row["status"] == "rejected"
    finally:
        conn.close()


def test_persistence_across_restart(tmp_db):
    """Shut the app down and start a new one against the same DB file."""
    from fastapi.testclient import TestClient
    from app.main import create_app

    app1 = create_app()
    with TestClient(app1) as c:
        login(c, "confirmer", "confirmer123")
        menu = _sample_items(c)
        res = _submit_call(c, phone="+493099990003", name="Perry Persistence",
                           items=menu[:1])
        oid = res["order_id"]

    app2 = create_app()
    with TestClient(app2) as c:
        login(c, "owner", "owner123")
        r = c.get(f"/confirmer/{oid}")
        assert r.status_code == 200
        assert "Perry Persistence" in r.text
