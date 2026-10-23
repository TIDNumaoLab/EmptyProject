import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from smdx_api.config import AppConfig
from smdx_api.main import create_app
from smdx_api.security import is_csrf_safe


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_state_changing_without_header_is_unsafe(method):
    assert is_csrf_safe(method, {}) is False
    assert is_csrf_safe(method, {"X-Requested-With": "other"}) is False
    assert is_csrf_safe(method, {"X-Requested-With": "smdx"}) is True


def test_get_is_always_safe():
    assert is_csrf_safe("GET", {}) is True


def test_post_without_header_returns_403(app):
    @app.post("/_t")
    def _t():
        return {"ok": True}

    raw = TestClient(app)  # 既定ヘッダなし
    res = raw.post("/_t")
    assert res.status_code == 403
    assert res.json() == {"detail": "この操作を行う権限がありません"}
    assert raw.post("/_t", headers={"X-Requested-With": "smdx"}).status_code == 200


def test_login_without_header_is_rejected(app):
    assert TestClient(app).post("/api/auth/login", json={}).status_code == 403


def test_cors_allows_configured_origin(client):
    res = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Requested-With",
        },
    )
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert res.headers["access-control-allow-credentials"] == "true"


def _add_session_routes(app):
    @app.post("/_login")
    def _login(request: Request):
        request.session["user_id"] = 1
        return {}

    @app.get("/_touch")
    def _touch(request: Request):
        return {"user_id": request.session.get("user_id")}


def test_session_max_age_default_and_sliding(app):
    _add_session_routes(app)
    c = TestClient(app, headers={"X-Requested-With": "smdx"})
    first = c.post("/_login")
    assert "max-age=10800" in first.headers["set-cookie"].lower()  # 既定3時間
    again = c.get("/_touch")  # 操作のたびに出し直す(期限が延びる)
    assert again.json() == {"user_id": 1}
    assert "max-age=10800" in again.headers["set-cookie"].lower()


def test_session_max_age_from_config(config):
    app = create_app(config.model_copy(update={"session_max_age_hours": 0.5}))
    _add_session_routes(app)
    res = TestClient(app, headers={"X-Requested-With": "smdx"}).post("/_login")
    assert "max-age=1800" in res.headers["set-cookie"].lower()


def test_session_max_age_must_be_positive(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("SESSION_MAX_AGE_HOURS", "0")
    with pytest.raises(ValidationError):
        AppConfig(_env_file=None)
