"""Open-Meteo の呼び出し(詳細設計書「外部API仕様(気象データ)」)。

認証不要。位置は店舗の緯度・経度、タイムゾーンは Asia/Tokyo。タイムアウト・HTTPエラー・応答不正は
すべて WeatherUnavailable にする(呼び出し側は NO_WEATHER としてベースライン予測に切り替える)。
"""
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

import httpx

from smdx_api.clock import JST

_TIME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$")
FORECAST_HOURLY = ["temperature_2m", "precipitation_probability", "precipitation", "weather_code"]
ARCHIVE_HOURLY = ["temperature_2m", "precipitation", "weather_code"]


class WeatherUnavailable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class HourlyWeather:
    time: datetime  # JST、正時
    weather_code: int
    temperature: float
    precipitation_probability: float | None
    precipitation: float | None


class WeatherClient(Protocol):
    def fetch_forecast(self, start: date, end: date) -> list[HourlyWeather]: ...

    def fetch_archive(self, start: date, end: date) -> list[HourlyWeather]: ...


class _ConfigLike(Protocol):
    weather_api_base_url: str
    weather_api_archive_url: str
    weather_api_timeout_seconds: float
    store_latitude: float
    store_longitude: float


def _float(v: Any) -> float | None:
    return None if v is None else float(v)


class OpenMeteoClient:
    def __init__(
        self,
        forecast_url: str,
        archive_url: str,
        latitude: float,
        longitude: float,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.forecast_url = forecast_url
        self.archive_url = archive_url
        self.latitude = latitude
        self.longitude = longitude
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_config(cls, config: _ConfigLike, transport: httpx.BaseTransport | None = None) -> "OpenMeteoClient":
        return cls(config.weather_api_base_url, config.weather_api_archive_url, config.store_latitude,
                   config.store_longitude, config.weather_api_timeout_seconds, transport)

    def fetch_forecast(self, start: date, end: date) -> list[HourlyWeather]:
        return self._fetch(self.forecast_url, start, end, FORECAST_HOURLY)

    def fetch_archive(self, start: date, end: date) -> list[HourlyWeather]:
        return self._fetch(self.archive_url, start, end, ARCHIVE_HOURLY)

    def _fetch(self, url: str, start: date, end: date, hourly: list[str]) -> list[HourlyWeather]:
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": "Asia/Tokyo",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(hourly),
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self._transport) as http:
                res = http.get(url, params=params)
        except httpx.HTTPError as e:
            raise WeatherUnavailable(f"気象APIに接続できません: {type(e).__name__}") from None
        if res.status_code != 200:
            raise WeatherUnavailable(f"気象APIの応答が不正です(HTTP {res.status_code})")
        try:
            return _parse(res.json(), hourly)
        except (ValueError, KeyError, TypeError):
            raise WeatherUnavailable("気象APIの応答が不正です") from None


def _parse(body: Any, hourly: list[str]) -> list[HourlyWeather]:
    data = body["hourly"]
    times = data["time"]
    columns = {k: data[k] for k in hourly}
    if any(len(v) != len(times) for v in columns.values()):
        raise ValueError("配列の長さが一致しない")
    rows = []
    for i, t in enumerate(times):
        m = _TIME_RE.match(t)
        if not m:
            raise ValueError(f"時刻の形式が不正: {t}")
        code, temp = columns["weather_code"][i], columns["temperature_2m"][i]
        if code is None or temp is None:
            continue  # 値の無い時刻は使わない
        prob = columns["precipitation_probability"][i] if "precipitation_probability" in columns else None
        rows.append(HourlyWeather(
            time=datetime(*(int(g) for g in m.groups()), tzinfo=JST),
            weather_code=int(code),
            temperature=float(temp),
            precipitation_probability=_float(prob),
            precipitation=_float(columns["precipitation"][i]),
        ))
    return rows
