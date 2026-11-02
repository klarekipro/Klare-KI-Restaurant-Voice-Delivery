"""SQLite connection helper and schema initialization.

The DB path is configurable via the KLARE_DB_PATH environment variable so that
tests can use an isolated file-based database without touching the dev DB.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
 request_key TEXT NOT NULL, actor INTEGER NOT NULL, digest TEXT NOT NULL, result TEXT NOT NULL,
 PRIMARY KEY(request_key, actor)
);
CREATE TABLE IF NOT EXISTS order_contacts (
 order_id INTEGER PRIMARY KEY REFERENCES orders(id), phone TEXT, name TEXT, street TEXT,
 house_number TEXT, plz TEXT, city TEXT, notes TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    display_name  TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK(role IN ('owner','confirmer','kitchen','courier')),
    password_hash BLOB    NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS customers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    phone         TEXT    NOT NULL UNIQUE,
    name          TEXT    NOT NULL,
    street        TEXT    NOT NULL,
    house_number  TEXT    NOT NULL,
    plz           TEXT    NOT NULL,
    city          TEXT    NOT NULL,
    notes         TEXT    NOT NULL DEFAULT '',
    trusted       INTEGER NOT NULL DEFAULT 0,
    opt_out_crm   INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);

CREATE TABLE IF NOT EXISTS menu_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    description   TEXT    NOT NULL DEFAULT '',
    price_cents   INTEGER NOT NULL CHECK(price_cents >= 0),
    available     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id          INTEGER REFERENCES customers(id),
    status               TEXT    NOT NULL CHECK(status IN
                                 ('new','confirmed','in_kitchen','ready',
                                  'assigned','en_route','delivered','closed',
                                  'rejected','cancelled','failed_delivery')),
    total_cents          INTEGER NOT NULL DEFAULT 0,
    source               TEXT    NOT NULL DEFAULT 'voice',
    call_id              TEXT,
    call_language        TEXT    NOT NULL DEFAULT 'de-DE',
    recording_stored     INTEGER NOT NULL DEFAULT 0,
    disclosure_at        TEXT,
    confirmer_user_id    INTEGER REFERENCES users(id),
    assigned_courier_id  INTEGER REFERENCES users(id),
    reject_reason        TEXT,
    delivery_notes       TEXT    NOT NULL DEFAULT '',
    created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    confirmed_at         TEXT,
    ready_at             TEXT,
    assigned_at          TEXT,
    en_route_at          TEXT,
    delivered_at         TEXT,
    closed_at            TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_courier ON orders(assigned_courier_id);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

CREATE TABLE IF NOT EXISTS order_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id       INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id   INTEGER NOT NULL REFERENCES menu_items(id),
    name_snapshot  TEXT    NOT NULL,
    qty            INTEGER NOT NULL CHECK(qty > 0),
    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
    modifiers      TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);

CREATE TABLE IF NOT EXISTS order_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    event      TEXT    NOT NULL,
    actor_user_id INTEGER REFERENCES users(id),
    detail     TEXT    NOT NULL DEFAULT '',
    occurred_at TEXT   NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_order_events_order ON order_events(order_id);

CREATE TABLE IF NOT EXISTS access_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id),
    action     TEXT    NOT NULL,
    object_type TEXT   NOT NULL,
    object_id  TEXT,
    reason     TEXT    NOT NULL DEFAULT '',
    occurred_at TEXT   NOT NULL DEFAULT (datetime('now'))
);

-- MISSION 12: Blueprint diagnostic/proposal tables (addition, no migration).
CREATE TABLE IF NOT EXISTS diagnostic_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_name TEXT    NOT NULL,
    city            TEXT    NOT NULL DEFAULT '',
    cuisine         TEXT    NOT NULL DEFAULT '',
    locations_count INTEGER NOT NULL DEFAULT 1 CHECK(locations_count >= 1),
    contact_person  TEXT    NOT NULL DEFAULT '',
    contact_role    TEXT    NOT NULL DEFAULT '',
    status          TEXT    NOT NULL DEFAULT 'draft'
                     CHECK(status IN ('draft','review','shared')),
    catalog_version TEXT    NOT NULL,
    created_by      INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_diagnostic_profiles_created_by
    ON diagnostic_profiles(created_by);

CREATE TABLE IF NOT EXISTS diagnostic_findings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id    INTEGER NOT NULL REFERENCES diagnostic_profiles(id) ON DELETE CASCADE,
    area_code     TEXT    NOT NULL,
    status        TEXT    NOT NULL
                   CHECK(status IN ('available','partial','manual','missing','unknown')),
    current_tool  TEXT    NOT NULL DEFAULT '',
    quality       INTEGER CHECK(quality IS NULL OR quality BETWEEN 1 AND 5),
    automation    INTEGER CHECK(automation IS NULL OR automation BETWEEN 1 AND 5),
    time_loss_min_per_day INTEGER
                   CHECK(time_loss_min_per_day IS NULL OR time_loss_min_per_day >= 0),
    verified      INTEGER NOT NULL DEFAULT 0 CHECK(verified IN (0,1)),
    notes         TEXT    NOT NULL DEFAULT '',
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (profile_id, area_code)
);

CREATE INDEX IF NOT EXISTS idx_diagnostic_findings_profile
    ON diagnostic_findings(profile_id);

CREATE TABLE IF NOT EXISTS diagnostic_selections (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id        INTEGER NOT NULL REFERENCES diagnostic_profiles(id) ON DELETE CASCADE,
    improvement_code  TEXT    NOT NULL,
    selected          INTEGER NOT NULL DEFAULT 1 CHECK(selected IN (0,1)),
    priority          TEXT    NOT NULL DEFAULT 'medium'
                       CHECK(priority IN ('low','medium','high')),
    -- MISSION 14 D05: distinguish engine-suggested priority from a sales
    -- override. The selection route writes `priority_source='manual'` ONLY
    -- for the box the user actually ticked or whose priority dropdown was
    -- changed. Rows that would carry an engine-generated priority are
    -- not persisted here any more.
    priority_source   TEXT    NOT NULL DEFAULT 'manual'
                       CHECK(priority_source IN ('manual','auto')),
    notes             TEXT    NOT NULL DEFAULT '',
    UNIQUE (profile_id, improvement_code)
);

CREATE INDEX IF NOT EXISTS idx_diagnostic_selections_profile
    ON diagnostic_selections(profile_id);
"""


def db_path() -> Path:
    env = os.environ.get("KLARE_DB_PATH")
    if env:
        return Path(env)
    root = Path(__file__).resolve().parent.parent
    data = root / "data"
    data.mkdir(exist_ok=True)
    return data / "mvp.sqlite"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _ensure_selections_priority_source(conn: sqlite3.Connection) -> None:
    """MISSION 14 D05: additive migration for existing DBs."""
    cols = {r["name"] for r in conn.execute(
        "PRAGMA table_info(diagnostic_selections)"
    ).fetchall()}
    if "priority_source" not in cols:
        conn.execute(
            "ALTER TABLE diagnostic_selections "
            "ADD COLUMN priority_source TEXT NOT NULL DEFAULT 'manual'"
        )


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        _ensure_selections_priority_source(conn)
        conn.execute("INSERT OR IGNORE INTO order_contacts SELECT o.id,c.phone,c.name,c.street,c.house_number,c.plz,c.city,c.notes FROM orders o JOIN customers c ON c.id=o.customer_id")
    finally:
        conn.close()


def iter_rows(cur: sqlite3.Cursor) -> Iterator[sqlite3.Row]:
    while True:
        row = cur.fetchone()
        if row is None:
            break
        yield row
