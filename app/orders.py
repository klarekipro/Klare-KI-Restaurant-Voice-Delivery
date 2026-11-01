"""Order state machine and domain operations."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from . import db

# State transition table — mirrors design/ux.md §4 and design/architecture.md §4.
TRANSITIONS = {
    "new":         {"confirmed", "rejected", "cancelled"},
    "confirmed":   {"in_kitchen", "ready", "cancelled"},
    "in_kitchen":  {"ready", "cancelled"},
    "ready":       {"assigned"},
    "assigned":    {"en_route", "ready"},
    "en_route":    {"delivered", "failed_delivery"},
    "delivered":   {"closed"},
    "failed_delivery": {"assigned", "cancelled", "closed"},
    "closed":      set(),
    "rejected":    set(),
    "cancelled":   set(),
}


class StateError(Exception):
    pass


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat(" ")


def log_event(conn, order_id: int, event: str,
              actor_user_id: Optional[int] = None, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO order_events (order_id, event, actor_user_id, detail) "
        "VALUES (?, ?, ?, ?)",
        (order_id, event, actor_user_id, detail),
    )


def transition(conn, order_id: int, next_state: str,
               actor_user_id: Optional[int] = None, detail: str = "") -> None:
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
        try:
            transition(conn, order_id, next_state, actor_user_id, detail)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return
    row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        raise StateError(f"order {order_id} not found")
    cur = row["status"]
    if next_state not in TRANSITIONS.get(cur, set()):
        raise StateError(f"cannot transition {cur} -> {next_state}")

    stamp_column = {
        "confirmed":        "confirmed_at",
        "ready":            "ready_at",
        "assigned":         "assigned_at",
        "en_route":         "en_route_at",
        "delivered":        "delivered_at",
        "closed":           "closed_at",
    }.get(next_state)

    now = _now()
    if stamp_column:
        conn.execute(
            f"UPDATE orders SET status = ?, {stamp_column} = ? WHERE id = ?",
            (next_state, now, order_id),
        )
    else:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (next_state, order_id))
    log_event(conn, order_id, f"status.{next_state}", actor_user_id, detail)


def recalc_total(conn, order_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(qty * unit_price_cents), 0) AS t "
        "FROM order_items WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    total = int(row["t"] or 0)
    conn.execute("UPDATE orders SET total_cents = ? WHERE id = ?", (total, order_id))
    return total


def fetch_order(order_id: int) -> Optional[dict]:
    conn = db.connect()
    try:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            return None
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ? ORDER BY id",
            (order_id,),
        ).fetchall()
        customer = None
        if order["customer_id"]:
            customer = conn.execute(
                "SELECT * FROM order_contacts WHERE order_id = ?",
                (order_id,),
            ).fetchone()
        events = conn.execute(
            "SELECT * FROM order_events WHERE order_id = ? ORDER BY id",
            (order_id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "order": dict(order),
        "items": [dict(i) for i in items],
        "customer": dict(customer) if customer else None,
        "events": [dict(e) for e in events],
    }
