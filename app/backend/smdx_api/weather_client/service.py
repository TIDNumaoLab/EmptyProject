"""予報の取得(再利用つき)と過去実績の取得。"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from smdx_api.weather_client.client import HourlyWeather, WeatherClient, WeatherUnavailable
from smdx_api.weather_client.store import day_range, find_recent_forecast, save_actuals, save_forecast

# 予報の提供範囲(約16日先)のため、対象日は当日〜15日先に限る
MAX_DAYS_AHEAD = 15


@dataclass
class ForecastResult:
    available: bool
    fetched_at: datetime | None = None
    rows: list[HourlyWeather] = field(default_factory=list)


def get_forecast(db: Session, client: WeatherClient, start: date, end: date, now: datetime, stale_hours: float) -> ForecastResult:
    """期間の1時間ごとの予報。再計算の判定時間内に取得済みなら再利用し、無ければ取得して保存する。

    取得できない場合(範囲外・失敗・時刻の欠け)は available=False を返し、例外は外に出さない。
    """
    today = now.date()
    if end < start or start < today or end > today + timedelta(days=MAX_DAYS_AHEAD):
        return ForecastResult(False)
    recent = find_recent_forecast(db, start, end, now - timedelta(hours=stale_hours))
    if recent is not None:
        return ForecastResult(True, recent[0], recent[1])
    try:
        fetched = client.fetch_forecast(start, end)
    except WeatherUnavailable:
        return ForecastResult(False)
    lo, hi = day_range(start, end)
    rows = sorted((r for r in fetched if lo <= r.time < hi), key=lambda r: r.time)
    if len({r.time for r in rows}) < ((end - start).days + 1) * 24:
        return ForecastResult(False)
    save_forecast(db, now, rows)
    return ForecastResult(True, now, rows)


def fetch_weather_actuals(db: Session, client: WeatherClient, start: date, end: date) -> int:
    """過去実績を取得して weather_actuals に保存する(観測時刻で上書き)。失敗は WeatherUnavailable。"""
    return save_actuals(db, client.fetch_archive(start, end), source="archive")
