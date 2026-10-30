"""An unavailable grant service must not prevent visitors from signing in."""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.testclient import TestClient


@pytest.fixture
def gated_app(monkeypatch):
    # The optional geo-auth dependency lives outside this repository. Stub
    # its grant provider to exercise MELTS middleware without a live portal.
    monkeypatch.delenv("MELTS_AUTH", raising=False)
    module = importlib.import_module("web.app")
    monkeypatch.setenv("APP_ACCESS_SERVICE_TOKEN", "test-token")
    monkeypatch.setenv("APP_ACCESS_API_URL", "http://auth.test")
    access = SimpleNamespace(start=AsyncMock(), aclose=AsyncMock(), health=lambda: {})
    provider = ModuleType("geo_auth.appaccess")
    provider.AppAccess = lambda *args, **kwargs: access
    provider.HttpGrantSource = lambda *args, **kwargs: object()
    transport = ModuleType("geo_auth.appaccess_http")
    transport.gate = AsyncMock(
        return_value=JSONResponse({"detail": "Service temporarily unavailable"}, status_code=503)
    )
    monkeypatch.setitem(sys.modules, "geo_auth", ModuleType("geo_auth"))
    monkeypatch.setitem(sys.modules, "geo_auth.appaccess", provider)
    monkeypatch.setitem(sys.modules, "geo_auth.appaccess_http", transport)

    app = FastAPI()
    assert module._install_app_access(app)

    @app.get("/")
    async def index():
        return RedirectResponse("/login", status_code=302)

    @app.get("/login")
    async def login():
        return RedirectResponse("https://astrax.art/login", status_code=302)

    @app.get("/api/presets")
    async def presets():
        return {"private": True}

    with TestClient(app) as client:
        yield client, transport.gate


def test_anonymous_visitor_can_reach_sso_login(gated_app):
    client, gate = gated_app
    root = client.get("/", follow_redirects=False)
    assert root.status_code == 302
    assert root.headers["location"] == "/login"
    login = client.get(root.headers["location"], follow_redirects=False)
    assert login.status_code == 302
    assert login.headers["location"] == "https://astrax.art/login"
    gate.assert_not_awaited()


@pytest.mark.parametrize("path", ["/api/presets", "/login-extra"])
def test_other_paths_still_require_authorization(gated_app, path):
    client, gate = gated_app
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 503
    gate.assert_awaited_once()
