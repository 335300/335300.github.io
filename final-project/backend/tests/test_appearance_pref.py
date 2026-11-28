"""Appearance setting (Light / Dark / Match Mac), stored with the display prefs.

Prefs live in app-state.json (not in data.json), so no schema bump is needed:
an older app-state file without the key simply reads as "system".
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.api.deps import get_today
from app.app import create_app

from .conftest import TODAY


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    return TestClient(app)


def test_default_is_system(client):
    assert client.get("/api/prefs").json()["appearance"] == "system"


def test_set_dark_then_light_and_keep_other_prefs(client):
    client.patch("/api/prefs", json={"show_savings_tile": True})
    assert client.patch("/api/prefs", json={"appearance": "dark"}).json()["appearance"] == "dark"
    body = client.get("/api/prefs").json()
    assert body["appearance"] == "dark" and body["show_savings_tile"] is True
    assert client.patch("/api/prefs", json={"appearance": "light"}).json()["appearance"] == "light"


def test_unknown_value_is_refused(client):
    assert client.patch("/api/prefs", json={"appearance": "sepia"}).status_code == 422
    assert client.get("/api/prefs").json()["appearance"] == "system"


def test_old_or_broken_state_file_reads_as_system(client):
    path = config.app_state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"prefs": {"show_savings_tile": True}}), encoding="utf-8")
    assert client.get("/api/prefs").json()["appearance"] == "system"
    path.write_text(json.dumps({"prefs": {"appearance": "neon"}}), encoding="utf-8")
    assert client.get("/api/prefs").json()["appearance"] == "system"
