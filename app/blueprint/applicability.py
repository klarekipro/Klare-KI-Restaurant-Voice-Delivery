"""Per-improvement applicability rules (MISSION 14 remediation).

The MISSION 13 Codex audit established that MISSION 12's gap engine proposed
every catalog module whenever the corresponding area was not fully `available`.
That turned Blueprint into a sales pitch for the Klare KI Hub instead of an
objective diagnostic.

This module encodes an *applicability gate* per improvement. Each rule inspects
the full set of findings (not just one area) and returns:

- ``required``        — a concrete, observable gap exists that the module could
                        address, with a solid driver (status plus quality or
                        time loss).
- ``conditional``     — a signal exists but the evidence is weak (e.g. status
                        ``partial`` only, no quality rating).
- ``not_applicable``  — the restaurant's situation makes this module inherently
                        unsuitable (e.g. platform-only delivery for a module
                        about own couriers; a working phone for a phone module).
- ``insufficient_data`` — the responsible area was not answered or marked
                        ``unknown``. The suggestion is *not* produced and the
                        area is listed under "Noch zu klären".

Rules are pure functions over a dict ``findings_by_area``; they do not touch
the database or import from the rest of the app except the shared dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


Verdict = str  # "required" | "conditional" | "not_applicable" | "insufficient_data"


@dataclass(frozen=True)
class Applicability:
    verdict: Verdict
    reason: str
    evidence: tuple[tuple[str, str], ...]      # (area_code, observation)
    confidence: str                             # "low" | "medium" | "high"


def _as_dict(finding) -> dict:
    """Normalise a sqlite3.Row or dict to a plain dict for rule authors."""
    if isinstance(finding, dict):
        return finding
    return {k: finding[k] for k in finding.keys()}


def _finding(by_area: Mapping, code: str):
    row = by_area.get(code)
    return _as_dict(row) if row is not None else None


def _bad(status: str) -> bool:
    return status in ("missing", "manual", "partial")


def _good(status: str) -> bool:
    return status == "available"


def _unknown_or_missing(f) -> bool:
    return f is None or f.get("status") == "unknown"


def _strong_pain(f) -> bool:
    """Explicit, measurable pain signal beyond status alone."""
    quality = f.get("quality")
    automation = f.get("automation")
    time_loss = f.get("time_loss_min_per_day")
    return (
        (quality is not None and quality <= 2)
        or (automation is not None and automation <= 2)
        or (time_loss is not None and time_loss >= 60)
    )


def _observation(area_code: str, label: str, f) -> tuple[str, str]:
    bits = [label]
    if f.get("current_tool"):
        bits.append(f"aktuell: {f['current_tool']}")
    if f.get("quality") is not None:
        bits.append(f"Qualität {f['quality']}/5")
    if f.get("automation") is not None:
        bits.append(f"Automatisierung {f['automation']}/5")
    if f.get("time_loss_min_per_day"):
        bits.append(f"geschätzter Zeitverlust {f['time_loss_min_per_day']} min/Tag")
    return (area_code, "; ".join(bits))


# ---------- individual improvement rules ----------

def _ai_phone_reception(by_area):
    phone = _finding(by_area, "phone")
    if _unknown_or_missing(phone):
        return Applicability("insufficient_data",
                             "Bereich Telefonie noch nicht beantwortet.",
                             (), "low")
    status = phone["status"]
    if _good(status) and not _strong_pain(phone):
        return Applicability("not_applicable",
                             "Telefonannahme funktioniert laut Angabe.",
                             (_observation("phone", "Telefonannahme funktioniert", phone),),
                             "high")
    if status == "missing":
        return Applicability("required",
                             "Telefonannahme fehlt vollständig.",
                             (_observation("phone", "Status: fehlt", phone),),
                             "high")
    if status == "manual" and _strong_pain(phone):
        return Applicability("required",
                             "Manuelle Telefonannahme mit konkret genannter Belastung.",
                             (_observation("phone", "Status: manuell", phone),),
                             "high")
    if status == "manual":
        return Applicability("conditional",
                             "Manuelle Telefonannahme, keine konkrete Belastung angegeben.",
                             (_observation("phone", "Status: manuell", phone),),
                             "medium")
    # partial
    return Applicability("conditional",
                         "Telefonannahme teilweise, Umfang offen.",
                         (_observation("phone", "Status: teilweise", phone),),
                         "low")


def _unified_order_intake(by_area):
    platforms = _finding(by_area, "delivery_platforms")
    online = _finding(by_area, "online_orders")
    pos = _finding(by_area, "pos")

    if _unknown_or_missing(platforms) and _unknown_or_missing(online):
        return Applicability("insufficient_data",
                             "Bereiche Lieferplattformen und Online-Bestellungen "
                             "noch nicht beantwortet.", (), "low")

    # If no delivery platforms are used and no online channel exists, there is
    # nothing to unify.
    if (platforms and platforms["status"] == "missing"
            and online and online["status"] == "missing"):
        return Applicability("not_applicable",
                             "Weder Plattformen noch Online-Kanäle vorhanden.",
                             (), "high")

    evidence = []
    strong = False
    # Platforms exist and are run manually → classic tablet-chaos pain.
    if platforms and platforms["status"] == "manual":
        evidence.append(_observation("delivery_platforms",
                                     "Plattform-Bestellungen laufen manuell",
                                     platforms))
        if _strong_pain(platforms):
            strong = True
    # Online channel exists but POS not integrated.
    if online and online["status"] in ("partial", "manual") and pos:
        if pos["status"] in ("manual", "partial", "missing"):
            evidence.append(_observation("online_orders",
                                         "Online-Kanal ohne POS-Integration",
                                         online))
            if _strong_pain(online):
                strong = True
    if not evidence:
        return Applicability("not_applicable",
                             "Kein Hinweis auf Doppelerfassung oder Tablet-Chaos.",
                             (), "medium")
    verdict = "required" if strong else "conditional"
    return Applicability(verdict,
                         "Hinweise auf Mehrkanal-Doppelerfassung vorhanden.",
                         tuple(evidence),
                         "medium" if strong else "low")


def _kds(by_area):
    kitchen = _finding(by_area, "kitchen")
    if _unknown_or_missing(kitchen):
        return Applicability("insufficient_data",
                             "Bereich Küche noch nicht beantwortet.", (), "low")
    status = kitchen["status"]
    if _good(status) and not _strong_pain(kitchen):
        return Applicability("not_applicable",
                             "Küchenorganisation funktioniert laut Angabe.",
                             (_observation("kitchen", "Status: vorhanden", kitchen),),
                             "high")
    if status == "missing":
        return Applicability("required",
                             "Keine strukturierte Küchenanzeige vorhanden.",
                             (_observation("kitchen", "Status: fehlt", kitchen),),
                             "high")
    if _strong_pain(kitchen):
        return Applicability("required",
                             "Küchenorganisation mit konkret genannter Belastung.",
                             (_observation("kitchen", f"Status: {status}", kitchen),),
                             "medium")
    if status in ("manual", "partial"):
        return Applicability("conditional",
                             "Küchenorganisation nur teilweise, keine konkrete Belastung.",
                             (_observation("kitchen", f"Status: {status}", kitchen),),
                             "low")
    return Applicability("insufficient_data", "Unerwarteter Status.", (), "low")


def _delivery_mgmt(by_area):
    couriers = _finding(by_area, "couriers")
    platforms = _finding(by_area, "delivery_platforms")

    # Hard applicability gate: does the restaurant actually run own delivery?
    # Signal: `couriers` status in (available/partial/manual) → yes.
    # Platform-only operations are indicated by `couriers=missing` with
    # platforms present → delivery_mgmt is NOT applicable.
    if _unknown_or_missing(couriers):
        return Applicability("insufficient_data",
                             "Bereich Fahrer/Dispatch noch nicht beantwortet.",
                             (), "low")

    couriers_status = couriers["status"]
    platforms_known = platforms is not None and platforms["status"] != "unknown"
    platforms_status = platforms["status"] if platforms_known else "unknown"

    # Reality-Check #5: wenn Plattformen selbst nicht entschieden sind, ist
    # „Plattform-only" eine unbelegte Vermutung. In diesem Fall fordern wir
    # Klärung statt automatisch not_applicable zu entscheiden.
    if couriers_status == "missing" and not platforms_known:
        return Applicability("insufficient_data",
                             "Keine eigenen Fahrer; der Status der Plattformen "
                             "ist offen — zunächst klären, nicht automatisch "
                             "als Plattform-only werten.",
                             (_observation("couriers", "Keine eigenen Fahrer", couriers),),
                             "medium")

    if couriers_status == "missing" and platforms_status != "missing":
        evidence = [_observation("couriers", "Keine eigenen Fahrer", couriers)]
        if platforms is not None:
            evidence.append(_observation("delivery_platforms",
                                         "Plattformen aktiv", platforms))
        return Applicability("not_applicable",
                             "Zustellung erfolgt ausschließlich über Plattformen "
                             "(keine eigenen Fahrer).",
                             tuple(evidence),
                             "high")

    if couriers_status == "missing" and platforms_status == "missing":
        return Applicability("not_applicable",
                             "Kein Zustellbetrieb erkennbar (nur Abholung oder vor Ort).",
                             (_observation("couriers", "Keine Fahrer", couriers),),
                             "medium")

    if _good(couriers_status) and not _strong_pain(couriers):
        return Applicability("not_applicable",
                             "Fahrer-Disposition funktioniert laut Angabe.",
                             (_observation("couriers", "Status: vorhanden", couriers),),
                             "high")

    # Reality-Check #5: available + konkret genannte Belastung ist ein Signal
    # (nicht genug für automatische Dringlichkeit, aber verdient einen
    # Vorschlag mit expliziter Begründung).
    if _good(couriers_status) and _strong_pain(couriers):
        return Applicability("conditional",
                             "Fahrer-Disposition im Einsatz, aber mit konkret "
                             "genannter Belastung.",
                             (_observation("couriers", "Status: vorhanden mit Pain",
                                           couriers),),
                             "low")

    if couriers_status in ("manual", "partial"):
        verdict = "required" if _strong_pain(couriers) else "conditional"
        return Applicability(verdict,
                             "Fahrer-Disposition ohne vollständige Automatisierung.",
                             (_observation("couriers", f"Status: {couriers_status}", couriers),),
                             "medium" if verdict == "required" else "low")

    return Applicability("insufficient_data", "Unerwarteter Status.", (), "low")


def _crm_automation(by_area):
    crm = _finding(by_area, "crm")
    if _unknown_or_missing(crm):
        return Applicability("insufficient_data",
                             "Bereich CRM noch nicht beantwortet.", (), "low")
    status = crm["status"]
    if _good(status) and not _strong_pain(crm):
        return Applicability("not_applicable",
                             "Stammkundenpflege erfolgt laut Angabe.",
                             (_observation("crm", "Status: vorhanden", crm),),
                             "high")
    if status == "missing":
        return Applicability("required",
                             "Keine Stammkundenpflege.",
                             (_observation("crm", "Status: fehlt", crm),),
                             "high")
    if _strong_pain(crm):
        return Applicability("required",
                             "CRM-Prozess mit konkreter Belastung.",
                             (_observation("crm", f"Status: {status}", crm),),
                             "medium")
    return Applicability("conditional",
                         "Stammkundenpflege nur teilweise.",
                         (_observation("crm", f"Status: {status}", crm),),
                         "low")


def _owner_analytics(by_area):
    analytics = _finding(by_area, "analytics")
    if _unknown_or_missing(analytics):
        return Applicability("insufficient_data",
                             "Bereich Analytik noch nicht beantwortet.", (), "low")
    status = analytics["status"]
    if _good(status):
        return Applicability("not_applicable",
                             "Betreiber nutzt bereits regelmäßige Kennzahlen.",
                             (_observation("analytics", "Status: vorhanden", analytics),),
                             "high")
    if status == "missing":
        return Applicability("required",
                             "Keine regelmäßige Kennzahlen-Übersicht.",
                             (_observation("analytics", "Status: fehlt", analytics),),
                             "medium")
    return Applicability("conditional",
                         "Kennzahlen nur teilweise vorhanden.",
                         (_observation("analytics", f"Status: {status}", analytics),),
                         "low")


def _staff_automation(by_area):
    manual_ops = _finding(by_area, "manual_ops")
    if _unknown_or_missing(manual_ops):
        return Applicability("insufficient_data",
                             "Bereich manuelle Prozesse noch nicht beantwortet.",
                             (), "low")
    status = manual_ops["status"]
    # If the operator reports NO manual processes, this module is not needed
    # — even if other areas are weak, this specific module is about manual ops.
    if status in ("available",):
        return Applicability("not_applicable",
                             "Keine zu automatisierenden manuellen Prozesse genannt.",
                             (_observation("manual_ops", "Status: vorhanden", manual_ops),),
                             "high")
    if _strong_pain(manual_ops):
        return Applicability("required",
                             "Manuelle Betriebsprozesse mit konkreter Belastung.",
                             (_observation("manual_ops", f"Status: {status}", manual_ops),),
                             "high")
    if status in ("manual", "partial", "missing"):
        return Applicability("conditional",
                             "Hinweis auf manuelle Prozesse, ohne quantifizierte Belastung.",
                             (_observation("manual_ops", f"Status: {status}", manual_ops),),
                             "medium")
    return Applicability("insufficient_data", "Unerwarteter Status.", (), "low")


def _review_mgmt(by_area):
    # Blueprint has no dedicated reviews area; the module only applies if the
    # operator explicitly flagged a review-management pain in CRM notes
    # (e.g. "Google-Bewertungen bleiben unbeantwortet"). Without that evidence,
    # the module stays silent.
    crm = _finding(by_area, "crm")
    if _unknown_or_missing(crm):
        return Applicability("insufficient_data",
                             "CRM-Bereich noch nicht beantwortet.", (), "low")
    notes = (crm.get("notes") or "").lower()
    review_terms = ("bewertung", "review", "google", "rezension")
    if any(term in notes for term in review_terms):
        return Applicability("conditional",
                             "Hinweis auf Bewertungsmanagement in den Notizen.",
                             (_observation("crm", "Bewertungen in Notizen genannt", crm),),
                             "low")
    return Applicability("not_applicable",
                         "Kein Hinweis auf Bewertungs-Problem.", (), "high")


def _workflow_automation(by_area):
    accounting = _finding(by_area, "accounting")
    menu = _finding(by_area, "menu_compliance")
    manual_ops = _finding(by_area, "manual_ops")

    if (_unknown_or_missing(accounting)
            and _unknown_or_missing(menu)
            and _unknown_or_missing(manual_ops)):
        return Applicability("insufficient_data",
                             "Bereiche Buchhaltung, Speisekarte und manuelle "
                             "Prozesse noch nicht beantwortet.", (), "low")

    evidence = []
    strong = False
    if accounting and accounting["status"] in ("manual", "partial", "missing"):
        evidence.append(_observation("accounting",
                                     f"Buchhaltung: {accounting['status']}",
                                     accounting))
        if _strong_pain(accounting):
            strong = True
    if menu and menu["status"] in ("manual", "partial", "missing"):
        evidence.append(_observation("menu_compliance",
                                     f"Speisekarte/LMIV: {menu['status']}",
                                     menu))
        if _strong_pain(menu):
            strong = True
    if manual_ops and manual_ops["status"] in ("manual",) and _strong_pain(manual_ops):
        evidence.append(_observation("manual_ops",
                                     "Manuelle Prozesse mit Belastung",
                                     manual_ops))
        strong = True
    if not evidence:
        return Applicability("not_applicable",
                             "Keine wiederkehrenden Medienbrüche genannt.", (), "medium")
    verdict = "required" if strong else "conditional"
    return Applicability(verdict,
                         "Hinweise auf Medienbrüche in Buchhaltung oder Speisekarte.",
                         tuple(evidence),
                         "medium" if strong else "low")


RULES: Mapping[str, Callable[[Mapping], Applicability]] = {
    "ai_phone_reception":  _ai_phone_reception,
    "unified_order_intake": _unified_order_intake,
    "kds":                 _kds,
    "delivery_mgmt":       _delivery_mgmt,
    "crm_automation":      _crm_automation,
    "owner_analytics":     _owner_analytics,
    "staff_automation":    _staff_automation,
    "review_mgmt":         _review_mgmt,
    "workflow_automation": _workflow_automation,
}
