"""MISSION 16 regression tests.

Each test is tied to a Codex MISSION 15 blocker (R1..R7) or to one of the
eight mandatory scenarios (A..H) from the mission brief. The suite covers
the exact adversarial cases Codex ran and extends them with scenarios the
Codex report called out as unverified (D, E, F, G, H).
"""
from __future__ import annotations

import ast
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import login, logout

ROOT = Path(__file__).resolve().parents[1]


# ---------- shared helpers ----------

def _create(client, name="MISSION16") -> int:
    r = client.post("/blueprint/diagnose/new",
                    data={"restaurant_name": name},
                    follow_redirects=False)
    assert r.status_code == 303
    return int(r.headers["location"].rsplit("/", 1)[1])


def _area(client, pid: int, code: str, **data):
    payload = {"status": "available", "quality": "5", "automation": "5",
               "time_loss_min_per_day": "0",
               "current_tool": f"Existing {code}", "verified": "1"}
    for k, v in data.items():
        payload[k] = str(v) if isinstance(v, int) else v
    r = client.post(f"/blueprint/diagnose/{pid}/area/{code}",
                    data=payload, follow_redirects=False)
    assert r.status_code == 303, (code, payload, r.status_code, r.text[:200])


def _healthy_rows(**overrides):
    """Build the full 12-area healthy baseline for `gap.analyze()` directly."""
    from app.blueprint.catalog import DIAGNOSE_AREAS
    rows = {}
    for a in DIAGNOSE_AREAS:
        rows[a.code] = {
            "area_code": a.code, "status": "available",
            "quality": 5, "automation": 5, "time_loss_min_per_day": 0,
            "verified": 1, "current_tool": f"Existing {a.code}", "notes": "",
        }
    for k, v in overrides.items():
        rows[k] = {**rows[k], **v, "area_code": k}
    return rows


def _analyze(rows):
    from app.blueprint.gap import analyze
    return analyze(rows.values())


# =========================================================
# R1 — healthy manual process is NOT required
# =========================================================

@pytest.mark.parametrize("code", ["phone", "kitchen", "crm", "manual_ops"])
def test_R1_healthy_manual_is_not_required(code):
    """MISSION 15 R1: automation score alone is not proof of pain.

    `status=manual, quality=5, automation=1, time=0, notes="works well"` must
    NOT produce a `required` verdict for the responsible area.
    """
    rows = _healthy_rows(**{code: {
        "status": "manual", "quality": 5, "automation": 1,
        "time_loss_min_per_day": 0,
        "notes": "Works well; no missed orders or improvement need",
    }})
    result = _analyze(rows)
    offending = [
        s for s in result.suggestions
        if s.verdict == "required" and any(a == code for a, _ in s.evidence)
    ]
    assert not offending, (code, [(s.improvement.code, s.verdict, s.evidence) for s in result.suggestions])


# =========================================================
# R2 — problem outside catalog must not be no_need
# =========================================================

def test_R2_explicit_core_payment_gap_is_not_no_need():
    """MISSION 15 R2: a missing payments area must NOT silently become
    `no_need`, even though the catalog has no payment module."""
    result = _analyze(_healthy_rows(payments={
        "status": "missing", "quality": 1, "time_loss_min_per_day": 120,
        "notes": "Payment process and required controls absent",
    }))
    assert result.outcome != "no_need"
    assert "payments" in result.problems_without_match
    # And there must be no fake payments catalog entry.
    codes = {s.improvement.code for s in result.suggestions}
    assert all("payment" not in c for c in codes)


def test_R2_available_analytics_with_pain_is_not_no_need():
    """MISSION 15 R2: a working-but-painful analytics area ⇒ not no_need."""
    result = _analyze(_healthy_rows(analytics={
        "quality": 1, "time_loss_min_per_day": 180,
        "notes": "Existing reporting produces wrong figures",
    }))
    assert result.outcome != "no_need"


# =========================================================
# R3 — review-mgmt respects negation
# =========================================================

def test_R3_negated_review_note_does_not_create_problem():
    """MISSION 15 R3: 'Keine Probleme mit Google-Bewertungen' must NOT
    trigger a review-management suggestion."""
    result = _analyze(_healthy_rows(crm={
        "notes": "Keine Probleme mit Google-Bewertungen; alle Rezensionen "
                 "werden beantwortet.",
    }))
    codes = {s.improvement.code for s in result.suggestions}
    assert "review_mgmt" not in codes


def test_R3_affirmative_review_problem_still_triggers():
    """A clearly affirmed problem is still picked up."""
    result = _analyze(_healthy_rows(crm={
        "notes": "Google-Bewertungen bleiben unbeantwortet, "
                 "wir haben ein Problem mit Rezensionen.",
    }))
    codes = {s.improvement.code for s in result.suggestions}
    assert "review_mgmt" in codes


