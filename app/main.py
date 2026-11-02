"""FastAPI entry point: routes for all MVP flows."""
from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import hashlib
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import auth, db, orders, seed
from .blueprint import router as blueprint_router
from .voice.simulator import SimulatorVoiceProvider

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
STATIC_DIR = BASE_DIR / "static"

VOICE = SimulatorVoiceProvider()

def session_secret():
    configured = os.environ.get("KLARE_SESSION_SECRET")
    if configured:
        return configured
    path = db.db_path().with_suffix(".session-secret")
    try:
        with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as f:
            f.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return path.read_text().strip()


def report_window(days=1):
    """Return (start, end) UTC-ISO strings for a window of exactly `days` days
    ending at the next local midnight (inclusive of today).

    For `days=1` → heute [00:00, morgen 00:00). For `days=7` → letzte 7 Tage
    (6 vorhergehende Tage + heute).
    """
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    start = datetime.combine(today - timedelta(days=days - 1),
                             datetime.min.time(), ZoneInfo("Europe/Berlin"))
    end = datetime.combine(today + timedelta(days=1),
                           datetime.min.time(), ZoneInfo("Europe/Berlin"))
    return tuple(t.astimezone(timezone.utc).replace(tzinfo=None).isoformat(" ") for t in (start, end))


def _format_cents(cents: int) -> str:
    euros = cents // 100
    rest = cents % 100
    return f"{euros},{rest:02d} €"


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


def _status_de(code: str) -> str:
    return STATUS_DE.get(code, code)


def _status_class(code: str) -> str:
    return STATUS_CLASS.get(code, "status-badge--cancelled")


ROLE_DE = {
    "owner": "Inhaber:in",
    "confirmer": "Konfirmierer:in",
    "kitchen": "Küche",
    "courier": "Fahrer:in",
}


def _role_de(code: str) -> str:
    return ROLE_DE.get(code, code)


def _datetime_de(value: str) -> str:
    """Render a stored UTC-ISO timestamp as DD.MM.YYYY HH:MM in Europe/Berlin."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace(" ", "T"))
    except (TypeError, ValueError):
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(ZoneInfo("Europe/Berlin"))
    return local.strftime("%d.%m.%Y %H:%M")


def _time_de(value: str) -> str:
    """Short HH:MM form of a stored timestamp in Europe/Berlin."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace(" ", "T"))
    except (TypeError, ValueError):
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo("Europe/Berlin")).strftime("%H:%M")


TEMPLATES.env.filters["cents"] = _format_cents
TEMPLATES.env.filters["status_de"] = _status_de
TEMPLATES.env.filters["status_class"] = _status_class
TEMPLATES.env.filters["role_de"] = _role_de
TEMPLATES.env.filters["datetime_de"] = _datetime_de
TEMPLATES.env.filters["time_de"] = _time_de


