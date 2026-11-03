"""Evidence-based gap analysis for Blueprint (MISSION 14 remediation).

The previous engine proposed any catalog module whenever the matching area
was not fully ``available``. The MISSION 13 audit called this out: unmarked
boxes became sales opportunities. The engine below gates every proposal
through ``applicability.RULES`` and returns a per-suggestion ``evidence``
trail so the report can show *why* a specific restaurant should consider a
specific module — not just that the module exists in a catalog.

Nothing in this module writes to the database. The engine is purely a
function of the finding rows plus the applicability rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .applicability import RULES, _notes_signal_problem, _strong_pain
from .catalog import (
    AREA_BY_CODE,
    IMPROVEMENTS,
    IMPROVEMENT_BY_CODE,
    Improvement,
)

# Core areas: if any of these is unanswered or unknown, we do not pronounce
# "no need" — because they most often decide the real pain in a German
# delivery restaurant. Non-core unknowns are listed as "to clarify" but
# do not block the no-need outcome.
CRITICAL_AREAS: tuple[str, ...] = ("pos", "payments", "phone", "kitchen")


@dataclass(frozen=True)
class Suggestion:
    improvement: Improvement
    verdict: str                                  # "required" | "conditional"
    reason: str                                   # kurze Begründung
    evidence: tuple[tuple[str, str], ...]         # (area_code, Beobachtung)
    confidence: str                               # "low" | "medium" | "high"


@dataclass(frozen=True)
class ProblemArea:
    """A confirmed or probable problem detected independent of the catalog.

    MISSION 16 R2: Blueprint must separate "no catalog match" from "no
    problem". A problem is signalled by one of these inputs:

    - ``status=missing`` for any answered area (direct admission of absence).
    - ``_strong_pain`` on an available/partial/manual area (measured
      quality<=2 or time_loss>=60 or affirmative notes).

    A ``ProblemArea`` is reported even when no catalog improvement would
    cover it. The report then shows "problems noted, no matching module" —
    not a fake catalog entry.
    """
    area_code: str
    reason: str          # kurze deutschsprachige Begründung
    confidence: str      # "low" | "medium" | "high"


@dataclass(frozen=True)
class GapResult:
    suggestions: tuple[Suggestion, ...]
    to_clarify: tuple[str, ...]                   # answered as `unknown`
    not_answered: tuple[str, ...]                 # not answered at all
    verify_recommended: tuple[str, ...]           # `available` + `verified=0`
    not_applicable: tuple[tuple[str, str], ...]   # (improvement_code, reason)
    problems: tuple[ProblemArea, ...] = ()        # independent of catalog
    problems_without_match: tuple[str, ...] = ()  # problem areas with no suggestion

    @property
    def outcome(self) -> str:
        """Classification used by the report.

        - ``insufficient`` — critical areas missing/unknown → no verdict.
        - ``problems_without_match`` — Probleme festgestellt, aber kein
          Katalog-Modul passt (MISSION 16 R2).
        - ``has_findings`` — mindestens eine Empfehlung.
        - ``no_need`` — alle 12 beantwortet, keine Probleme, keine Empfehlung.
        """
        if any(a in CRITICAL_AREAS for a in self.not_answered + self.to_clarify):
            return "insufficient"
        if self.suggestions:
            return "has_findings"
        if self.problems_without_match:
            return "problems_without_match"
        # All critical areas answered, no suggestion fired, no uncovered
        # problem, no unanswered area → honest "no need".
        if not self.not_answered:
            return "no_need"
        return "insufficient"


def _finding_dict(row) -> dict:
    if isinstance(row, dict):
        return row
    return {k: row[k] for k in row.keys()}


def analyze(findings: Iterable[Mapping]) -> GapResult:
    """Produce a GapResult from an iterable of finding rows.

    Each row exposes ``area_code``, ``status``, ``verified``, and optionally
    ``quality``, ``automation``, ``time_loss_min_per_day``, ``current_tool``,
    ``notes``. Unknown areas are listed under ``to_clarify``, un-answered
    areas under ``not_answered``.
    """
    by_area: dict[str, dict] = {}
    for row in findings:
        f = _finding_dict(row)
        code = f.get("area_code")
        if code in AREA_BY_CODE:
            by_area[code] = f

    to_clarify = tuple(
        code for code, f in sorted(by_area.items()) if f.get("status") == "unknown"
    )
    not_answered = tuple(
        a.code for a in AREA_BY_CODE.values()
        if a.code not in by_area or by_area[a.code].get("status") == "unknown"
    )
    verify_recommended = tuple(
        code for code, f in sorted(by_area.items())
        if f.get("status") == "available" and not (f.get("verified") or 0)
    )

    suggestions: list[Suggestion] = []
    not_applicable: list[tuple[str, str]] = []
    for improvement in IMPROVEMENTS:
        rule = RULES.get(improvement.code)
        if rule is None:
            continue
        verdict = rule(by_area)
        if verdict.verdict in ("required", "conditional"):
            suggestions.append(Suggestion(
                improvement=improvement,
                verdict=verdict.verdict,
                reason=verdict.reason,
                evidence=verdict.evidence,
                confidence=verdict.confidence,
            ))
        elif verdict.verdict == "not_applicable":
            not_applicable.append((improvement.code, verdict.reason))
        # insufficient_data: silently omitted; the responsible area is
        # already in to_clarify / not_answered.

    # Required first, then conditional; keep catalog order inside each bucket.
    def _rank(s: Suggestion) -> tuple[int, int]:
        bucket = 0 if s.verdict == "required" else 1
        order = next((i for i, m in enumerate(IMPROVEMENTS) if m.code == s.improvement.code), 999)
        return (bucket, order)

    suggestions.sort(key=_rank)

    # MISSION 16 R2: compute confirmed problem areas independent of the
    # catalog. A missing status is a direct admission; a non-missing status
    # with strong pain is a problem the operator confirmed via measurements
    # or affirmative notes.
    problems = _detect_problems(by_area)
    covered_areas: set[str] = set()
    for s in suggestions:
        for ac, _ in s.evidence:
            covered_areas.add(ac)
        # Also credit the improvement's primary and addressed areas.
        covered_areas.add(s.improvement.primary_area)
        covered_areas.update(s.improvement.addresses_area_codes)
    problems_without_match = tuple(
        p.area_code for p in problems if p.area_code not in covered_areas
    )

    return GapResult(
        suggestions=tuple(suggestions),
        to_clarify=to_clarify,
        not_answered=not_answered,
        verify_recommended=verify_recommended,
        not_applicable=tuple(not_applicable),
        problems=problems,
        problems_without_match=problems_without_match,
    )


def _detect_problems(by_area: Mapping[str, Mapping]) -> tuple[ProblemArea, ...]:
    """Return confirmed problem areas, independent of the catalog.

    See ``ProblemArea`` docstring for the detection contract. The function
    is deliberately conservative: it never invents a problem from status
    alone unless the status is ``missing`` (= operator explicitly admits the
    system does not exist). All measured-pain signals go through
    ``_strong_pain``, which (post-R1) requires quality<=2, time_loss>=60 or
    an affirmative problem note.
    """
    problems: list[ProblemArea] = []
    for code, f in sorted(by_area.items()):
        status = f.get("status")
        if status in (None, "unknown"):
            continue
        if status == "missing":
            # Direct admission; confidence depends on verification + notes.
            if f.get("verified") or _notes_signal_problem(f):
                conf = "high"
            elif f.get("quality") is not None or f.get("time_loss_min_per_day") is not None:
                conf = "medium"
            else:
                conf = "medium"  # a bare "missing" is still an operator admission
            problems.append(ProblemArea(
                area_code=code,
                reason=f"Bereich {code}: Status fehlt (vom Betrieb angegeben).",
                confidence=conf,
            ))
            continue
        if _strong_pain(f):
            # Measured pain on an existing/partial/manual area.
            quality = f.get("quality")
            time_loss = f.get("time_loss_min_per_day")
            notes_problem = _notes_signal_problem(f)
            parts = [f"Status: {status}"]
            if quality is not None and quality <= 2:
                parts.append(f"Qualität {quality}/5")
            if time_loss is not None and time_loss >= 60:
                parts.append(f"geschätzter Zeitverlust {time_loss} min/Tag")
            if notes_problem:
                parts.append("Problem in Notizen genannt")
            # Confidence: measured + verified = high; measured only = medium;
            # notes-only = low (operator claim, unverified).
            if f.get("verified"):
                conf = "high"
            elif quality is not None or time_loss is not None:
                conf = "medium"
            else:
                conf = "low"
            problems.append(ProblemArea(
                area_code=code,
                reason=f"Bereich {code}: " + "; ".join(parts),
                confidence=conf,
            ))
    return tuple(problems)


# -------- helpers for render-time context --------

def preserved_system_label(improvement: Improvement, by_area: Mapping) -> str:
    """Describe the restaurant's own primary system — never substitute MVP paths.

    Enforces Codex MISSION 13 D10: the preserved-systems text in the report
    must reflect the real restaurant tool from `current_tool`, with a
    neutral fallback that does NOT reference Klare KI MVP interfaces.
    """
    area_code = improvement.primary_area
    f = by_area.get(area_code)
    if not f:
        return "Noch zu klären"
    tool = (f.get("current_tool") or "").strip()
    if tool:
        return f"aktuell genutzt: {tool}"
    status = f.get("status")
    if status in ("available", "partial"):
        return "Vom Betrieb bestätigtes System — Name nicht erfasst"
    if status in ("manual", "missing"):
        return "Kein spezielles Werkzeug im Einsatz"
    return "Noch zu klären"


def selected_improvements_for(profile_selections: Iterable[Mapping]) -> tuple[Improvement, ...]:
    """Return catalog improvements for a profile's `selected=1` selection rows."""
    codes: list[str] = []
    for row in profile_selections:
        d = _finding_dict(row)
        if d.get("selected", 1):
            codes.append(d["improvement_code"])
    return tuple(IMPROVEMENT_BY_CODE[c] for c in codes if c in IMPROVEMENT_BY_CODE)
