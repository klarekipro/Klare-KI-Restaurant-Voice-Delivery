"""Pure gap-analysis: given findings + catalog, produce suggestions.

Everything in here is deterministic and side-effect free — unit-testable
without a database.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .catalog import (
    AREA_BY_CODE,
    IMPROVEMENTS,
    IMPROVEMENT_BY_CODE,
    Improvement,
)

STATUS_PRIORITY: Mapping[str, str] = {
    "missing": "high",
    "manual":  "medium",
    "partial": "low",
}


@dataclass(frozen=True)
class Suggestion:
    improvement: Improvement
    priority: str                     # "high" | "medium" | "low"
    driver_areas: tuple[str, ...]     # area_codes that caused this suggestion
    verification_recommended: bool    # True wenn `available` aber `verified=0`


@dataclass(frozen=True)
class GapResult:
    suggestions: tuple[Suggestion, ...]
    to_clarify: tuple[str, ...]       # area_codes mit Status "unknown"
    verify_recommended: tuple[str, ...]  # area_codes "available" + verified=0


_PRIO_RANK = {"high": 0, "medium": 1, "low": 2}


def analyze(findings: Iterable[Mapping]) -> GapResult:
    """Build a GapResult from an iterable of findings (dict-like rows).

    Each row must expose: `area_code`, `status`, and (optionally) `verified`.
    """
    by_area: dict[str, dict] = {}
    for row in findings:
        code = row["area_code"]
        if code in AREA_BY_CODE:
            by_area[code] = {
                "status": row["status"],
                "verified": bool(row.get("verified") or 0) if hasattr(row, "get") else bool(row["verified"]),
            }

    to_clarify = tuple(
        code for code, f in sorted(by_area.items()) if f["status"] == "unknown"
    )
    verify_recommended = tuple(
        code for code, f in sorted(by_area.items())
        if f["status"] == "available" and not f["verified"]
    )

    # For each improvement, derive its priority from the WORST status among the
    # areas it addresses (missing beats manual beats partial beats available).
    suggestions: list[Suggestion] = []
    for improvement in IMPROVEMENTS:
        drivers: list[tuple[str, str]] = []  # (area_code, priority)
        for area_code in improvement.addresses_area_codes:
            finding = by_area.get(area_code)
            if not finding:
                continue
            prio = STATUS_PRIORITY.get(finding["status"])
            if prio:
                drivers.append((area_code, prio))
        if not drivers:
            continue
        top_prio = min(drivers, key=lambda d: _PRIO_RANK[d[1]])[1]
        suggestions.append(Suggestion(
            improvement=improvement,
            priority=top_prio,
            driver_areas=tuple(code for code, _ in drivers),
            verification_recommended=False,
        ))

    suggestions.sort(key=lambda s: (_PRIO_RANK[s.priority], s.improvement.code))
    return GapResult(
        suggestions=tuple(suggestions),
        to_clarify=to_clarify,
        verify_recommended=verify_recommended,
    )


def selected_improvements_for(profile_selections: Iterable[Mapping]) -> tuple[Improvement, ...]:
    """Return catalog improvements for a profile's `selected=1` selection rows."""
    codes = [row["improvement_code"] for row in profile_selections
             if (row["selected"] if not hasattr(row, "get") else row.get("selected", 1))]
    return tuple(IMPROVEMENT_BY_CODE[c] for c in codes if c in IMPROVEMENT_BY_CODE)