def create_app() -> FastAPI:
    app = FastAPI(title="Klare KI Restaurant MVP", version="0.1.0")
    app.add_middleware(SessionMiddleware, secret_key=session_secret(), max_age=60 * 60 * 12)
    @app.middleware("http")
    async def local_boundary(request, call_next):
        # Reject cross-origin browser writes (including login CSRF).
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if (origin and origin != str(request.base_url).rstrip("/")) or request.headers.get("sec-fetch-site") == "cross-site":
                return Response("Schreibzugriff von fremder Herkunft verweigert.", status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    db.init_db()
    # Seed is idempotent, safe at startup.
    seed.run()
    app.include_router(blueprint_router)

    def _wants_json(request: Request) -> bool:
        accept = request.headers.get("accept", "")
        return "application/json" in accept or request.url.path.startswith("/call/") \
            or request.url.path.endswith("/reveal_phone")

    def _render_error(request: Request, code: int, title: str, message: str,
                      detail: str = "", cta_href: str = "/", cta_label: str = "Zur Startseite"):
        if _wants_json(request):
            return Response(content=detail or message, status_code=code,
                            media_type="text/plain; charset=utf-8")
        return TEMPLATES.TemplateResponse(
            request, "error.html",
            ctx(request, title=title, message=message, detail=detail,
                cta_href=cta_href, cta_label=cta_label),
            status_code=code,
        )

    @app.exception_handler(orders.StateError)
    def _state_error(request: Request, exc: orders.StateError):
        return _render_error(
            request, 409,
            "Statuswechsel nicht möglich",
            "Die Bestellung ist nicht mehr in dem erwarteten Status. "
            "Bitte laden Sie die Seite neu.",
            detail=str(exc),
        )

    @app.exception_handler(sqlite3.IntegrityError)
    def integrity_error(request, exc):
        return _render_error(
            request, 409,
            "Daten-Konflikt",
            "Die Angaben sind unvollständig oder widersprechen bereits gespeicherten Daten.",
        )

    @app.exception_handler(StarletteHTTPException)
    def http_exception(request: Request, exc: StarletteHTTPException):
        code = exc.status_code
        detail = str(exc.detail) if exc.detail else ""
        if code == 401:
            if _wants_json(request):
                return Response("Anmeldung erforderlich.", status_code=401)
            return RedirectResponse("/login", status_code=303)
        if code == 403:
            return _render_error(
                request, 403, "Kein Zugriff",
                "Für diesen Bereich fehlt Ihnen die Berechtigung. "
                "Bitte wenden Sie sich an die Inhaberin oder den Inhaber.",
                cta_href="/", cta_label="Zurück zur Übersicht",
            )
        if code == 404:
            return _render_error(
                request, 404, "Seite nicht gefunden",
                "Die aufgerufene Adresse existiert nicht oder wurde verschoben.",
                detail=detail,
            )
        if code == 400:
            return _render_error(
                request, 400, "Ungültige Eingabe",
                "Die Eingabe konnte nicht verarbeitet werden.",
                detail=detail,
            )
        return _render_error(request, code, "Fehler",
                             "Ein Fehler ist aufgetreten.", detail=detail)

    @app.exception_handler(RequestValidationError)
    def validation_error(request: Request, exc: RequestValidationError):
        return _render_error(
            request, 400, "Ungültige Eingabe",
            "Bitte prüfen Sie die eingegebenen Daten.",
            detail="Formularvalidierung fehlgeschlagen.",
        )

    def ctx(request: Request, **extra) -> dict:
        base = {
            "request": request,
            "user": auth.current_user(request),
        }
        base.update(extra)
        return base

    # ---------- auth ----------

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        user = auth.current_user(request)
        if not user:
            return RedirectResponse("/login", status_code=303)
        return RedirectResponse(_home_for(user.role), status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        return TEMPLATES.TemplateResponse(request, "login.html", ctx(request, error=None))

    @app.post("/login", response_class=HTMLResponse)
    def login_submit(request: Request,
                     username: str = Form(...),
                     password: str = Form(...)):
        user = auth.login(username, password)
        if not user:
            return TEMPLATES.TemplateResponse(request, "login.html", ctx(request, error="Login fehlgeschlagen."),
                status_code=400,
            )
        request.session.clear()
        request.session["uid"] = user.id
        return RedirectResponse(_home_for(user.role), status_code=303)

    @app.post("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    # ---------- menu ----------

    @app.get("/menu", response_class=HTMLResponse)
    def menu_page(request: Request,
                  user: auth.User = Depends(auth.require_strict("owner", "confirmer", "kitchen"))):
        conn = db.connect()
        try:
            items = conn.execute(
                "SELECT * FROM menu_items ORDER BY name"
            ).fetchall()
        finally:
            conn.close()
        return TEMPLATES.TemplateResponse(request, "menu.html", ctx(request, items=items, can_edit=user.is_owner()),
        )

    @app.post("/menu/new")
    def menu_create(request: Request,
                    name: str = Form(...),
                    description: str = Form(""),
                    price_eur: str = Form(...),
                    user: auth.User = Depends(auth.require_strict("owner"))):
        if not name.strip() or len(name) > 120:
            raise HTTPException(400, "Ungültiger Positionsname.")
        price_cents = _parse_price(price_eur)
        conn = db.connect()
        try:
            conn.execute(
                "INSERT INTO menu_items (name, description, price_cents) VALUES (?, ?, ?)",
                (name.strip(), description.strip(), price_cents),
            )
        finally:
            conn.close()
        return RedirectResponse("/menu", status_code=303)

    @app.post("/menu/{item_id}/toggle")
    def menu_toggle(request: Request, item_id: int,
                    user: auth.User = Depends(auth.require_strict("owner"))):
        conn = db.connect()
        try:
            conn.execute(
                "UPDATE menu_items SET available = 1 - available WHERE id = ?",
                (item_id,),
            )
        finally:
            conn.close()
        return RedirectResponse("/menu", status_code=303)

    # ---------- customers ----------

    @app.get("/customers", response_class=HTMLResponse)
    def customers_page(request: Request,
                       user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        conn = db.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM customers ORDER BY name"
            ).fetchall()
        finally:
            conn.close()
        return TEMPLATES.TemplateResponse(request, "customers.html", ctx(request, customers=rows),
        )

    @app.post("/customers/{cid}/edit")
    def customers_edit(request: Request, cid: int,
                       name: str = Form(...),
                       street: str = Form(...),
                       house_number: str = Form(...),
                       plz: str = Form(...),
                       city: str = Form(...),
                       notes: str = Form(""),
                       user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        name_v = name.strip()
        street_v = street.strip()
        house_v = house_number.strip()
        plz_v = plz.strip()
        city_v = city.strip()
        if not name_v or not street_v or not house_v or not city_v:
            raise HTTPException(400, "Name, Straße, Hausnummer und Ort sind Pflichtfelder.")
        if not re.fullmatch(r"\d{5}", plz_v):
            raise HTTPException(400, "PLZ muss aus 5 Ziffern bestehen.")
        if len(name_v) > 120 or len(street_v) > 120 or len(city_v) > 80 \
                or len(house_v) > 20 or len(notes.strip()) > 400:
            raise HTTPException(400, "Eingabefeld überschreitet die zulässige Länge.")
        conn = db.connect()
        try:
            conn.execute(
                "UPDATE customers SET name=?, street=?, house_number=?, plz=?, "
                "city=?, notes=?, updated_at=datetime('now') WHERE id=?",
                (name_v, street_v, house_v, plz_v, city_v, notes.strip(), cid),
            )
        finally:
            conn.close()
        return RedirectResponse("/customers?flash=saved", status_code=303)

    # ---------- call simulator (voice entry point) ----------

    @app.get("/call", response_class=HTMLResponse)
    def call_page(request: Request,
                  user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        conn = db.connect()
        try:
            menu = conn.execute(
                "SELECT id, name, price_cents FROM menu_items "
                "WHERE available = 1 ORDER BY name"
            ).fetchall()
        finally:
            conn.close()
        return TEMPLATES.TemplateResponse(request, "call_simulator.html", ctx(request, menu=menu, disclosure=_disclosure_de()),
        )

    @app.post("/call/lookup")
    def call_lookup(request: Request,
                    phone: str = Form(...),
                    user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        phone = _normalize_phone(phone)
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT * FROM customers WHERE phone = ?", (phone,)
            ).fetchone()
        finally:
            conn.close()
        if row:
            return {
                "matched": True,
                "customer": {
                    "id": row["id"],
                    "name": row["name"],
                    "street": row["street"],
                    "house_number": row["house_number"],
                    "plz": row["plz"],
                    "city": row["city"],
                    "notes": row["notes"],
                    "trusted": bool(row["trusted"]),
                    "opt_out_crm": bool(row["opt_out_crm"]),
                },
            }
        return {"matched": False, "customer": None}

    @app.post("/call/submit")
    async def call_submit(request: Request,
                          user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        try:
            payload = await request.json()
        except ValueError:
            raise HTTPException(400, "Ungültiges JSON-Format.")
        if not isinstance(payload, dict):
            raise HTTPException(400, "Erwartet wird ein JSON-Objekt.")
        return _submit_call_payload(payload, actor_user_id=user.id, request_key=request.headers.get("Idempotency-Key"))

    # ---------- confirmer ----------

    @app.get("/confirmer", response_class=HTMLResponse)
    def confirmer_queue(request: Request,
                        user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        conn = db.connect()
        try:
            rows = conn.execute(
                "SELECT o.id, o.status, o.total_cents, o.created_at, "
                "       c.name AS customer_name, c.phone AS customer_phone "
                "FROM orders o LEFT JOIN order_contacts c ON o.id = c.order_id "
                "WHERE o.status IN ('new','confirmed','in_kitchen','ready') "
                "ORDER BY o.created_at DESC"
            ).fetchall()
        finally:
            conn.close()
        return TEMPLATES.TemplateResponse(request, "confirmer_queue.html", ctx(request, orders=rows),
        )

    @app.get("/confirmer/{order_id}", response_class=HTMLResponse)
    def confirmer_review(request: Request, order_id: int,
                         user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        bundle = orders.fetch_order(order_id)
        if not bundle:
            raise HTTPException(404, "Bestellung nicht gefunden.")
        conn = db.connect()
        try:
            menu = conn.execute(
                "SELECT id, name, price_cents FROM menu_items "
                "WHERE available = 1 ORDER BY name"
            ).fetchall()
        finally:
            conn.close()
        return TEMPLATES.TemplateResponse(request, "confirmer_review.html", ctx(request, bundle=bundle, menu=menu),
        )

    @app.post("/confirmer/{order_id}/approve")
    def confirmer_approve(request: Request, order_id: int,
                          user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM order_items WHERE order_id=?", (order_id,)).fetchone():
                raise HTTPException(400, "Eine leere Bestellung kann nicht bestätigt werden.")
            orders.transition(conn, order_id, "confirmed", actor_user_id=user.id)
            conn.execute(
                "UPDATE orders SET confirmer_user_id = ? WHERE id = ?",
                (user.id, order_id),
            )
            # Promote the customer to trusted on first successful confirm.
            row = conn.execute(
                "SELECT customer_id FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if row and row["customer_id"]:
                conn.execute(
                    "UPDATE customers SET trusted = 1, updated_at = datetime('now') "
                    "WHERE id = ?",
                    (row["customer_id"],),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return RedirectResponse("/confirmer?flash=approved", status_code=303)

    @app.post("/confirmer/{order_id}/reject")
    def confirmer_reject(request: Request, order_id: int,
                         reason: str = Form(...),
                         user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        reason_v = reason.strip()
        if not reason_v:
            raise HTTPException(400, "Grund für die Ablehnung ist erforderlich.")
        if len(reason_v) > 400:
            raise HTTPException(400, "Grund ist zu lang (max. 400 Zeichen).")
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE orders SET reject_reason = ? WHERE id = ?",
                (reason_v, order_id),
            )
            orders.transition(conn, order_id, "rejected",
                              actor_user_id=user.id, detail=reason_v)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return RedirectResponse("/confirmer?flash=rejected", status_code=303)

    @app.post("/confirmer/{order_id}/edit_item")
    def confirmer_edit_item(request: Request, order_id: int,
                            item_id: int = Form(...),
                            qty: int = Form(...),
                            user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        if not 0 <= qty <= 100:
            raise HTTPException(400, "Menge muss ≥ 0 sein.")
        _require_state(order_id, "new")
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()["status"] != "new":
                raise HTTPException(409, "Diese Bestellung kann nicht mehr bearbeitet werden.")
            if qty == 0:
                conn.execute(
                    "DELETE FROM order_items WHERE id = ? AND order_id = ?",
                    (item_id, order_id),
                )
            else:
                conn.execute(
                    "UPDATE order_items SET qty = ? WHERE id = ? AND order_id = ?",
                    (qty, item_id, order_id),
                )
            orders.recalc_total(conn, order_id)
            orders.log_event(conn, order_id, "item.edited", user.id,
                             f"item_id={item_id} qty={qty}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return RedirectResponse(f"/confirmer/{order_id}", status_code=303)

    @app.post("/confirmer/{order_id}/add_item")
    def confirmer_add_item(request: Request, order_id: int,
                           menu_item_id: int = Form(...),
                           qty: int = Form(1),
                           user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        if not 1 <= qty <= 100:
            raise HTTPException(400, "Menge muss ≥ 1 sein.")
        _require_state(order_id, "new")
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT id, name, price_cents FROM menu_items WHERE id = ? AND available = 1",
                (menu_item_id,),
            ).fetchone()
            if not row:
                raise HTTPException(400, "Position unbekannt oder nicht verfügbar.")
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()["status"] != "new":
                raise HTTPException(409, "Diese Bestellung kann nicht mehr bearbeitet werden.")
            conn.execute(
                "INSERT INTO order_items "
                "(order_id, menu_item_id, name_snapshot, qty, unit_price_cents) "
                "VALUES (?, ?, ?, ?, ?)",
                (order_id, row["id"], row["name"], qty, row["price_cents"]),
            )
            orders.recalc_total(conn, order_id)
            orders.log_event(conn, order_id, "item.added", user.id,
                             f"menu_item_id={row['id']} qty={qty}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return RedirectResponse(f"/confirmer/{order_id}", status_code=303)

    # ---------- kitchen ----------

    @app.get("/kitchen", response_class=HTMLResponse)
    def kitchen_page(request: Request,
                     user: auth.User = Depends(auth.require_strict("owner", "kitchen"))):
        conn = db.connect()
        try:
            rows = conn.execute(
                "SELECT o.id, o.status, o.confirmed_at, o.ready_at, "
                "       o.created_at "
                "FROM orders o "
                "WHERE o.status IN ('confirmed','in_kitchen') "
                "ORDER BY o.confirmed_at ASC"
            ).fetchall()
            # fetch items for each
            items_by_order = {}
            for r in rows:
                items = conn.execute(
                    "SELECT name_snapshot, qty, modifiers FROM order_items "
                    "WHERE order_id = ? ORDER BY id",
                    (r["id"],),
                ).fetchall()
                items_by_order[r["id"]] = items
            ready = conn.execute(
                "SELECT id, ready_at FROM orders WHERE status = 'ready' "
                "ORDER BY ready_at ASC"
            ).fetchall()
        finally:
            conn.close()
        return TEMPLATES.TemplateResponse(request, "kitchen.html", ctx(request, orders=rows, items_by_order=items_by_order, ready=ready),
        )

    @app.post("/kitchen/{order_id}/start")
    def kitchen_start(request: Request, order_id: int,
                      user: auth.User = Depends(auth.require_strict("owner", "kitchen"))):
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                raise HTTPException(404, "Bestellung nicht gefunden.")
            if row["status"] != "in_kitchen":
                orders.transition(conn, order_id, "in_kitchen", actor_user_id=user.id)
            conn.execute("COMMIT")
        except Exception:
            try: conn.execute("ROLLBACK")
            except Exception: pass
            raise
        finally:
            conn.close()
        return RedirectResponse("/kitchen?flash=start", status_code=303)

    @app.post("/kitchen/{order_id}/ready")
    def kitchen_ready(request: Request, order_id: int,
                      user: auth.User = Depends(auth.require_strict("owner", "kitchen"))):
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                raise HTTPException(404, "Bestellung nicht gefunden.")
            current = row["status"]
            if current == "ready":
                conn.execute("COMMIT")
            else:
                if current == "confirmed":
                    orders.transition(conn, order_id, "in_kitchen", actor_user_id=user.id)
                orders.transition(conn, order_id, "ready", actor_user_id=user.id)
                conn.execute("COMMIT")
        except Exception:
            try: conn.execute("ROLLBACK")
            except Exception: pass
            raise
        finally:
            conn.close()
        return RedirectResponse("/kitchen?flash=ready", status_code=303)

    # ---------- courier dispatch + mobile ----------

    @app.get("/dispatch", response_class=HTMLResponse)
    def dispatch_page(request: Request,
                      user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        conn = db.connect()
        try:
            ready = conn.execute(
                "SELECT o.*, c.name AS customer_name, c.street, c.house_number, c.plz, c.city "
                "FROM orders o LEFT JOIN order_contacts c ON o.id = c.order_id "
                "WHERE o.status = 'ready' ORDER BY o.ready_at ASC"
            ).fetchall()
            couriers = conn.execute(
                "SELECT id, display_name FROM users WHERE role = 'courier' AND active = 1 "
                "ORDER BY display_name"
            ).fetchall()
        finally:
            conn.close()
        return TEMPLATES.TemplateResponse(request, "dispatch.html", ctx(request, ready=ready, couriers=couriers),
        )

    @app.post("/dispatch/{order_id}/assign")
    def dispatch_assign(request: Request, order_id: int,
                        courier_id: int = Form(...),
                        user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            crow = conn.execute(
                "SELECT id FROM users WHERE id = ? AND role = 'courier' AND active = 1",
                (courier_id,),
            ).fetchone()
            if not crow:
                raise HTTPException(400, "Fahrer unbekannt.")
            conn.execute(
                "UPDATE orders SET assigned_courier_id = ? WHERE id = ?",
                (courier_id, order_id),
            )
            orders.transition(conn, order_id, "assigned",
                              actor_user_id=user.id, detail=f"courier={courier_id}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return RedirectResponse("/dispatch?flash=assigned", status_code=303)

    @app.get("/courier", response_class=HTMLResponse)
    def courier_page(request: Request,
                     user: auth.User = Depends(auth.require_strict("owner", "courier"))):
        conn = db.connect()
        try:
            rows = conn.execute(
                "SELECT o.*, c.name AS customer_first_name, c.street, c.house_number, "
                "       c.plz, c.city, c.notes AS delivery_notes "
                "FROM orders o LEFT JOIN order_contacts c ON o.id = c.order_id "
                "WHERE o.assigned_courier_id = ? AND o.status IN ('assigned','en_route') "
                "ORDER BY o.assigned_at ASC",
                (user.id,),
            ).fetchall()
            start, end = report_window()
            done = conn.execute(
                "SELECT o.id, o.delivered_at, o.total_cents "
                "FROM orders o "
                "WHERE o.assigned_courier_id = ? "
                "  AND o.status IN ('delivered','closed') "
                "  AND o.delivered_at >= ? AND o.delivered_at < ? "
                "ORDER BY o.delivered_at DESC",
                (user.id, start, end),
            ).fetchall()
        finally:
            conn.close()
        return TEMPLATES.TemplateResponse(request, "courier_assignments.html", ctx(request, orders=rows, done=done),
        )

    @app.get("/courier/{order_id}", response_class=HTMLResponse)
    def courier_delivery(request: Request, order_id: int,
                         user: auth.User = Depends(auth.require_strict("owner", "courier"))):
        bundle = orders.fetch_order(order_id)
        if not bundle:
            raise HTTPException(404, "Bestellung nicht gefunden.")
        if not user.is_owner() and bundle["order"]["assigned_courier_id"] != user.id:
            raise HTTPException(403, "Diese Bestellung ist nicht Ihnen zugewiesen.")
        nav_url = None
        if bundle["customer"]:
            addr = (
                f"{bundle['customer']['street']} {bundle['customer']['house_number']}, "
                f"{bundle['customer']['plz']} {bundle['customer']['city']}, Deutschland"
            )
            nav_url = f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(addr)}"
        return TEMPLATES.TemplateResponse(request, "courier_delivery.html", ctx(request, bundle=bundle, nav_url=nav_url),
        )

    @app.post("/courier/{order_id}/start")
    def courier_start(request: Request, order_id: int,
                      user: auth.User = Depends(auth.require_strict("owner", "courier"))):
        _ensure_courier_owns(user, order_id)
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                raise HTTPException(404, "Bestellung nicht gefunden.")
            if row["status"] != "en_route":
                orders.transition(conn, order_id, "en_route", actor_user_id=user.id)
            conn.execute("COMMIT")
        except Exception:
            try: conn.execute("ROLLBACK")
            except Exception: pass
            raise
        finally:
            conn.close()
        return RedirectResponse(f"/courier/{order_id}", status_code=303)

    @app.post("/courier/{order_id}/reveal_phone")
    def courier_reveal_phone(request: Request, order_id: int,
                             reason: str = Form("call_customer"),
                             user: auth.User = Depends(auth.require_strict("owner", "courier"))):
        _ensure_courier_owns(user, order_id)
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT c.phone FROM orders o LEFT JOIN order_contacts c ON o.id = c.order_id "
                "WHERE o.id = ?",
                (order_id,),
            ).fetchone()
            if not row or not row["phone"]:
                raise HTTPException(404, "Keine Telefonnummer verfügbar.")
            conn.execute(
                "INSERT INTO access_log (user_id, action, object_type, object_id, reason) "
                "VALUES (?, 'reveal_phone', 'order', ?, ?)",
                (user.id, str(order_id), reason.strip()[:120]),
            )
            orders.log_event(conn, order_id, "pii.phone_revealed", user.id, reason.strip()[:120])
        finally:
            conn.close()
        return {"phone": row["phone"]}

    @app.post("/courier/{order_id}/delivered")
    def courier_delivered(request: Request, order_id: int,
                          user: auth.User = Depends(auth.require_strict("owner", "courier"))):
        _ensure_courier_owns(user, order_id)
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                raise HTTPException(404, "Bestellung nicht gefunden.")
            current = row["status"]
            if current == "closed":
                conn.execute("COMMIT")
            else:
                if current != "delivered":
                    orders.transition(conn, order_id, "delivered", actor_user_id=user.id)
                orders.transition(conn, order_id, "closed", actor_user_id=user.id)
                conn.execute("COMMIT")
        except Exception:
            try: conn.execute("ROLLBACK")
            except Exception: pass
            raise
        finally:
            conn.close()
        return RedirectResponse("/courier?flash=delivered", status_code=303)

    @app.post("/courier/{order_id}/failed")
    def courier_failed(request: Request, order_id: int,
                       reason: str = Form(...),
                       user: auth.User = Depends(auth.require_strict("owner", "courier"))):
        _ensure_courier_owns(user, order_id)
        reason_v = reason.strip()
        if not reason_v:
            raise HTTPException(400, "Grund ist erforderlich.")
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            orders.transition(conn, order_id, "failed_delivery",
                              actor_user_id=user.id, detail=reason_v[:160])
            conn.execute("COMMIT")
        except Exception:
            try: conn.execute("ROLLBACK")
            except Exception: pass
            raise
        finally:
            conn.close()
        return RedirectResponse("/courier?flash=failed", status_code=303)

    # ---------- dashboard ----------

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request,
                  range_: str = Query("today", alias="range"),
                  user: auth.User = Depends(auth.require_strict("owner"))):
        range_ = range_ if range_ in ("today", "7d") else "today"
        conn = db.connect()
        try:
            start, end = report_window(1 if range_ == "today" else 7)
            where = f"created_at >= '{start}' AND created_at < '{end}'"
            where_delivered = f"delivered_at >= '{start}' AND delivered_at < '{end}'"
            where_ready = f"ready_at >= '{start}' AND ready_at < '{end}'"

            prepared = conn.execute(
                f"SELECT COUNT(*) AS n FROM orders "
                f"WHERE {where_ready} "
            ).fetchone()["n"]

            kitchen_stats = conn.execute(
                "SELECT "
                "  SUM(CASE WHEN o.confirmed_at IS NOT NULL AND o.ready_at IS NOT NULL "
                "           THEN (strftime('%s', o.ready_at) - strftime('%s', o.confirmed_at)) END) AS prep_seconds, "
                "  COUNT(CASE WHEN o.confirmed_at IS NOT NULL AND o.ready_at IS NOT NULL THEN 1 END) AS prep_count, "
                "  COALESCE((SELECT SUM(oi.qty) FROM order_items oi JOIN orders o2 ON oi.order_id=o2.id "
               f"            WHERE o2.ready_at >= '{start}' AND o2.ready_at < '{end}'), 0) AS items_prepared "
                "FROM orders o "
               f"WHERE o.ready_at >= '{start}' AND o.ready_at < '{end}'"
            ).fetchone()
            prep_count = kitchen_stats["prep_count"] or 0
            avg_prep_s = int((kitchen_stats["prep_seconds"] or 0) / prep_count) if prep_count else 0
            avg_prep_min = round(avg_prep_s / 60, 1)
            items_prepared = kitchen_stats["items_prepared"] or 0

            per_courier = conn.execute(
                "SELECT u.id, u.display_name, "
                "       COUNT(o.id) AS delivered_count, "
                "       COALESCE(SUM(o.total_cents), 0) AS gross_cents "
                "FROM users u "
                "LEFT JOIN orders o ON o.assigned_courier_id = u.id "
                "   AND o.status IN ('delivered','closed') "
                f"  AND {where_delivered} "
                "WHERE u.role = 'courier' AND u.active = 1 "
                "GROUP BY u.id, u.display_name "
                "ORDER BY delivered_count DESC, u.display_name"
            ).fetchall()

            totals = conn.execute(
                f"SELECT "
                f"  COUNT(*) AS orders_count, "
                f"  COALESCE(SUM(CASE WHEN status IN ('delivered','closed') THEN total_cents END), 0) AS gross_delivered, "
                f"  COALESCE(SUM(CASE WHEN status NOT IN ('rejected','cancelled','failed_delivery') THEN total_cents END), 0) AS gross_active, "
                f"  SUM(CASE WHEN status IN ('rejected','cancelled','failed_delivery') THEN 1 ELSE 0 END) AS cancel_count, "
                f"  SUM(CASE WHEN source = 'voice' THEN 1 ELSE 0 END) AS voice_count "
                f"FROM orders WHERE {where}"
            ).fetchone()
            totals = dict(totals)
            delivered = conn.execute(f"SELECT COUNT(*) n, COALESCE(SUM(total_cents),0) gross FROM orders WHERE status IN ('delivered','closed') AND {where_delivered}").fetchone()
            totals["gross_delivered"] = delivered["gross"]
            orders_count = totals["orders_count"] or 0
            avg_ticket = (totals["gross_delivered"] // delivered["n"]) if delivered["n"] else None
            cancel_rate = (
                round(100.0 * (totals["cancel_count"] or 0) / orders_count, 1)
                if orders_count else 0.0
            )
            ai_share = (
                round(100.0 * (totals["voice_count"] or 0) / orders_count, 1)
                if orders_count else 0.0
            )
        finally:
            conn.close()
        return TEMPLATES.TemplateResponse(
            request,
            "dashboard.html",
            ctx(
                request,
                range_=range_,
                prepared=prepared,
                avg_prep_min=avg_prep_min,
                items_prepared=items_prepared,
                per_courier=per_courier,
                totals=totals,
                avg_ticket=avg_ticket,
                cancel_rate=cancel_rate,
                ai_share=ai_share,
            ),
        )

    # ---------- helpers ----------

    def _require_state(order_id: int, expected: str) -> None:
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT status FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
        finally:
            conn.close()
        if not row:
            raise HTTPException(404, "Bestellung nicht gefunden.")
        if row["status"] != expected:
            raise HTTPException(409, f"Status ist '{_status_de(row['status'])}', erwartet '{_status_de(expected)}'.")

    def _ensure_courier_owns(user: auth.User, order_id: int) -> None:
        if user.is_owner():
            return
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT assigned_courier_id FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
        finally:
            conn.close()
        if not row or row["assigned_courier_id"] != user.id:
            raise HTTPException(403, "Diese Bestellung ist nicht Ihnen zugewiesen.")

    def _submit_call_payload(payload: dict, actor_user_id: int, request_key=None) -> dict:
        if not isinstance(payload.get("address"), dict) or not isinstance(payload.get("items"), list):
            raise HTTPException(400, "Adresse oder Positionen fehlen.")
        phone = _normalize_phone(str(payload.get("phone", "")).strip())
        name = str(payload.get("name", "")).strip()
        address = payload.get("address") or {}
        street = str(address.get("street", "")).strip()
        house_number = str(address.get("house_number", "")).strip()
        plz = str(address.get("plz", "")).strip()
        city = str(address.get("city", "")).strip()
        delivery_notes = str(address.get("notes", "")).strip()
        items = payload.get("items") or []

        if not phone or not name or not street or not house_number or not plz or not city:
            raise HTTPException(400, "Anrufer- oder Adressdaten unvollständig.")
        if not re.fullmatch(r"\d{5}", plz):
            raise HTTPException(400, "PLZ muss aus 5 Ziffern bestehen.")
        if not items:
            raise HTTPException(400, "Leere Bestellung kann nicht übermittelt werden.")

        if not re.fullmatch(r"\+[1-9]\d{6,14}", phone):
            raise HTTPException(400, "Telefonnummer ist ungültig.")
        for item in items:
            if not isinstance(item, dict) or type(item.get("menu_item_id")) is not int or type(item.get("qty")) is not int or not 1 <= item["qty"] <= 100:
                raise HTTPException(400, "Position oder Menge ungültig (erlaubt: 1–100).")
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        if request_key and not re.fullmatch(r"[a-zA-Z0-9-]{16,80}", request_key):
            raise HTTPException(400, "Idempotenz-Schlüssel ungültig.")
        call_meta = VOICE.start_call(phone)

        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if request_key:
                previous = conn.execute("SELECT * FROM submissions WHERE request_key=? AND actor=?", (request_key, actor_user_id)).fetchone()
                if previous:
                    if previous["digest"] != digest:
                        raise HTTPException(409, "Idempotenz-Schlüssel wurde mit anderen Daten erneut verwendet.")
                    conn.execute("COMMIT")
                    return json.loads(previous["result"])
            row = conn.execute(
                "SELECT * FROM customers WHERE phone = ?", (phone,)
            ).fetchone()
            if row:
                customer_id = row["id"]
                crm_match = "matched" if row["trusted"] else "unmatched"
                changed_fields = [
                    f for f, old, new in (
                        ("name", row["name"], name),
                        ("street", row["street"], street),
                        ("house_number", row["house_number"], house_number),
                        ("plz", row["plz"], plz),
                        ("city", row["city"], city),
                    ) if (old or "") != (new or "")
                ]
                conn.execute(
                    "UPDATE customers SET name=?, street=?, house_number=?, plz=?, "
                    "city=?, notes=?, updated_at=datetime('now') WHERE id=?",
                    (name, street, house_number, plz, city, delivery_notes, customer_id),
                )
                if changed_fields:
                    conn.execute(
                        "INSERT INTO access_log (user_id, action, object_type, object_id, reason) "
                        "VALUES (?, 'customer.updated', 'customer', ?, ?)",
                        (actor_user_id, str(customer_id),
                         "voice_submit:" + ",".join(changed_fields))
                    )
            else:
                cur = conn.execute(
                    "INSERT INTO customers (phone, name, street, house_number, plz, city, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (phone, name, street, house_number, plz, city, delivery_notes),
                )
                customer_id = cur.lastrowid
                crm_match = "unmatched"

            cur = conn.execute(
                "INSERT INTO orders (customer_id, status, source, call_id, call_language, "
                "disclosure_at, recording_stored, delivery_notes) "
                "VALUES (?, 'new', 'voice', ?, ?, ?, 0, ?)",
                (customer_id, call_meta.call_id, call_meta.language,
                 call_meta.disclosure_at, delivery_notes),
            )
            order_id = cur.lastrowid

            total = 0
            for it in items:
                mid = int(it.get("menu_item_id"))
                qty = int(it.get("qty", 1))
                if not 1 <= qty <= 100:
                    raise HTTPException(400, "Ungültige Menge.")
                m = conn.execute(
                    "SELECT id, name, price_cents FROM menu_items "
                    "WHERE id = ? AND available = 1",
                    (mid,),
                ).fetchone()
                if not m:
                    raise HTTPException(400, "Position unbekannt oder nicht verfügbar.")
                conn.execute(
                    "INSERT INTO order_items "
                    "(order_id, menu_item_id, name_snapshot, qty, unit_price_cents) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (order_id, m["id"], m["name"], qty, m["price_cents"]),
                )
                total += qty * m["price_cents"]
            conn.execute(
                "UPDATE orders SET total_cents = ? WHERE id = ?", (total, order_id)
            )
            conn.execute("INSERT INTO order_contacts (order_id, phone, name, street, house_number, plz, city, notes) VALUES (?,?,?,?,?,?,?,?)", (order_id, phone, name, street, house_number, plz, city, delivery_notes))
            if request_key:
                result = dict(order_id=order_id, call_id=call_meta.call_id, crm_match_status=crm_match, total_cents=total)
                conn.execute("INSERT INTO submissions VALUES (?,?,?,?)", (request_key, actor_user_id, digest, json.dumps(result)))
            orders.log_event(conn, order_id, "voice.order.submitted",
                             actor_user_id,
                             f"call_id={call_meta.call_id} crm={crm_match}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        VOICE.end_call(call_meta.call_id)
        return {
            "order_id": order_id,
            "call_id": call_meta.call_id,
            "crm_match_status": crm_match,
            "total_cents": total,
        }

    return app


def _home_for(role: str) -> str:
    return {
        "owner":     "/dashboard",
        "confirmer": "/confirmer",
        "kitchen":   "/kitchen",
        "courier":   "/courier",
    }.get(role, "/menu")


_PRICE_RE = re.compile(r"^\s*(\d+)(?:[.,](\d{1,2}))?\s*€?\s*$")


def _parse_price(raw: str) -> int:
    m = _PRICE_RE.match(raw or "")
    if not m:
        raise HTTPException(400, "Preis ungültig. Bitte Format 9,90 verwenden.")
    euros = int(m.group(1))
    cents_part = m.group(2) or "0"
    cents_part = (cents_part + "00")[:2]
    return euros * 100 + int(cents_part)


def _normalize_phone(raw: str) -> str:
    s = re.sub(r"[^\d+]", "", raw or "")
    if s.startswith("00"):
        s = "+" + s[2:]
    if s and not s.startswith("+"):
        if s.startswith("0"):
            s = "+49" + s[1:]
        else:
            s = "+49" + s
    return s


def _disclosure_de() -> str:
    return (
        "Guten Tag, hier ist der Sprachassistent von Klare KI. "
        "Sie sprechen mit einer KI. Dieses Gespräch wird nicht aufgezeichnet. "
        "Ich speichere nur die Angaben, die für Ihre Bestellung notwendig sind. "
        "Sagen Sie jederzeit 'Mitarbeiter', wenn Sie lieber mit einer Person sprechen möchten."
    )


app = create_app()