# =========================================================
# R4 — evidence preserves actual status
# =========================================================

def test_R4_phone_evidence_does_not_invent_partial_status():
    """MISSION 15 R4: `available` input must not be reported as
    'Status: teilweise' in evidence."""
    result = _analyze(_healthy_rows(phone={
        "quality": 1, "time_loss_min_per_day": 120,
    }))
    s = next(s for s in result.suggestions
             if s.improvement.code == "ai_phone_reception")
    assert "Status: teilweise" not in str(s.evidence)
    # Positive: the real status is kept.
    assert any("vorhanden" in obs.lower() for _, obs in s.evidence)


# =========================================================
# R5 — confidence calibration
# =========================================================

def test_R5_status_only_unverified_missing_is_not_high_confidence():
    """MISSION 15 R5: a bare `status=missing` without verification, quality,
    time, or notes must not report confidence='high'."""
    result = _analyze(_healthy_rows(phone={
        "status": "missing", "quality": None, "automation": None,
        "time_loss_min_per_day": None, "verified": 0, "current_tool": "",
        "notes": "",
    }))
    s = next(s for s in result.suggestions
             if s.improvement.code == "ai_phone_reception")
    assert s.confidence != "high"


def test_R5_verified_missing_keeps_high_confidence():
    result = _analyze(_healthy_rows(phone={
        "status": "missing", "verified": 1,
    }))
    s = next(s for s in result.suggestions
             if s.improvement.code == "ai_phone_reception")
    assert s.confidence == "high"


# =========================================================
# R6 — legacy priority rows do not override new high engine priority
# =========================================================

def test_R6_legacy_unselected_overrides_do_not_survive(tmp_path, monkeypatch):
    """MISSION 15 R6: upgrade an actual MISSION 12 schema database (which
    stored `selected=0, priority='medium'` for every catalog entry) and
    verify the engine's `high` recommendation on a new finding wins.
    """
    from app import db, auth
    from app.main import create_app
    from fastapi.testclient import TestClient
    path = tmp_path / "legacy.sqlite"
    monkeypatch.setenv("KLARE_DB_PATH", str(path))

    # Rehydrate the exact MISSION 12 schema from git history.
    source = subprocess.check_output(
        ["git", "show", "53d04a5:app/db.py"], cwd=ROOT, text=True
    )
    tree = ast.parse(source)
    schema = next(
        ast.literal_eval(n.value) for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "SCHEMA" for t in n.targets)
    )
    with sqlite3.connect(path) as d:
        d.executescript(schema)
        d.execute(
            "INSERT INTO users(id,username,password_hash,display_name,role) "
            "VALUES(1,'owner',?,'Synthetic Owner','owner')",
            (auth.hash_password("owner123"),),
        )
        d.execute(
            "INSERT INTO diagnostic_profiles(id,restaurant_name,catalog_version,created_by) "
            "VALUES(1,'Legacy Mission 12','2026-11-02',1)"
        )
        # Legacy MISSION 12 wrote these for every catalog item.
        for code in ("kds", "ai_phone_reception", "crm_automation"):
            d.execute(
                "INSERT INTO diagnostic_selections "
                "(profile_id,improvement_code,selected,priority) "
                "VALUES(1,?,0,'medium')",
                (code,),
            )

    with TestClient(create_app()) as c:
        login(c, "owner", "owner123")
        _area(c, 1, "kitchen", status="missing")
        html = c.get("/blueprint/proposal/1").text
        block = re.search(
            r'<select name="priority_kds">(.*?)</select>', html, re.S
        ).group(1)
        assert re.search(r'value="high"\s+selected', block), \
            "Legacy medium override still masking new engine high"


# =========================================================
# R7 — failed delivery reason + timestamp visible
# =========================================================

def test_R7_failed_delivery_reason_and_timestamp_visible(client):
    """MISSION 15 R7: dispatch SQL must look up the actual event name
    `status.failed_delivery` and surface reason + timestamp."""
    from app import db
    login(client, "owner", "owner123")
    r = client.post("/call/submit", json={
        "phone": "+493099990016", "name": "Synthetic R7",
        "address": {"street": "Testweg", "house_number": "1",
                    "plz": "10115", "city": "Berlin"},
        "items": [{"menu_item_id": 1, "qty": 1}],
    })
    oid = r.json()["order_id"]
    client.post(f"/confirmer/{oid}/approve")
    client.post(f"/kitchen/{oid}/ready")
    with db.connect() as d:
        cid = d.execute(
            "SELECT id FROM users WHERE username='courier1'"
        ).fetchone()[0]
    client.post(f"/dispatch/{oid}/assign", data={"courier_id": cid})
    logout(client)
    login(client, "courier1", "courier123")
    client.post(f"/courier/{oid}/start")
    client.post(f"/courier/{oid}/failed",
                data={"reason": "SYNTHETIC_FAILURE_REASON_16"})
    logout(client)
    login(client, "owner", "owner123")
    r = client.get("/dispatch")
    assert r.status_code == 200
    assert "SYNTHETIC_FAILURE_REASON_16" in r.text, \
        "reason not surfaced — SQL event name mismatch"
    row = next(o for o in r.context["failed"] if o["id"] == oid)
    assert row["failed_at"] is not None


