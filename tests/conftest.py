"""Pytest fixtures: isolated SQLite + TestClient."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def tmp_db(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    path = Path(tmp.name)
    monkeypatch.setenv("KLARE_DB_PATH", str(path))
    yield path
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    # Cleanup WAL/SHM too
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists():
            sidecar.unlink()


@pytest.fixture()
def client(tmp_db):
    # Import inside the fixture so KLARE_DB_PATH is already set.
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


def login(client: TestClient, username: str, password: str) -> None:
    r = client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    assert r.status_code == 303, (r.status_code, r.text[:200])


def logout(client: TestClient) -> None:
    client.post("/logout", follow_redirects=False)
