"""FastAPI entry point: routes for all MVP flows."""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, db, orders, seed
from .voice.simulator import SimulatorVoiceProvider

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
STATIC_DIR = BASE_DIR / "static"

VOICE = SimulatorVoiceProvider()

SESSION_SECRET = os.environ.get(
    "KLARE_SESSION_SECRET",
    "dev-only-secret-change-me-in-every-non-local-environment",
)


def _format_cents(cents: int) -> str:
    euros = cents // 100
    rest = cents % 100
    return f"{euros},{rest:02d} €"


TEMPLATES.env.filters["cents"] = _format_cents


def create_app() -> FastAPI:
    app = FastAPI(title="Klare KI Restaurant MVP", version="0.1.0")
    app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=60 * 60 * 12)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    db.init_db()
    # Seed is idempotent, safe at startup.
    seed.run()

    @app.exception_handler(orders.StateError)
    def _state_error(request: Request, exc: orders.StateError):
        return Response(status_code=409, content=str(exc))

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
        conn = db.connect()
        try:
            conn.execute(
                "UPDATE customers SET name=?, street=?, house_number=?, plz=?, "
                "city=?, notes=?, updated_at=datetime('now') WHERE id=?",
                (name.strip(), street.strip(), house_number.strip(),
                 plz.strip(), city.strip(), notes.strip(), cid),
            )
        finally:
            conn.close()
        return RedirectResponse("/customers", status_code=303)

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
        payload = await request.json()
        return _submit_call_payload(payload, actor_user_id=user.id)

    # ---------- confirmer ----------

    @app.get("/confirmer", response_class=HTMLResponse)
    def confirmer_queue(request: Request,
                        user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        conn = db.connect()
        try:
            rows = conn.execute(
                "SELECT o.id, o.status, o.total_cents, o.created_at, "
                "       c.name AS customer_name, c.phone AS customer_phone "
                "FROM orders o LEFT JOIN customers c ON o.customer_id = c.id "
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
            raise HTTPException(404, "order not found")
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
            conn.execute("BEGIN")
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
        return RedirectResponse("/confirmer", status_code=303)

    @app.post("/confirmer/{order_id}/reject")
    def confirmer_reject(request: Request, order_id: int,
                         reason: str = Form(...),
                         user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        conn = db.connect()
        try:
            conn.execute("BEGIN")
            conn.execute(
                "UPDATE orders SET reject_reason = ? WHERE id = ?",
                (reason.strip(), order_id),
            )
            orders.transition(conn, order_id, "rejected",
                              actor_user_id=user.id, detail=reason.strip())
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return RedirectResponse("/confirmer", status_code=303)

    @app.post("/confirmer/{order_id}/edit_item")
    def confirmer_edit_item(request: Request, order_id: int,
                            item_id: int = Form(...),
                            qty: int = Form(...),
                            user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        if qty < 0:
            raise HTTPException(400, "qty must be >= 0")
        _require_state(order_id, "new")
        conn = db.connect()
        try:
            conn.execute("BEGIN")
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
        if qty < 1:
            raise HTTPException(400, "qty must be >= 1")
        _require_state(order_id, "new")
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT id, name, price_cents FROM menu_items WHERE id = ? AND available = 1",
                (menu_item_id,),
            ).fetchone()
            if not row:
                raise HTTPException(400, "unknown or unavailable menu item")
            conn.execute("BEGIN")
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
        except HTTPException:
            raise
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
            orders.transition(conn, order_id, "in_kitchen", actor_user_id=user.id)
        finally:
            conn.close()
        return RedirectResponse("/kitchen", status_code=303)

    @app.post("/kitchen/{order_id}/ready")
    def kitchen_ready(request: Request, order_id: int,
                      user: auth.User = Depends(auth.require_strict("owner", "kitchen"))):
        conn = db.connect()
        try:
            # Allow going confirmed -> ready directly (skip in_kitchen).
            row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
            if row and row["status"] == "confirmed":
                orders.transition(conn, order_id, "in_kitchen", actor_user_id=user.id)
            orders.transition(conn, order_id, "ready", actor_user_id=user.id)
        finally:
            conn.close()
        return RedirectResponse("/kitchen", status_code=303)

    # ---------- courier dispatch + mobile ----------

    @app.get("/dispatch", response_class=HTMLResponse)
    def dispatch_page(request: Request,
                      user: auth.User = Depends(auth.require_strict("owner", "confirmer"))):
        conn = db.connect()
        try:
            ready = conn.execute(
                "SELECT o.*, c.name AS customer_name, c.street, c.house_number, c.plz, c.city "
                "FROM orders o LEFT JOIN customers c ON o.customer_id = c.id "
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
            conn.execute("BEGIN")
            crow = conn.execute(
                "SELECT id FROM users WHERE id = ? AND role = 'courier' AND active = 1",
                (courier_id,),
            ).fetchone()
            if not crow:
                raise HTTPException(400, "unknown courier")
            conn.execute(
                "UPDATE orders SET assigned_courier_id = ? WHERE id = ?",
                (courier_id, order_id),
            )
            orders.transition(conn, order_id, "assigned",
                              actor_user_id=user.id, detail=f"courier={courier_id}")
            conn.execute("COMMIT")
        except HTTPException:
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return RedirectResponse("/dispatch", status_code=303)

    @app.get("/courier", response_class=HTMLResponse)
    def courier_page(request: Request,
                     user: auth.User = Depends(auth.require_strict("owner", "courier"))):
        conn = db.connect()
        try:
            rows = conn.execute(
                "SELECT o.*, c.name AS customer_first_name, c.street, c.house_number, "
                "       c.plz, c.city, c.notes AS delivery_notes "
                "FROM orders o LEFT JOIN customers c ON o.customer_id = c.id "
                "WHERE o.assigned_courier_id = ? AND o.status IN ('assigned','en_route') "
                "ORDER BY o.assigned_at ASC",
                (user.id,),
            ).fetchall()
            done = conn.execute(
                "SELECT o.id, o.delivered_at, o.total_cents "
                "FROM orders o "
                "WHERE o.assigned_courier_id = ? "
                "  AND o.status IN ('delivered','closed') "
                "  AND date(o.delivered_at) = date('now') "
                "ORDER BY o.delivered_at DESC",
                (user.id,),
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
            raise HTTPException(404, "order not found")
        if not user.is_owner() and bundle["order"]["assigned_courier_id"] != user.id:
            raise HTTPException(403, "not your order")
        nav_url = None
        if bundle["customer"]:
            addr = (
                f"{bundle['customer']['street']} {bundle['customer']['house_number']}, "
                f"{bundle['customer']['plz']} {bundle['customer']['city']}"
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
            orders.transition(conn, order_id, "en_route", actor_user_id=user.id)
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
                "SELECT c.phone FROM orders o LEFT JOIN customers c ON o.customer_id = c.id "
                "WHERE o.id = ?",
                (order_id,),
            ).fetchone()
            if not row or not row["phone"]:
                raise HTTPException(404, "no phone")
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
            conn.execute("BEGIN")
            orders.transition(conn, order_id, "delivered", actor_user_id=user.id)
            orders.transition(conn, order_id, "closed", actor_user_id=user.id)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return RedirectResponse("/courier", status_code=303)

    @app.post("/courier/{order_id}/failed")
    def courier_failed(request: Request, order_id: int,
                       reason: str = Form(...),
                       user: auth.User = Depends(auth.require_strict("owner", "courier"))):
        _ensure_courier_owns(user, order_id)
        conn = db.connect()
        try:
            orders.transition(conn, order_id, "failed_delivery",
                              actor_user_id=user.id, detail=reason.strip()[:160])
        finally:
            conn.close()
        return RedirectResponse("/courier", status_code=303)

    # ---------- dashboard ----------

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request,
                  range_: str = Query("today", alias="range"),
                  user: auth.User = Depends(auth.require_strict("owner"))):
        range_ = range_ if range_ in ("today", "7d") else "today"
        conn = db.connect()
        try:
            if range_ == "today":
                where = "date(created_at) = date('now')"
                where_delivered = "date(delivered_at) = date('now')"
                where_ready = "date(ready_at) = date('now')"
            else:
                where = "date(created_at) >= date('now','-6 day')"
                where_delivered = "date(delivered_at) >= date('now','-6 day')"
                where_ready = "date(ready_at) >= date('now','-6 day')"

            prepared = conn.execute(
                f"SELECT COUNT(*) AS n FROM orders "
                f"WHERE {where_ready} AND status IN ('ready','assigned','en_route','delivered','closed')"
            ).fetchone()["n"]

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
                f"  COALESCE(SUM(CASE WHEN status NOT IN ('rejected','cancelled') THEN total_cents END), 0) AS gross_active, "
                f"  SUM(CASE WHEN status IN ('rejected','cancelled') THEN 1 ELSE 0 END) AS cancel_count, "
                f"  SUM(CASE WHEN source = 'voice' THEN 1 ELSE 0 END) AS voice_count "
                f"FROM orders WHERE {where}"
            ).fetchone()
            orders_count = totals["orders_count"] or 0
            avg_ticket = (totals["gross_delivered"] // max(1, orders_count)) if orders_count else 0
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
            raise HTTPException(404, "order not found")
        if row["status"] != expected:
            raise HTTPException(409, f"order status is {row['status']}, expected {expected}")

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
            raise HTTPException(403, "not your order")

    def _submit_call_payload(payload: dict, actor_user_id: int) -> dict:
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
            raise HTTPException(400, "missing caller/address fields")
        if not re.fullmatch(r"\d{5}", plz):
            raise HTTPException(400, "PLZ must be 5 digits")
        if not items:
            raise HTTPException(400, "cannot submit an empty order")

        call_meta = VOICE.start_call(phone)

        conn = db.connect()
        try:
            conn.execute("BEGIN")
            row = conn.execute(
                "SELECT * FROM customers WHERE phone = ?", (phone,)
            ).fetchone()
            if row:
                customer_id = row["id"]
                crm_match = "matched" if row["trusted"] else "unmatched"
                conn.execute(
                    "UPDATE customers SET name=?, street=?, house_number=?, plz=?, "
                    "city=?, notes=?, updated_at=datetime('now') WHERE id=?",
                    (name, street, house_number, plz, city, delivery_notes, customer_id),
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
                if qty < 1:
                    continue
                m = conn.execute(
                    "SELECT id, name, price_cents FROM menu_items "
                    "WHERE id = ? AND available = 1",
                    (mid,),
                ).fetchone()
                if not m:
                    continue
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
            orders.log_event(conn, order_id, "voice.order.submitted",
                             actor_user_id,
                             f"call_id={call_meta.call_id} crm={crm_match}")
            conn.execute("COMMIT")
        except HTTPException:
            raise
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
        raise HTTPException(400, "invalid price")
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
