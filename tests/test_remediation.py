"""Regression tests for MISSION 14 Codex-reported defects.

Every test is linked to the Codex ID it closes (D01..D10) plus the three
commercial scenarios A / B / C from the mission brief.
"""
from __future__ import annotations

from .conftest import login, logout
from .test_e2e_flow import _submit_call


# ---------- helpers ----------

def _create_profile(client, name="MISSION14") -> int:
    r = client.post("/blueprint/diagnose/new",
                    data={"restaurant_name": name},
                    follow_redirects=False)
    assert r.status_code == 303
    return int(r.headers["location"].split("/")[-1])


def _answer(client, pid: int, area: str, **data):
    data.setdefault("status", "manual")
    r = client.post(f"/blueprint/diagnose/{pid}/area/{area}",
                    data=data, follow_redirects=False)
    assert r.status_code == 303, (area, data, r.status_code)


def _answer_all(client, pid: int, overrides: dict | None = None):
    overrides = overrides or {}
    for area in ("pos", "payments", "delivery_platforms", "phone",
                 "online_orders", "kitchen", "couriers", "crm",
                 "analytics", "menu_compliance", "accounting", "manual_ops"):
        data = {"status": "available", "verified": "1",
                "quality": "5", "automation": "5"}
        data.update(overrides.get(area, {}))
        r = client.post(f"/blueprint/diagnose/{pid}/area/{area}",
                        data=data, follow_redirects=False)
        assert r.status_code == 303, (area, data, r.status_code)


# ---------- D01: profile edit ----------

def test_d01_edit_route_updates_profile(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client, name="Vorname Nachname")
    r = client.get(f"/blueprint/diagnose/{pid}/edit")
    assert r.status_code == 200
    assert "Reiter bearbeiten" in r.text
    r = client.post(f"/blueprint/diagnose/{pid}/edit",
                    data={"restaurant_name": "Pizzeria Neu",
                          "city": "Hamburg",
                          "cuisine": "Pizza",
                          "locations_count": 2,
                          "contact_person": "Herr Schmidt",
                          "contact_role": "Inhaber"},
                    follow_redirects=False)
    assert r.status_code == 303
    r = client.get(f"/blueprint/diagnose/{pid}")
    assert "Pizzeria Neu" in r.text
    assert "Hamburg" in r.text
    assert "Herr Schmidt" in r.text


