"""Tests for the Klare KI Restaurant Blueprint (MISSION 12).

Coverage targets:
- RBAC on /blueprint/diagnose and /blueprint/proposal (only owner).
- Public-ish DEMO + overview accessible to all logged-in users.
- Diagnostic profile CRUD + area upsert idempotence.
- Gap-logic correctness (unknown is not a gap, available is skipped).
- Report rendering with mandatory confidentiality footer and catalog version.
- Free-text redaction for phone/email/IBAN.
- access_log entries written for key mutations.
"""
from __future__ import annotations

from .conftest import login, logout


# ---------- RBAC ----------

def test_overview_requires_login(client):
    r = client.get("/blueprint", follow_redirects=False)
    # Session middleware is active but no user is signed in; the global
    # 401-handler converts it to a 303 to /login.
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_overview_visible_for_any_logged_in_role(client):
    login(client, "kitchen", "kitchen123")
    r = client.get("/blueprint")
    assert r.status_code == 200
    assert "Blueprint" in r.text


def test_demo_visible_for_courier(client):
    login(client, "courier1", "courier123")
    r = client.get("/blueprint/demo")
    assert r.status_code == 200
    assert "Pizzeria" in r.text


def test_diagnose_list_denied_for_confirmer(client):
    login(client, "confirmer", "confirmer123")
    r = client.get("/blueprint/diagnose", follow_redirects=False)
    assert r.status_code == 403


def test_diagnose_new_denied_for_kitchen(client):
    login(client, "kitchen", "kitchen123")
    r = client.post("/blueprint/diagnose/new",
                    data={"restaurant_name": "Hack"},
                    follow_redirects=False)
    assert r.status_code == 403


# ---------- Profile CRUD + area upsert ----------

def test_profile_create_and_show(client):
    login(client, "owner", "owner123")
    r = client.post("/blueprint/diagnose/new",
                    data={"restaurant_name": "Pizzeria Testovič",
                          "city": "Berlin", "cuisine": "Pizza",
                          "locations_count": 2,
                          "contact_person": "Herr Rossi",
                          "contact_role": "Inhaber"},
                    follow_redirects=False)
    assert r.status_code == 303
    pid = int(r.headers["location"].split("/")[-1])
    r = client.get(f"/blueprint/diagnose/{pid}")
    assert r.status_code == 200
    assert "Pizzeria Testovič" in r.text
    assert "Herr Rossi" in r.text


def test_profile_name_required(client):
    login(client, "owner", "owner123")
    r = client.post("/blueprint/diagnose/new",
                    data={"restaurant_name": "  "})
    assert r.status_code == 400


def _create_profile(client, name="Test-R") -> int:
    r = client.post("/blueprint/diagnose/new",
                    data={"restaurant_name": name},
                    follow_redirects=False)
    assert r.status_code == 303
    return int(r.headers["location"].split("/")[-1])