def test_R7_failed_reason_is_html_escaped(client):
    """Reason text originates in a free-text field; it must be escaped when
    rendered on /dispatch."""
    from app import db
    login(client, "owner", "owner123")
    r = client.post("/call/submit", json={
        "phone": "+493099990017", "name": "Synthetic R7 escape",
        "address": {"street": "Testweg", "house_number": "1",
                    "plz": "10115", "city": "Berlin"},
        "items": [{"menu_item_id": 1, "qty": 1}],
    })
    oid = r.json()["order_id"]
    client.post(f"/confirmer/{oid}/approve")
    client.post(f"/kitchen/{oid}/ready")
    with db.connect() as d:
        cid = d.execute(
            "SELECT id FROM users WHERE username='courier1'"
        ).fetchone()[0]
    client.post(f"/dispatch/{oid}/assign", data={"courier_id": cid})
    logout(client)
    login(client, "courier1", "courier123")
    client.post(f"/courier/{oid}/start")
    client.post(f"/courier/{oid}/failed",
                data={"reason": "<script>alert(1)</script>"})
    logout(client)
    login(client, "owner", "owner123")
    html = client.get("/dispatch").text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("role", ["kitchen", "courier1"])
def test_R7_failed_reason_hidden_from_wrong_roles(client, role):
    """Non-owner / non-confirmer roles must not see the dispatch page at all."""
    login(client, role, {"kitchen": "kitchen123", "courier1": "courier123"}[role])
    r = client.get("/dispatch", follow_redirects=False)
    assert r.status_code == 403


# =========================================================
# Evidence integrity — observations mirror the input exactly
# =========================================================

def test_evidence_mirrors_input_time_and_quality():
    """Observations must contain the exact numbers the operator supplied."""
    rows = _healthy_rows(phone={
        "status": "manual", "quality": 1, "time_loss_min_per_day": 90,
    })
    result = _analyze(rows)
    s = next(s for s in result.suggestions
             if s.improvement.code == "ai_phone_reception")
    joined = " | ".join(obs for _, obs in s.evidence)
    assert "Qualität 1/5" in joined
    assert "90 min/Tag" in joined


def test_evidence_does_not_mention_zero_time_as_pain():
    """A reported `time_loss_min_per_day=0` must not appear as a pain indicator."""
    rows = _healthy_rows(phone={
        "status": "manual", "quality": 5, "automation": 1,
        "time_loss_min_per_day": 0,
    })
    result = _analyze(rows)
    for s in result.suggestions:
        if s.improvement.code != "ai_phone_reception":
            continue
        joined = " | ".join(obs for _, obs in s.evidence)
        assert "0 min/Tag" not in joined, \
            "zero time loss leaked into pain evidence"


# =========================================================
# Scenario A — manual with real losses → actionable recommendations
# =========================================================

def test_scenario_A_manual_with_losses_gives_recommendations():
    rows = _healthy_rows(
        phone={"status": "manual", "quality": 1, "time_loss_min_per_day": 120},
        kitchen={"status": "manual", "quality": 2, "time_loss_min_per_day": 60},
        couriers={"status": "manual", "quality": 2, "time_loss_min_per_day": 45},
        manual_ops={"status": "manual", "quality": 1, "time_loss_min_per_day": 90},
    )
    result = _analyze(rows)
    codes = {s.improvement.code for s in result.suggestions}
    assert "ai_phone_reception" in codes
    assert "kds" in codes
    assert "delivery_mgmt" in codes
    assert result.outcome == "has_findings"


# =========================================================
# Scenario B — POS + Lieferando without own delivery
# =========================================================

def test_scenario_B_platform_only_hides_dispatch_module():
    rows = _healthy_rows(
        pos={"current_tool": "Existing Lightspeed POS"},
        delivery_platforms={"current_tool": "Lieferando"},
        couriers={"status": "missing",
                  "notes": "Only platform delivery, no own fleet"},
        phone={"status": "manual", "quality": 2, "time_loss_min_per_day": 90},
    )
    result = _analyze(rows)
    codes = {s.improvement.code for s in result.suggestions}
    assert "delivery_mgmt" not in codes
    # dispatch must appear under not_applicable with the platform-only reason.
    reasons = {code: reason for code, reason in result.not_applicable}
    assert "delivery_mgmt" in reasons
    assert "Plattformen" in reasons["delivery_mgmt"]


