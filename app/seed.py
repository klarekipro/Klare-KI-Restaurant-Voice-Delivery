"""Seed demo data (users, menu, one repeat customer).

Demo credentials are intentionally weak and are listed only in the README for
local evaluation. They must not be reused in any production-adjacent setting.
"""
from __future__ import annotations

from . import auth, db

DEMO_USERS = [
    ("owner",      "Olivia Owner",    "owner",     "owner123"),
    ("confirmer",  "Carla Confirmer", "confirmer", "confirmer123"),
    ("kitchen",    "Konrad Kitchen",  "kitchen",   "kitchen123"),
    ("courier1",   "Carlo Courier",   "courier",   "courier123"),
    ("courier2",   "Caro Courier",    "courier",   "courier123"),
]

DEMO_MENU = [
    ("Pizza Margherita",         "Tomatensauce, Mozzarella, Basilikum",             990),
    ("Pizza Salami",             "Tomatensauce, Mozzarella, Salami",                1190),
    ("Pizza Funghi",             "Tomatensauce, Mozzarella, Champignons",           1090),
    ("Döner Teller",             "Fleisch nach Wahl, Salat, Pommes, Soße",          1250),
    ("Lahmacun",                 "Türkische Pizza mit Hackfleisch",                 650),
    ("Pasta Bolognese",          "Rindfleisch, Tomate, Parmesan",                   1150),
    ("Caesar Salat",             "Römersalat, Hähnchen, Croutons, Dressing",         990),
    ("Tiramisu",                 "Hausgemacht",                                     550),
    ("Cola 0,33L",               "",                                                 290),
    ("Mineralwasser 0,5L",       "",                                                 250),
]

DEMO_REPEAT_CUSTOMER = {
    "phone": "+49301234567",
    "name": "Thomas Müller",
    "street": "Hauptstraße",
    "house_number": "12a",
    "plz": "10115",
    "city": "Berlin",
    "notes": "2. Stock, Klingel Müller",
    "trusted": 1,
    "opt_out_crm": 0,
}


def run(verbose: bool = False) -> None:
    db.init_db()
    conn = db.connect()
    try:
        for username, display, role, password in DEMO_USERS:
            exists = conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO users (username, display_name, role, password_hash) "
                "VALUES (?, ?, ?, ?)",
                (username, display, role, auth.hash_password(password)),
            )
            if verbose:
                print(f"user: {username}/{role}")

        for name, description, price in DEMO_MENU:
            exists = conn.execute(
                "SELECT 1 FROM menu_items WHERE name = ?", (name,)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO menu_items (name, description, price_cents) "
                "VALUES (?, ?, ?)",
                (name, description, price),
            )
            if verbose:
                print(f"menu: {name} {price/100:.2f}€")

        c = DEMO_REPEAT_CUSTOMER
        exists = conn.execute(
            "SELECT 1 FROM customers WHERE phone = ?", (c["phone"],)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO customers "
                "(phone, name, street, house_number, plz, city, notes, trusted, opt_out_crm) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (c["phone"], c["name"], c["street"], c["house_number"], c["plz"],
                 c["city"], c["notes"], c["trusted"], c["opt_out_crm"]),
            )
            if verbose:
                print(f"customer: {c['phone']} {c['name']}")
    finally:
        conn.close()


if __name__ == "__main__":
    run(verbose=True)
