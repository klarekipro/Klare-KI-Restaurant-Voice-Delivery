"""Blueprint HTTP routes (DEMO · DIAGNOSE · PROPOSAL)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import auth, db, formatting
from . import catalog, gap, redact

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
formatting.register(_TEMPLATES)
_TEMPLATES.env.filters["bp_status_de"] = lambda c: catalog.STATUS_DE.get(c, c)
_TEMPLATES.env.filters["bp_status_chip"] = lambda c: catalog.STATUS_CHIP.get(c, "status-badge--unknown")
_TEMPLATES.env.filters["bp_priority_de"] = lambda c: catalog.PRIORITY_DE.get(c, c)


router = APIRouter(prefix="/blueprint", tags=["blueprint"])


def _ctx(request: Request, **extra) -> dict:
    base = {
        "request": request,
        "user": auth.current_user(request),
        "catalog_version": catalog.CATALOG_VERSION,
        "areas": catalog.DIAGNOSE_AREAS,
        "status_codes": catalog.STATUS_CODES,
        "status_de": catalog.STATUS_DE,
    }
    base.update(extra)
    return base


def _log(conn, user_id: int, action: str, profile_id: int, reason: str = "") -> None:
    conn.execute(
        "INSERT INTO access_log (user_id, action, object_type, object_id, reason) "
        "VALUES (?, ?, 'blueprint_profile', ?, ?)",
        (user_id, action, str(profile_id), reason[:120]),
    )


def _load_profile(conn, pid: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM diagnostic_profiles WHERE id = ?", (pid,)
    ).fetchone()
    return dict(row) if row else None


def _load_findings(conn, pid: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM diagnostic_findings WHERE profile_id = ?", (pid,)
    ).fetchall()
    return [dict(r) for r in rows]


def _load_selections(conn, pid: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM diagnostic_selections WHERE profile_id = ?", (pid,)
    ).fetchall()
    return [dict(r) for r in rows]


# ---------- Overview + DEMO ----------

@router.get("", response_class=HTMLResponse)
def overview(request: Request):
    user = auth.current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="login required")
    return _TEMPLATES.TemplateResponse(request, "blueprint/overview.html", _ctx(request))


@router.get("/demo", response_class=HTMLResponse)
def demo(request: Request):
    user = auth.current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="login required")
    return _TEMPLATES.TemplateResponse(
        request, "blueprint/demo.html",
        _ctx(request, improvements=catalog.IMPROVEMENTS),
    )


# ---------- DIAGNOSE list + new ----------

@router.get("/diagnose", response_class=HTMLResponse)
def diagnose_list(request: Request,
                  user: auth.User = Depends(auth.require_strict("owner"))):
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT p.*, "
            "       (SELECT COUNT(*) FROM diagnostic_findings f WHERE f.profile_id = p.id) AS answered, "
            "       u.display_name AS created_by_name "
            "FROM diagnostic_profiles p "
            "LEFT JOIN users u ON p.created_by = u.id "
            "ORDER BY p.updated_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return _TEMPLATES.TemplateResponse(
        request, "blueprint/diagnose_list.html",
        _ctx(request, profiles=[dict(r) for r in rows], total_areas=len(catalog.DIAGNOSE_AREAS)),
    )


@router.get("/diagnose/new", response_class=HTMLResponse)
def diagnose_new_form(request: Request,
                      user: auth.User = Depends(auth.require_strict("owner"))):
    return _TEMPLATES.TemplateResponse(
        request, "blueprint/diagnose_new.html", _ctx(request, error=None),
    )


@router.post("/diagnose/new")
def diagnose_new_submit(
    request: Request,
    restaurant_name: str = Form(...),
    city: str = Form(""),
    cuisine: str = Form(""),
    locations_count: int = Form(1),
    contact_person: str = Form(""),
    contact_role: str = Form(""),
    user: auth.User = Depends(auth.require_strict("owner")),
):
    name = restaurant_name.strip()
    if not name:
        raise HTTPException(400, "Restaurantname ist erforderlich.")
    if len(name) > 120 or len(city) > 80 or len(cuisine) > 80 \
            or len(contact_person) > 120 or len(contact_role) > 60:
        raise HTTPException(400, "Eingabefeld überschreitet die zulässige Länge.")
    if locations_count < 1 or locations_count > 999:
        raise HTTPException(400, "Standortanzahl muss zwischen 1 und 999 liegen.")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "INSERT INTO diagnostic_profiles "
            "(restaurant_name, city, cuisine, locations_count, "
            " contact_person, contact_role, catalog_version, created_by) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (name, city.strip(), cuisine.strip(), locations_count,
             contact_person.strip(), contact_role.strip(),
             catalog.CATALOG_VERSION, user.id),
        )
        pid = cur.lastrowid
        _log(conn, user.id, "blueprint.profile.create", pid)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return RedirectResponse(f"/blueprint/diagnose/{pid}", status_code=303)


# ---------- DIAGNOSE profile overview + area ----------

@router.get("/diagnose/{pid}", response_class=HTMLResponse)
def diagnose_profile(request: Request, pid: int,
                     user: auth.User = Depends(auth.require_strict("owner"))):
    conn = db.connect()
    try:
        profile = _load_profile(conn, pid)
        if not profile:
            raise HTTPException(404, "Profil nicht gefunden.")
        findings = _load_findings(conn, pid)
    finally:
        conn.close()
    answered = {f["area_code"]: f for f in findings}
    return _TEMPLATES.TemplateResponse(
        request, "blueprint/diagnose_profile.html",
        _ctx(request,
             profile=profile,
             findings=answered,
             total=len(catalog.DIAGNOSE_AREAS),
             done=len(answered)),
    )


@router.get("/diagnose/{pid}/area/{code}", response_class=HTMLResponse)
def diagnose_area_form(request: Request, pid: int, code: str,
                       user: auth.User = Depends(auth.require_strict("owner"))):
    area = catalog.AREA_BY_CODE.get(code)
    if not area:
        raise HTTPException(404, "Bereich unbekannt.")
    conn = db.connect()
    try:
        profile = _load_profile(conn, pid)
        if not profile:
            raise HTTPException(404, "Profil nicht gefunden.")
        row = conn.execute(
            "SELECT * FROM diagnostic_findings WHERE profile_id = ? AND area_code = ?",
            (pid, code),
        ).fetchone()
        findings = _load_findings(conn, pid)
    finally:
        conn.close()
    answered_codes = {f["area_code"] for f in findings}
    unanswered = [a for a in catalog.DIAGNOSE_AREAS if a.code not in answered_codes and a.code != code]
    next_area = unanswered[0] if unanswered else None
    return _TEMPLATES.TemplateResponse(
        request, "blueprint/diagnose_area.html",
        _ctx(request,
             profile=profile,
             area=area,
             finding=dict(row) if row else None,
             done=len(answered_codes),
             total=len(catalog.DIAGNOSE_AREAS),
             next_area=next_area),
    )


def _int_or_none(raw: str, lo: int, hi: int) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        raise HTTPException(400, "Ungültige Zahl.")
    if value < lo or value > hi:
        raise HTTPException(400, f"Wert muss zwischen {lo} und {hi} liegen.")
    return value


@router.post("/diagnose/{pid}/area/{code}")
def diagnose_area_submit(
    request: Request, pid: int, code: str,
    status: str = Form(...),
    current_tool: str = Form(""),
    quality: str = Form(""),
    automation: str = Form(""),
    time_loss_min_per_day: str = Form(""),
    verified: str = Form(""),
    notes: str = Form(""),
    user: auth.User = Depends(auth.require_strict("owner")),
):
    if code not in catalog.AREA_BY_CODE:
        raise HTTPException(404, "Bereich unbekannt.")
    if status not in catalog.STATUS_CODES:
        raise HTTPException(400, "Status ungültig.")
    current_tool = current_tool.strip()[:120]
    quality_v = _int_or_none(quality, 1, 5)
    automation_v = _int_or_none(automation, 1, 5)
    time_v = _int_or_none(time_loss_min_per_day, 0, 24 * 60)
    verified_v = 1 if verified in ("1", "on", "true") else 0

    redaction = redact.redact(notes)

    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        profile = _load_profile(conn, pid)
        if not profile:
            raise HTTPException(404, "Profil nicht gefunden.")
        conn.execute(
            "INSERT INTO diagnostic_findings "
            "(profile_id, area_code, status, current_tool, quality, automation, "
            " time_loss_min_per_day, verified, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(profile_id, area_code) DO UPDATE SET "
            "  status=excluded.status, current_tool=excluded.current_tool, "
            "  quality=excluded.quality, automation=excluded.automation, "
            "  time_loss_min_per_day=excluded.time_loss_min_per_day, "
            "  verified=excluded.verified, notes=excluded.notes, "
            "  updated_at=datetime('now')",
            (pid, code, status, current_tool, quality_v, automation_v,
             time_v, verified_v, redaction.text),
        )
        conn.execute(
            "UPDATE diagnostic_profiles SET updated_at=datetime('now') WHERE id=?",
            (pid,),
        )
        _log(conn, user.id, "blueprint.finding.upsert", pid, f"area={code}")
        if redaction.changed:
            _log(conn, user.id, "blueprint.notes.redacted", pid,
                 f"area={code} hits={','.join(redaction.hits)}")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return RedirectResponse(f"/blueprint/diagnose/{pid}", status_code=303)


# ---------- Edit profile basics (MISSION 14 D01) ----------

@router.get("/diagnose/{pid}/edit", response_class=HTMLResponse)
def diagnose_edit_form(request: Request, pid: int,
                       user: auth.User = Depends(auth.require_strict("owner"))):
    conn = db.connect()
    try:
        profile = _load_profile(conn, pid)
    finally:
        conn.close()
    if not profile:
        raise HTTPException(404, "Profil nicht gefunden.")
    return _TEMPLATES.TemplateResponse(
        request, "blueprint/diagnose_edit.html",
        _ctx(request, profile=profile, error=None),
    )


@router.post("/diagnose/{pid}/edit")
def diagnose_edit_submit(
    request: Request, pid: int,
    restaurant_name: str = Form(...),
    city: str = Form(""),
    cuisine: str = Form(""),
    locations_count: int = Form(1),
    contact_person: str = Form(""),
    contact_role: str = Form(""),
    user: auth.User = Depends(auth.require_strict("owner")),
):
    name = restaurant_name.strip()
    if not name:
        raise HTTPException(400, "Restaurantname ist erforderlich.")
    if len(name) > 120 or len(city) > 80 or len(cuisine) > 80 \
            or len(contact_person) > 120 or len(contact_role) > 60:
        raise HTTPException(400, "Eingabefeld überschreitet die zulässige Länge.")
    if locations_count < 1 or locations_count > 999:
        raise HTTPException(400, "Standortanzahl muss zwischen 1 und 999 liegen.")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not _load_profile(conn, pid):
            raise HTTPException(404, "Profil nicht gefunden.")
        conn.execute(
            "UPDATE diagnostic_profiles SET "
            "  restaurant_name=?, city=?, cuisine=?, locations_count=?, "
            "  contact_person=?, contact_role=?, updated_at=datetime('now') "
            "WHERE id=?",
            (name, city.strip(), cuisine.strip(), locations_count,
             contact_person.strip(), contact_role.strip(), pid),
        )
        _log(conn, user.id, "blueprint.profile.update", pid, "basics")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return RedirectResponse(f"/blueprint/diagnose/{pid}", status_code=303)


# ---------- Status transitions + delete ----------

_ALLOWED_STATUS = ("draft", "review", "shared")


@router.post("/diagnose/{pid}/status")
def diagnose_status(request: Request, pid: int,
                    status: str = Form(...),
                    user: auth.User = Depends(auth.require_strict("owner"))):
    if status not in _ALLOWED_STATUS:
        raise HTTPException(400, "Status ungültig.")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not _load_profile(conn, pid):
            raise HTTPException(404, "Profil nicht gefunden.")
        conn.execute(
            "UPDATE diagnostic_profiles SET status=?, updated_at=datetime('now') WHERE id=?",
            (status, pid),
        )
        _log(conn, user.id, "blueprint.profile.update", pid, f"status={status}")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return RedirectResponse(f"/blueprint/diagnose/{pid}", status_code=303)


@router.post("/diagnose/{pid}/delete")
def diagnose_delete(request: Request, pid: int,
                    user: auth.User = Depends(auth.require_strict("owner"))):
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not _load_profile(conn, pid):
            raise HTTPException(404, "Profil nicht gefunden.")
        conn.execute("DELETE FROM diagnostic_profiles WHERE id=?", (pid,))
        _log(conn, user.id, "blueprint.profile.delete", pid)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return RedirectResponse("/blueprint/diagnose", status_code=303)


# ---------- PROPOSAL ----------

def _gap_for_profile(conn, pid: int):
    findings = _load_findings(conn, pid)
    return findings, gap.analyze(findings)


_ENGINE_PRIORITY = {
    ("required", "high"):   "high",
    ("required", "medium"): "high",
    ("required", "low"):    "medium",
    ("conditional", "high"):   "medium",
    ("conditional", "medium"): "low",
    ("conditional", "low"):    "low",
}


def _engine_priority(suggestion) -> str:
    """Default priority *suggestion* for the sales conversation.

    Documented as "Vorschlag — keine Dringlichkeitsbewertung" in the UI.
    The engine never writes this to disk; it only appears when the human
    user has not manually set a priority (MISSION 14 D05).
    """
    return _ENGINE_PRIORITY.get(
        (suggestion.verdict, suggestion.confidence), "medium"
    )


@router.get("/proposal/{pid}", response_class=HTMLResponse)
def proposal_view(request: Request, pid: int,
                  user: auth.User = Depends(auth.require_strict("owner"))):
    conn = db.connect()
    try:
        profile = _load_profile(conn, pid)
        if not profile:
            raise HTTPException(404, "Profil nicht gefunden.")
        findings, result = _gap_for_profile(conn, pid)
        selections = _load_selections(conn, pid)
    finally:
        conn.close()
    selected_codes = {s["improvement_code"] for s in selections if s["selected"]}
    # MISSION 16 R6: manual overrides only count when the row is ALSO
    # `selected=1`. Legacy MISSION 12 saves wrote `selected=0, medium` rows
    # with `priority_source='manual'` after the MISSION 14 migration; those
    # must not override new engine recommendations.
    manual_priority = {
        s["improvement_code"]: s["priority"]
        for s in selections
        if s.get("priority_source") == "manual" and s["selected"]
    }
    engine_priority = {s.improvement.code: _engine_priority(s)
                       for s in result.suggestions}
    display_priority = {**engine_priority, **manual_priority}

    return _TEMPLATES.TemplateResponse(
        request, "blueprint/proposal.html",
        _ctx(request,
             profile=profile,
             findings_by_area={f["area_code"]: f for f in findings},
             result=result,
             selected_codes=selected_codes,
             display_priority=display_priority,
             manual_priority=manual_priority,
             preserved_system_label=gap.preserved_system_label,
             improvement_by_code=catalog.IMPROVEMENT_BY_CODE,
             areas_by_code={a.code: a for a in catalog.DIAGNOSE_AREAS},
             answered=sum(1 for f in findings if f["status"] != "unknown"),
             total=len(catalog.DIAGNOSE_AREAS)),
    )


@router.post("/proposal/{pid}/select")
async def proposal_select(request: Request, pid: int,
                          user: auth.User = Depends(auth.require_strict("owner"))):
    """Persist only the actually-selected rows with a manual priority.

    MISSION 14 D05: writing a row for every catalog entry (with a default
    medium priority) silently overrode engine-generated priorities for
    improvements the user had not touched. The new contract is:

    - A row exists in ``diagnostic_selections`` ONLY for an improvement
      the user ticked.
    - Its priority is the explicit choice from the form, stored with
      ``priority_source='manual'``.
    - Un-ticked improvements have NO row — the proposal view falls back
      to the engine's suggested priority.
    """
    form = await request.form()
    selected_codes = set(form.getlist("selected"))
    priorities: dict[str, str] = {}
    for code in selected_codes:
        raw = (form.get(f"priority_{code}") or "medium").strip()
        if raw not in ("low", "medium", "high"):
            raw = "medium"
        priorities[code] = raw

    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        profile = _load_profile(conn, pid)
        if not profile:
            raise HTTPException(404, "Profil nicht gefunden.")
        conn.execute(
            "DELETE FROM diagnostic_selections WHERE profile_id=?", (pid,)
        )
        for code, prio in priorities.items():
            if code not in catalog.IMPROVEMENT_BY_CODE:
                continue
            conn.execute(
                "INSERT INTO diagnostic_selections "
                "(profile_id, improvement_code, selected, priority, priority_source) "
                "VALUES (?,?,?,?,'manual')",
                (pid, code, 1, prio),
            )
        _log(conn, user.id, "blueprint.selection.update", pid,
             f"selected={len(priorities)}")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return RedirectResponse(f"/blueprint/proposal/{pid}", status_code=303)


@router.get("/proposal/{pid}/report", response_class=HTMLResponse)
def proposal_report(request: Request, pid: int,
                    user: auth.User = Depends(auth.require_strict("owner"))):
    conn = db.connect()
    try:
        profile = _load_profile(conn, pid)
        if not profile:
            raise HTTPException(404, "Profil nicht gefunden.")
        findings, result = _gap_for_profile(conn, pid)
        selections = _load_selections(conn, pid)
        _log(conn, user.id, "blueprint.report.render", pid)
    finally:
        conn.close()

    findings_by_area = {f["area_code"]: f for f in findings}
    selected = {s["improvement_code"]: s for s in selections if s["selected"]}
    chosen = tuple(
        s for s in result.suggestions if s.improvement.code in selected
    )
    unchosen = tuple(
        s for s in result.suggestions if s.improvement.code not in selected
    )
    display_priority = {s.improvement.code: _engine_priority(s)
                        for s in result.suggestions}
    for code, row in selected.items():
        # MISSION 16 R6: only honour manual overrides on actually-selected rows.
        if row.get("priority_source") == "manual" and row.get("selected"):
            display_priority[code] = row["priority"]

    now_local = datetime.now(ZoneInfo("Europe/Berlin"))
    return _TEMPLATES.TemplateResponse(
        request, "blueprint/report.html",
        _ctx(request,
             profile=profile,
             findings_by_area=findings_by_area,
             result=result,
             selected=selected,
             chosen=chosen,
             unchosen=unchosen,
             display_priority=display_priority,
             preserved_system_label=gap.preserved_system_label,
             improvement_by_code=catalog.IMPROVEMENT_BY_CODE,
             areas_by_code={a.code: a for a in catalog.DIAGNOSE_AREAS},
             generated_at=now_local.strftime("%d.%m.%Y %H:%M"),
             total=len(catalog.DIAGNOSE_AREAS),
             outcome=result.outcome),
    )
