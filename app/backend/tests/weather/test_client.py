"""Open-Meteo クライアント(httpx の MockTransport で模擬応答)。"""
from datetime import date, datetime

import httpx
import pytest

from smdx_api.clock import JST
from smdx_api.config import AppConfig
from smdx_api.weather_client.client import HourlyWeather, OpenMeteoClient, WeatherUnavailable
from smdx_api.weather_client.config import WeatherConfig

TIMES = ["2026-10-16T00:00", "2026-10-16T01:00"]


def _client(handler) -> OpenMeteoClient:
    return OpenMeteoClient.from_config(WeatherConfig(_env_file=None), transport=httpx.MockTransport(handler))


def _ok(**hourly):
    base = {"time": TIMES, "temperature_2m": [15.1, 14.8], "precipitation_probability": [10, 20],
            "precipitation": [0, 0.2], "weather_code": [1, 61]}
    return httpx.Response(200, json={"hourly": base | hourly})


def test_forecast_parses_hourly_and_sends_params():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url.copy_with(query=None))
        seen.update(dict(req.url.params))
        return _ok()

    rows = _client(handler).fetch_forecast(date(2026, 10, 16), date(2026, 10, 17))
    assert seen["url"] == "https://api.open-meteo.com/v1/forecast"
    assert seen["timezone"] == "Asia/Tokyo" and seen["start_date"] == "2026-10-16" and seen["end_date"] == "2026-10-17"
    assert (seen["latitude"], seen["longitude"]) == ("35.6895", "139.6917")
    assert seen["hourly"] == "temperature_2m,precipitation_probability,precipitation,weather_code"
    assert rows[1] == HourlyWeather(datetime(2026, 10, 16, 1, tzinfo=JST), 61, 14.8, 20.0, 0.2)


def test_archive_uses_archive_url_without_probability():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url.copy_with(query=None))
        seen["hourly"] = req.url.params["hourly"]
        return httpx.Response(200, json={"hourly": {"time": TIMES, "temperature_2m": [1.0, 2.0], "precipitation": [0, 0], "weather_code": [3, 3]}})

    rows = _client(handler).fetch_archive(date(2026, 10, 16), date(2026, 10, 16))
    assert seen["url"] == "https://archive-api.open-meteo.com/v1/archive"
    assert seen["hourly"] == "temperature_2m,precipitation,weather_code"
    assert rows[0].precipitation_probability is None and rows[0].weather_code == 3


def test_null_values_are_skipped():
    rows = _client(lambda req: _ok(weather_code=[1, None])).fetch_forecast(date(2026, 10, 16), date(2026, 10, 16))
    assert [r.time.hour for r in rows] == [0]


def _raise_timeout(req):
    raise httpx.ReadTimeout("timeout")


@pytest.mark.parametrize("handler", [
    lambda req: httpx.Response(500),
    lambda req: httpx.Response(200, json={}),
    lambda req: httpx.Response(200, text="not json"),
    lambda req: _ok(temperature_2m=[15.1]),       # 配列の長さが合わない
    lambda req: _ok(time=["2026/10/16 00:00", "x"]),
    _raise_timeout,
])
def test_failures_raise_weather_unavailable(handler):
    with pytest.raises(WeatherUnavailable):
        _client(handler).fetch_forecast(date(2026, 10, 16), date(2026, 10, 16))


def test_timeout_and_location_come_from_config(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("WEATHER_API_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("STORE_LATITUDE", "36.0")
    c = OpenMeteoClient.from_config(AppConfig(_env_file=None))
    assert c.timeout_seconds == 7 and c.latitude == 36.0


def test_weather_config_defaults_match_app_config(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)
    for k in ["WEATHER_API_TIMEOUT_SECONDS", "STORE_LATITUDE", "STORE_LONGITUDE", "WEATHER_API_BASE_URL", "WEATHER_API_ARCHIVE_URL"]:
        monkeypatch.delenv(k, raising=False)
    w, a = WeatherConfig(_env_file=None), AppConfig(_env_file=None)
    for f in ["weather_api_base_url", "weather_api_archive_url", "weather_api_timeout_seconds", "store_latitude", "store_longitude"]:
        assert getattr(w, f) == getattr(a, f)
    assert w.weather_api_timeout_seconds == 10