def test_d01_edit_requires_owner(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    logout(client)
    login(client, "kitchen", "kitchen123")
    r = client.post(f"/blueprint/diagnose/{pid}/edit",
                    data={"restaurant_name": "Fremder"},
                    follow_redirects=False)
    assert r.status_code == 403


def test_d01_edit_rejects_empty_name(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    r = client.post(f"/blueprint/diagnose/{pid}/edit",
                    data={"restaurant_name": "  "}, follow_redirects=False)
    assert r.status_code == 400


# ---------- D02: zero vs blank round-trip ----------

def test_d02_zero_time_loss_survives_round_trip(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    _answer(client, pid, "phone",
            status="available", time_loss_min_per_day="0",
            quality="5", automation="5", verified="1")
    r = client.get(f"/blueprint/diagnose/{pid}/area/phone")
    # The HTML must render `time_loss_min_per_day` with value="0", not blank.
    import re
    pattern = re.compile(
        r'name="time_loss_min_per_day"[^>]*value="0"'
        r'|value="0"[^>]*name="time_loss_min_per_day"'
    )
    assert pattern.search(r.text), r.text[r.text.find("time_loss"):r.text.find("time_loss")+400]
    # Store confirms 0 is persisted, not NULL.
    from app import db
    with db.connect() as c:
        row = c.execute(
            "SELECT time_loss_min_per_day FROM diagnostic_findings "
            "WHERE profile_id=? AND area_code='phone'", (pid,)
        ).fetchone()
    assert row["time_loss_min_per_day"] == 0


def test_d02_blank_time_loss_remains_null(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    _answer(client, pid, "phone", status="partial")  # no time_loss
    from app import db
    with db.connect() as c:
        row = c.execute(
            "SELECT time_loss_min_per_day FROM diagnostic_findings "
            "WHERE profile_id=? AND area_code='phone'", (pid,)
        ).fetchone()
    assert row["time_loss_min_per_day"] is None


def test_d02_zero_quality_rejected_as_out_of_range(client):
    """quality is 1..5; a submitted 0 must fail validation, not be silently stored."""
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    r = client.post(f"/blueprint/diagnose/{pid}/area/phone",
                    data={"status": "manual", "quality": "0"},
                    follow_redirects=False)
    assert r.status_code == 400


# ---------- D05: priority persistence ----------

def test_d05_priority_only_persists_for_ticked_boxes(client):
    """Saving selection must NOT write default-medium rows for the whole catalog."""
    from app import db
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    _answer(client, pid, "phone", status="missing")
    client.post(f"/blueprint/proposal/{pid}/select",
                data={"selected": "ai_phone_reception",
                      "priority_ai_phone_reception": "high"},
                follow_redirects=False)
    with db.connect() as c:
        rows = c.execute(
            "SELECT improvement_code, selected, priority, priority_source "
            "FROM diagnostic_selections WHERE profile_id=?", (pid,)
        ).fetchall()
    codes = {r["improvement_code"] for r in rows}
    assert codes == {"ai_phone_reception"}
    assert rows[0]["priority_source"] == "manual"


def test_d05_new_suggestion_keeps_engine_priority(client):
    """After an earlier save, a *new* suggestion must not be silenced to medium."""
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    _answer(client, pid, "phone", status="manual",
            quality="2", automation="2", time_loss_min_per_day="90")
    client.post(f"/blueprint/proposal/{pid}/select",
                data={"selected": "ai_phone_reception",
                      "priority_ai_phone_reception": "high"},
                follow_redirects=False)
    # Now the operator adds a *new* finding — kitchen missing.
    _answer(client, pid, "kitchen", status="missing")
    r = client.get(f"/blueprint/proposal/{pid}")
    # Kitchen (KDS) was not persisted on the earlier save (D05 fix). It must
    # appear with its engine-recommended `Hohe Priorität`, not stale medium.
    kds_block_start = r.text.find("Küchenanzeige")
    assert kds_block_start != -1
    kds_block = r.text[kds_block_start:kds_block_start + 1000]
    assert "Hohe Priorität" in kds_block


# ---------- D08: failed-delivery recovery ----------

def test_d08_dispatch_shows_failed_queue(client):
    """A failed-delivery order appears on /dispatch for operator action."""
    from app import db
    login(client, "owner", "owner123")
    r = client.post("/call/submit", json={
        "phone": "+493099997001", "name": "Thomas Müller",
        "address": {"street": "Hauptstraße", "house_number": "1",
                    "plz": "10115", "city": "Berlin"},
        "items": [{"menu_item_id": 1, "qty": 1}],
    })
    oid = r.json()["order_id"]
    client.post(f"/confirmer/{oid}/approve")
    client.post(f"/kitchen/{oid}/ready")
    with db.connect() as c:
        cid = c.execute("SELECT id FROM users WHERE username='courier1'").fetchone()[0]
    client.post(f"/dispatch/{oid}/assign", data={"courier_id": cid})
    logout(client)
    login(client, "courier1", "courier123")
    client.post(f"/courier/{oid}/start")
    client.post(f"/courier/{oid}/failed", data={"reason": "Kunde nicht angetroffen"})
    logout(client)
    login(client, "owner", "owner123")
    r = client.get("/dispatch")
    assert r.status_code == 200
    assert "Fehlgeschlagene Zustellungen" in r.text
    assert f"#{oid}" in r.text


def test_d08_retry_reassigns_order(client):
    from app import db
    login(client, "owner", "owner123")
    r = client.post("/call/submit", json={
        "phone": "+493099997002", "name": "Thomas Müller",
        "address": {"street": "Hauptstraße", "house_number": "1",
                    "plz": "10115", "city": "Berlin"},
        "items": [{"menu_item_id": 1, "qty": 1}],
    })
    oid = r.json()["order_id"]
    client.post(f"/confirmer/{oid}/approve")
    client.post(f"/kitchen/{oid}/ready")
    with db.connect() as c:
        c1 = c.execute("SELECT id FROM users WHERE username='courier1'").fetchone()[0]
        c2 = c.execute("SELECT id FROM users WHERE username='courier2'").fetchone()[0]
    client.post(f"/dispatch/{oid}/assign", data={"courier_id": c1})
    logout(client)
    login(client, "courier1", "courier123")
    client.post(f"/courier/{oid}/start")
    client.post(f"/courier/{oid}/failed", data={"reason": "Falsche Adresse"})
    logout(client)
    login(client, "owner", "owner123")
    r = client.post(f"/dispatch/{oid}/retry",
                    data={"courier_id": c2}, follow_redirects=False)
    assert r.status_code == 303
    with db.connect() as c:
        row = c.execute(
            "SELECT status, assigned_courier_id FROM orders WHERE id=?",
            (oid,)).fetchone()
    assert row["status"] == "assigned"
    assert row["assigned_courier_id"] == c2


def test_d08_retry_rejects_wrong_status(client):
    """Retry on a non-failed order must return 409."""
    from app import db
    login(client, "owner", "owner123")
    r = client.post("/call/submit", json={
        "phone": "+493099997003", "name": "T",
        "address": {"street": "A", "house_number": "1", "plz": "10115", "city": "Berlin"},
        "items": [{"menu_item_id": 1, "qty": 1}],
    })
    oid = r.json()["order_id"]
    with db.connect() as c:
        c1 = c.execute("SELECT id FROM users WHERE username='courier1'").fetchone()[0]
    r = client.post(f"/dispatch/{oid}/retry",
                    data={"courier_id": c1}, follow_redirects=False)
    assert r.status_code == 409


def test_d08_cancel_requires_reason_and_redacts_pii(client):
    """Cancel requires a reason ≥ 3 chars; reason runs through the Blueprint redactor."""
    from app import db
    login(client, "owner", "owner123")
    r = client.post("/call/submit", json={
        "phone": "+493099997004", "name": "T",
        "address": {"street": "A", "house_number": "1", "plz": "10115", "city": "Berlin"},
        "items": [{"menu_item_id": 1, "qty": 1}],
    })
    oid = r.json()["order_id"]
    client.post(f"/confirmer/{oid}/approve")
    client.post(f"/kitchen/{oid}/ready")
    with db.connect() as c:
        c1 = c.execute("SELECT id FROM users WHERE username='courier1'").fetchone()[0]
    client.post(f"/dispatch/{oid}/assign", data={"courier_id": c1})
    logout(client); login(client, "courier1", "courier123")
    client.post(f"/courier/{oid}/start")
    client.post(f"/courier/{oid}/failed", data={"reason": "unzustellbar"})
    logout(client); login(client, "owner", "owner123")
    # Empty reason → 400
    r = client.post(f"/dispatch/{oid}/cancel_failed",
                    data={"reason": "ab"}, follow_redirects=False)
    assert r.status_code == 400
    # Reason with PII → redactor strips phone, order ends up cancelled.
    r = client.post(f"/dispatch/{oid}/cancel_failed",
                    data={"reason": "Kunde unter +49 30 1234567 nicht erreichbar"},
                    follow_redirects=False)
    assert r.status_code == 303
    with db.connect() as c:
        row = c.execute(
            "SELECT status, reject_reason FROM orders WHERE id=?", (oid,)
        ).fetchone()
    assert row["status"] == "cancelled"
    assert "+49 30 1234567" not in row["reject_reason"]
    assert "[REDACTED" in row["reject_reason"]


def test_d08_courier_cannot_cancel_from_dispatch(client):
    """Courier role must not reach /dispatch/{id}/cancel_failed."""
    login(client, "courier1", "courier123")
    r = client.post("/dispatch/1/cancel_failed",
                    data={"reason": "test"}, follow_redirects=False)
    assert r.status_code == 403


# ---------- D09: mobile markers ----------

def test_d09_blueprint_tables_marked_for_stack(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    _answer(client, pid, "phone", status="manual",
            quality="2", automation="2", time_loss_min_per_day="60")
    r = client.get("/blueprint/diagnose")
    assert 'class="bp-stack"' in r.text
    r = client.get(f"/blueprint/diagnose/{pid}")
    assert 'data-label="Status"' in r.text
    r = client.get(f"/blueprint/proposal/{pid}")
    assert 'data-label="Verbesserung"' in r.text


def test_d09_report_table_has_scroll_wrapper(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    _answer(client, pid, "phone", status="manual")
    r = client.get(f"/blueprint/proposal/{pid}/report")
    assert 'scroll-table-wrapper' in r.text


# ---------- D10: catalog decoupling from MVP ----------

def test_d10_report_uses_current_tool_not_mvp(client):
    """When current_tool is provided, the report must substitute it."""
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    _answer(client, pid, "kitchen", status="partial",
            current_tool="Vectron KDS", quality="3", automation="3",
            time_loss_min_per_day="30")
    client.post(f"/blueprint/proposal/{pid}/select",
                data={"selected": "kds",
                      "priority_kds": "medium"},
                follow_redirects=False)
    r = client.get(f"/blueprint/proposal/{pid}/report")
    assert "Vectron KDS" in r.text
    assert "/kitchen" not in r.text  # No MVP path leaks into preserved_systems.
    assert "/customers" not in r.text
    assert "/dashboard" not in r.text


def test_d10_report_fallback_text_when_tool_empty(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    _answer(client, pid, "kitchen", status="missing")
    client.post(f"/blueprint/proposal/{pid}/select",
                data={"selected": "kds", "priority_kds": "medium"},
                follow_redirects=False)
    r = client.get(f"/blueprint/proposal/{pid}/report")
    assert "Kein spezielles Werkzeug im Einsatz" in r.text


# ---------- Scenario A: manual-heavy ----------

def test_scenario_A_manual_restaurant_gets_concrete_recommendations(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client, name="Zettelwirtschaft e.K.")
    overrides = {
        "phone":      dict(status="manual", quality="1", automation="1",
                           time_loss_min_per_day="180"),
        "kitchen":    dict(status="manual", quality="2", automation="1",
                           time_loss_min_per_day="60", current_tool="Bons auf Papier"),
        "couriers":   dict(status="manual", quality="2", automation="1",
                           time_loss_min_per_day="30", current_tool="Per Zuruf"),
        "manual_ops": dict(status="manual", quality="1", automation="1",
                           time_loss_min_per_day="120"),
    }
    _answer_all(client, pid, overrides)
    r = client.get(f"/blueprint/proposal/{pid}")
    assert "KI-gestützte Telefonannahme" in r.text
    assert "Küchenanzeige" in r.text
    assert "Fahrer- und Dispatch-Management" in r.text
    assert "Automatisierung manueller Prozesse" in r.text
    # Observations are shown (D07).
    assert "geschätzter Zeitverlust 180 min/Tag" in r.text


# ---------- Scenario B: POS + Lieferando, no own couriers ----------

def test_scenario_B_platform_only_delivery_hides_dispatch_module(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client, name="Pizzeria B")
    overrides = {
        "delivery_platforms": dict(status="available", verified="1",
                                   quality="4", automation="4",
                                   current_tool="Lieferando"),
        "couriers":           dict(status="missing",
                                   notes="Nur Plattform-Lieferung, keine eigenen Fahrer"),
        "crm":                dict(status="partial", quality="3", automation="2"),
    }
    _answer_all(client, pid, overrides)
    r = client.get(f"/blueprint/proposal/{pid}")
    # delivery_mgmt must not be in the recommended block; must appear under
    # "Nicht anwendbar" with the platform-only reason.
    assert "Nicht anwendbar für diesen Betrieb" in r.text
    assert "ausschließlich über Plattformen" in r.text
    # CRM-Modul darf angeboten werden, da partial + schwache automation.
    assert "Stammkunden- und Rückgewinnungs-Workflow" in r.text


# ---------- Scenario C: fully automated restaurant ----------

def test_scenario_C_fully_automated_restaurant_shows_no_need(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client, name="Perfekt GmbH")
    _answer_all(client, pid)  # all available/verified
    r = client.get(f"/blueprint/proposal/{pid}")
    assert "Aktuell kein zusätzlicher Implementierungsbedarf festgestellt" in r.text
    assert "Empfohlene Verbesserungen" not in r.text
    r = client.get(f"/blueprint/proposal/{pid}/report")
    assert "Aktuell kein zusätzlicher Implementierungsbedarf festgestellt" in r.text
    # No paid-audit CTA in no-need report (D06).
    assert "Zugänge erforderlich" not in r.text  # old next-steps template
    assert "weder ein kostenpflichtiges Audit" in r.text
    assert "verbindliches Angebot" in r.text


# ---------- Scenario C': critical area unknown ⇒ outcome insufficient ----------

def test_scenario_C_core_unknown_blocks_no_need(client):
    """Even if the rest is `available`, a critical-area `unknown` must not pretend `no_need`."""
    login(client, "owner", "owner123")
    pid = _create_profile(client, name="Unklar GmbH")
    overrides = {"payments": dict(status="unknown")}
    _answer_all(client, pid, overrides)
    r = client.get(f"/blueprint/proposal/{pid}")
    assert "Aktuell kein zusätzlicher Implementierungsbedarf festgestellt" not in r.text
    r = client.get(f"/blueprint/proposal/{pid}/report")
    assert "Diagnose unvollständig" in r.text


# ---------- Scenario: unknown stays unknown, not a gap ----------

def test_unknown_phone_does_not_fire_phone_module(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    _answer(client, pid, "phone", status="unknown")
    r = client.get(f"/blueprint/proposal/{pid}")
    assert "KI-gestützte Telefonannahme" not in r.text
    assert "Zunächst klären" in r.text


# ---------- Catalog text sanity (D10 wording) ----------

def test_catalog_text_free_of_mvp_paths():
    """The catalog itself must not reference /kitchen, /customers, /dashboard etc."""
    from app.blueprint import catalog
    forbidden = ("/kitchen", "/customers", "/dashboard", "/call", "/confirmer",
                 "Erweiterung der MVP", "aus dem MVP ist Ausgangspunkt")
    for improvement in catalog.IMPROVEMENTS:
        blob = (
            improvement.title + improvement.problem + improvement.proposal
            + " ".join(improvement.preserved_systems)
            + " ".join(t.name + t.note for t in improvement.possible_tools)
            + " ".join(i.name + i.purpose for i in improvement.required_integrations)
        )
        for bad in forbidden:
            assert bad not in blob, (improvement.code, bad)


def test_catalog_text_free_of_roi_promises():
    """No measurement/ROI promise in catalog text (plain lexical check)."""
    from app.blueprint import catalog
    bad_terms = ("ROI nach", "spart X", "Doppelerfassung entfällt",
                 "garantiert", "sofort")
    for improvement in catalog.IMPROVEMENTS:
        blob = improvement.proposal + improvement.expected_effect
        for bad in bad_terms:
            assert bad not in blob, (improvement.code, bad)
