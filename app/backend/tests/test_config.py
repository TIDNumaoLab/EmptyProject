import pytest
from pydantic import ValidationError

from smdx_api.config import AppConfig


def test_defaults_match_design(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)
    for k in ["DATABASE_URL", "CORS_ALLOW_ORIGINS", "STORE_LATITUDE", "SESSION_MAX_AGE_HOURS", "SESSION_COOKIE_SECURE"]:
        monkeypatch.delenv(k, raising=False)
    c = AppConfig(_env_file=None)
    assert c.database_url == "postgresql://postgres:postgres@localhost:5432/supermarket_dx"
    assert c.weather_api_base_url == "https://api.open-meteo.com/v1/forecast"
    assert c.weather_api_archive_url == "https://archive-api.open-meteo.com/v1/archive"
    assert c.weather_api_timeout_seconds == 10
    assert (c.store_latitude, c.store_longitude) == (35.6895, 139.6917)
    assert c.model_daily_path == "models/daily.joblib"
    assert c.model_time_band_path == "models/time_band.joblib"
    assert c.cors_allow_origins == ["http://localhost:5173"]
    assert c.session_cookie_secure is False
    assert c.session_max_age_hours == 3
    assert c.tz == "Asia/Tokyo"


def test_cors_origins_split_by_comma(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://a.example, https://b.example")
    assert AppConfig(_env_file=None).cors_allow_origins == ["http://a.example", "https://b.example"]


def test_session_secret_is_required(monkeypatch):
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(ValidationError):
        AppConfig(_env_file=None)


@pytest.mark.parametrize("secret", ["", "short-secret"])
def test_empty_or_short_session_secret_is_rejected(monkeypatch, secret):
    # 空の署名鍵で起動すると誰でもセッションCookieを偽造できる(.env.example をそのまま使った場合など)
    monkeypatch.setenv("SESSION_SECRET", secret)
    with pytest.raises(ValidationError):
        AppConfig(_env_file=None)
