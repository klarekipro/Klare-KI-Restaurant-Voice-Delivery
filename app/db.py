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


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.execute("INSERT OR IGNORE INTO order_contacts SELECT o.id,c.phone,c.name,c.street,c.house_number,c.plz,c.city,c.notes FROM orders o JOIN customers c ON c.id=o.customer_id")
    finally:
        conn.close()


def iter_rows(cur: sqlite3.Cursor) -> Iterator[sqlite3.Row]:
    while True:
        row = cur.fetchone()
        if row is None:
            break
        yield row