# =========================================================
# Scenario C — fully automated → no_need
# =========================================================

def test_scenario_C_fully_automated_is_no_need():
    result = _analyze(_healthy_rows())
    assert result.outcome == "no_need"
    assert result.suggestions == ()
    assert result.problems == ()


# =========================================================
# Scenario D — healthy manual with zero losses → NOT required (R1)
# =========================================================

def test_scenario_D_healthy_manual_zero_loss_is_not_sold():
    """A manual process can be well-run. Blueprint must not sell to it."""
    rows = _healthy_rows(phone={
        "status": "manual", "quality": 5, "automation": 1,
        "time_loss_min_per_day": 0,
        "notes": "Pass; no complaints or lost orders in the last quarter.",
    })
    result = _analyze(rows)
    required_phone = [
        s for s in result.suggestions
        if s.improvement.code == "ai_phone_reception" and s.verdict == "required"
    ]
    assert not required_phone
    # And the outcome should not be `has_findings` driven by this manual area
    # alone. A `conditional` low-confidence suggestion is tolerated.
    for s in result.suggestions:
        if s.improvement.code == "ai_phone_reception":
            assert s.verdict == "conditional"
            assert s.confidence in ("low", "medium")


# =========================================================
# Scenario E — confirmed payments problem, no catalog match
# =========================================================

def test_scenario_E_payments_problem_without_catalog_match():
    rows = _healthy_rows(payments={
        "status": "missing", "quality": 1, "time_loss_min_per_day": 120,
        "notes": "TSE missing, GoBD compliance unresolved",
    })
    result = _analyze(rows)
    assert result.outcome == "problems_without_match"
    assert "payments" in result.problems_without_match
    assert result.suggestions == ()
    problem = next(p for p in result.problems if p.area_code == "payments")
    assert problem.confidence == "high"


# =========================================================
# Scenario F — contradictory / incomplete data → honest confidence
# =========================================================

def test_scenario_F_contradictory_data_lowers_confidence():
    """`status=available` + `verified=0` + a low quality score sends a
    conflicting signal; confidence must not be `high`."""
    rows = _healthy_rows(phone={
        "status": "available", "verified": 0, "quality": 1,
        "time_loss_min_per_day": 90,
        "notes": "Available but quality self-rated low",
    })
    result = _analyze(rows)
    phone_suggestions = [
        s for s in result.suggestions
        if s.improvement.code == "ai_phone_reception"
    ]
    assert phone_suggestions, "Measured pain should surface at least a conditional suggestion"
    for s in phone_suggestions:
        assert s.confidence != "high"


def test_scenario_F_incomplete_signals_do_not_fire_required():
    rows = _healthy_rows(phone={
        "status": "partial", "quality": None, "automation": None,
        "time_loss_min_per_day": None, "notes": "",
    })
    result = _analyze(rows)
    for s in result.suggestions:
        if s.improvement.code == "ai_phone_reception":
            assert s.verdict != "required"


# =========================================================
# Scenario G — legacy profile migration (R6)
# =========================================================
# Covered by test_R6_legacy_unselected_overrides_do_not_survive above.


# =========================================================
# Scenario H — failed delivery reason visible (R7)
# =========================================================
# Covered by test_R7_failed_delivery_reason_and_timestamp_visible above.


# =========================================================
# Regression: catalog + outcome banners
# =========================================================

def test_report_renders_problems_without_match_outcome(client):
    """The Jinja template must render the new outcome banner."""
    login(client, "owner", "owner123")
    pid = _create(client, name="E payments gap")
    # 11 of 12 answered healthy; payments missing with evidence.
    for code in ("pos", "delivery_platforms", "phone", "online_orders",
                 "kitchen", "couriers", "crm", "analytics", "menu_compliance",
                 "accounting", "manual_ops"):
        _area(client, pid, code)
    _area(client, pid, "payments",
          status="missing", quality="1", time_loss_min_per_day="120",
          notes="Payment process absent", current_tool="", verified="1")
    html = client.get(f"/blueprint/proposal/{pid}").text
    assert "Probleme festgestellt" in html
    assert "Katalog bietet derzeit kein passendes Modul" in html
    html = client.get(f"/blueprint/proposal/{pid}/report").text
    assert "Katalog bietet derzeit kein passendes Modul" in html
    # And it does NOT silently say "no need".
    assert "Aktuell kein zusätzlicher Implementierungsbedarf festgestellt" not in html
