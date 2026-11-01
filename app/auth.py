"""Authentication, roles, access control."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import bcrypt
from fastapi import HTTPException, Request, status

from . import db

ROLES = ("owner", "confirmer", "kitchen", "courier")


@dataclass
class User:
    id: int
    username: str
    display_name: str
    role: str

    def is_owner(self) -> bool:
        return self.role == "owner"


def hash_password(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=10))


def verify_password(plain: str, stored: bytes) -> bool:
    if not stored:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), stored)
    except ValueError:
        return False


def login(username: str, password: str) -> User | None:
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id, username, display_name, role, password_hash, active "
            "FROM users WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
    finally:
        conn.close()
    if not row or not row["active"]:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return User(
        id=row["id"],
        username=row["username"],
        display_name=row["display_name"],
        role=row["role"],
    )


def current_user(request: Request) -> User | None:
    uid = request.session.get("uid")
    if not uid:
        return None
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id, username, display_name, role, active FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
    finally:
        conn.close()
    if not row or not row["active"]:
        return None
    return User(
        id=row["id"],
        username=row["username"],
        display_name=row["display_name"],
        role=row["role"],
    )


def require_strict(*roles: str) -> Callable[[Request], User]:
    """Allow access only if the user's role is in the allowlist.

    Owner is NOT auto-granted — pass "owner" explicitly where it should be
    allowed. This keeps each endpoint's role scope visible and auditable.
    """
    allowed = set(roles)

    def dep(request: Request) -> User:
        user = current_user(request)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "login required")
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "role not allowed")
        return user

    return dep