def test_area_upsert_is_idempotent(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    for status in ("manual", "manual", "missing"):
        r = client.post(f"/blueprint/diagnose/{pid}/area/phone",
                        data={"status": status, "notes": "ok"},
                        follow_redirects=False)
        assert r.status_code == 303
    from app import db
    with db.connect() as c:
        rows = c.execute("SELECT status FROM diagnostic_findings "
                         "WHERE profile_id=? AND area_code='phone'", (pid,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "missing"


def test_area_rejects_unknown_code(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    r = client.post(f"/blueprint/diagnose/{pid}/area/nonsense",
                    data={"status": "missing"})
    assert r.status_code == 404


def test_area_rejects_bad_status(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    r = client.post(f"/blueprint/diagnose/{pid}/area/phone",
                    data={"status": "later"})
    assert r.status_code == 400


def test_profile_status_transition_and_delete(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client, name="Löschbar")
    r = client.post(f"/blueprint/diagnose/{pid}/status",
                    data={"status": "shared"}, follow_redirects=True)
    assert "Freigegeben" in r.text
    r = client.post(f"/blueprint/diagnose/{pid}/delete", follow_redirects=False)
    assert r.status_code == 303
    r = client.get(f"/blueprint/diagnose/{pid}", follow_redirects=False)
    assert r.status_code == 404


def test_profile_delete_cascades_findings_and_selections(client):
    """DELETE must remove child rows via FK cascade (verifies PRAGMA)."""
    from app import db
    login(client, "owner", "owner123")
    pid = _create_profile(client, name="Kaskade")
    client.post(f"/blueprint/diagnose/{pid}/area/phone",
                data={"status": "missing"}, follow_redirects=False)
    client.post(f"/blueprint/diagnose/{pid}/area/kitchen",
                data={"status": "manual"}, follow_redirects=False)
    client.post(f"/blueprint/proposal/{pid}/select",
                data={"selected": "ai_phone_reception",
                      "priority_ai_phone_reception": "high"},
                follow_redirects=False)
    with db.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM diagnostic_findings "
                         "WHERE profile_id=?", (pid,)).fetchone()[0] == 2
        assert c.execute("SELECT COUNT(*) FROM diagnostic_selections "
                         "WHERE profile_id=?", (pid,)).fetchone()[0] >= 1

    client.post(f"/blueprint/diagnose/{pid}/delete", follow_redirects=False)

    with db.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM diagnostic_profiles "
                         "WHERE id=?", (pid,)).fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM diagnostic_findings "
                         "WHERE profile_id=?", (pid,)).fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM diagnostic_selections "
                         "WHERE profile_id=?", (pid,)).fetchone()[0] == 0


# ---------- Gap logic ----------

def test_unknown_is_not_a_gap(client):
    """A single 'unknown' answer must not produce any improvement suggestion."""
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    r = client.post(f"/blueprint/diagnose/{pid}/area/phone",
                    data={"status": "unknown"},
                    follow_redirects=False)
    assert r.status_code == 303
    r = client.get(f"/blueprint/proposal/{pid}")
    assert r.status_code == 200
    assert "Zunächst klären" in r.text
    assert "Empfohlene Verbesserungen" in r.text
    # Strict: with only an `unknown` answer, no suggestion row may appear.
    assert "aktuell keine Verbesserungen" in r.text
    assert "KI-gestützte Telefonannahme" not in r.text


def test_available_is_not_proposed(client):
    """All 12 'available'+verified ⇒ no-need outcome, no suggestions, no audit CTA."""
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    for area in ("phone", "kitchen", "couriers", "crm", "analytics",
                 "manual_ops", "accounting", "menu_compliance",
                 "pos", "payments", "delivery_platforms", "online_orders"):
        client.post(f"/blueprint/diagnose/{pid}/area/{area}",
                    data={"status": "available", "verified": "1",
                          "quality": "5", "automation": "5"},
                    follow_redirects=False)
    r = client.get(f"/blueprint/proposal/{pid}")
    assert "Aktuell kein zusätzlicher Implementierungsbedarf festgestellt" in r.text


def test_missing_phone_proposes_ai_phone_reception(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    client.post(f"/blueprint/diagnose/{pid}/area/phone",
                data={"status": "missing"},
                follow_redirects=False)
    r = client.get(f"/blueprint/proposal/{pid}")
    assert r.status_code == 200
    assert "KI-gestützte Telefonannahme" in r.text


# ---------- Selection + report ----------

def test_proposal_selection_and_report(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client, name="Druckbar")
    client.post(f"/blueprint/diagnose/{pid}/area/phone",
                data={"status": "missing"},
                follow_redirects=False)
    r = client.post(f"/blueprint/proposal/{pid}/select",
                    data={"selected": "ai_phone_reception",
                          "priority_ai_phone_reception": "high"},
                    follow_redirects=False)
    assert r.status_code == 303
    r = client.get(f"/blueprint/proposal/{pid}/report")
    assert r.status_code == 200
    text = r.text
    assert "Diskussionsgrundlage" in text
    assert "Vertraulich" in text
    assert "Richtwert Klare KI" in text and "kein Angebot" in text
    assert "KI-gestützte Telefonannahme" in text
    assert "Katalog-Version" in text


def test_report_contains_catalog_version(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    r = client.get(f"/blueprint/proposal/{pid}/report")
    # Even without findings/selections the report renders with the version.
    from app.blueprint.catalog import CATALOG_VERSION
    assert CATALOG_VERSION in r.text


# ---------- Redaction ----------

def test_notes_redaction_hits_phone_email(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    r = client.post(f"/blueprint/diagnose/{pid}/area/phone",
                    data={"status": "manual",
                          "notes": "Rückfrage an +49 30 1234567 oder test@example.com"},
                    follow_redirects=False)
    assert r.status_code == 303
    r = client.get(f"/blueprint/diagnose/{pid}/area/phone")
    assert "[REDACTED:phone]" in r.text
    assert "[REDACTED:email]" in r.text
    from app import db
    with db.connect() as c:
        row = c.execute(
            "SELECT reason FROM access_log WHERE action='blueprint.notes.redacted' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    assert "phone" in row["reason"] and "email" in row["reason"]


def test_notes_short_fragment_is_not_redacted(client):
    """A short digit sequence like a quantity must not be falsely redacted."""
    login(client, "owner", "owner123")
    pid = _create_profile(client)
    r = client.post(f"/blueprint/diagnose/{pid}/area/kitchen",
                    data={"status": "manual",
                          "notes": "3 Pizzaöfen, 2 Mitarbeiter in Stoßzeit"},
                    follow_redirects=False)
    assert r.status_code == 303
    r = client.get(f"/blueprint/diagnose/{pid}/area/kitchen")
    assert "[REDACTED" not in r.text
    assert "3 Pizzaöfen" in r.text


# ---------- Audit log ----------

def test_audit_log_profile_create_delete(client):
    login(client, "owner", "owner123")
    pid = _create_profile(client, name="Audit-R")
    client.post(f"/blueprint/diagnose/{pid}/delete")
    from app import db
    with db.connect() as c:
        actions = [r["action"] for r in c.execute(
            "SELECT action FROM access_log WHERE object_type='blueprint_profile' "
            "ORDER BY id ASC"
        ).fetchall()]
    assert "blueprint.profile.create" in actions
    assert "blueprint.profile.delete" in actions


# ---------- Pure-function gap unit tests ----------

def test_gap_unit_unknown_only():
    from app.blueprint.gap import analyze
    result = analyze([{"area_code": "phone", "status": "unknown", "verified": 0}])
    assert result.to_clarify == ("phone",)
    assert result.suggestions == ()


def test_gap_unit_missing_phone_proposes_high():
    from app.blueprint.gap import analyze
    result = analyze([{"area_code": "phone", "status": "missing", "verified": 0,
                        "quality": None, "automation": None,
                        "time_loss_min_per_day": None, "notes": "",
                        "current_tool": ""}])
    titles = [s.improvement.title for s in result.suggestions]
    assert "KI-gestützte Telefonannahme" in titles
    s = result.suggestions[0]
    assert s.verdict == "required"
    assert s.confidence == "high"


def test_gap_unit_available_not_proposed():
    from app.blueprint.gap import analyze
    result = analyze([{"area_code": "phone", "status": "available", "verified": 1}])
    assert result.suggestions == ()
    assert result.verify_recommended == ()


def test_gap_unit_available_unverified_recommends_verification():
    from app.blueprint.gap import analyze
    result = analyze([{"area_code": "phone", "status": "available", "verified": 0}])
    assert "phone" in result.verify_recommended
