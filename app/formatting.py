"""Shared Jinja2 filter functions. Imported by both main and blueprint."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

STATUS_DE = {
    "new":             "Neu – zu prüfen",
    "confirmed":       "Bestätigt",
    "in_kitchen":      "In Zubereitung",
    "ready":           "Fertig",
    "assigned":        "Fahrer zugewiesen",
    "en_route":        "Unterwegs",
    "delivered":       "Zugestellt",
    "closed":          "Abgeschlossen",
    "failed_delivery": "Zustellung fehlgeschlagen",
    "rejected":        "Abgelehnt",
    "cancelled":       "Abgebrochen",
}

STATUS_CLASS = {
    "new":             "status-badge--new",
    "confirmed":       "status-badge--confirmed",
    "in_kitchen":      "status-badge--in-kitchen",
    "ready":           "status-badge--ready",
    "assigned":        "status-badge--assigned",
    "en_route":        "status-badge--en-route",
    "delivered":       "status-badge--delivered",
    "closed":          "status-badge--closed",
    "failed_delivery": "status-badge--failed",
    "rejected":        "status-badge--rejected",
    "cancelled":       "status-badge--cancelled",
}

ROLE_DE = {
    "owner":     "Inhaber:in",
    "confirmer": "Konfirmierer:in",
    "kitchen":   "Küche",
    "courier":   "Fahrer:in",
}


def format_cents(cents: int) -> str:
    euros = cents // 100
    rest = cents % 100
    return f"{euros},{rest:02d} €"


def status_de(code: str) -> str:
    return STATUS_DE.get(code, code)


def status_class(code: str) -> str:
    return STATUS_CLASS.get(code, "status-badge--cancelled")


def role_de(code: str) -> str:
    return ROLE_DE.get(code, code)


def datetime_de(value: str) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace(" ", "T"))
    except (TypeError, ValueError):
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y %H:%M")


def time_de(value: str) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace(" ", "T"))
    except (TypeError, ValueError):
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo("Europe/Berlin")).strftime("%H:%M")


def register(templates) -> None:
    env = templates.env
    env.filters["cents"] = format_cents
    env.filters["status_de"] = status_de
    env.filters["status_class"] = status_class
    env.filters["role_de"] = role_de
    env.filters["datetime_de"] = datetime_de
    env.filters["time_de"] = time_de
