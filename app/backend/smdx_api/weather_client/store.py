"""取得した気象の保存と読み出し(weather_forecasts / weather_actuals)。"""
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from smdx_api.clock import JST
from smdx_api.db.models import WeatherActual, WeatherForecast
from smdx_api.weather_client.client import HourlyWeather

_CHUNK = 1000


def day_range(start: date, end: date) -> tuple[datetime, datetime]:
    """start 0:00 〜 end 翌日 0:00(JST)の半開区間。"""
    return datetime.combine(start, time(0), JST), datetime.combine(end + timedelta(days=1), time(0), JST)


def save_forecast(db: Session, fetched_at: datetime, rows: Sequence[HourlyWeather]) -> None:
    values = [dict(fetched_at=fetched_at, forecast_time=r.time, weather_code=r.weather_code, temperature=r.temperature,
                   precipitation_probability=r.precipitation_probability, precipitation=r.precipitation) for r in rows]
    for i in range(0, len(values), _CHUNK):
        db.execute(insert(WeatherForecast).values(values[i : i + _CHUNK]).on_conflict_do_nothing(
            index_elements=["fetched_at", "forecast_time"]))
    db.flush()


def _to_hourly(r) -> HourlyWeather:
    return HourlyWeather(r.forecast_time, r.weather_code, r.temperature, r.precipitation_probability, r.precipitation)


def find_recent_forecast(
    db: Session, start: date, end: date, fetched_after: datetime
) -> tuple[datetime, list[HourlyWeather]] | None:
    """期間の全時刻を含む取得のうち、fetched_after より後で最も新しいもの。"""
    lo, hi = day_range(start, end)
    expected = ((end - start).days + 1) * 24
    fetched_at = db.scalar(
        select(WeatherForecast.fetched_at)
        .where(WeatherForecast.fetched_at > fetched_after, WeatherForecast.forecast_time >= lo, WeatherForecast.forecast_time < hi)
        .group_by(WeatherForecast.fetched_at)
        .having(func.count() >= expected)
        .order_by(WeatherForecast.fetched_at.desc())
        .limit(1)
    )
    if fetched_at is None:
        return None
    rows = db.scalars(
        select(WeatherForecast)
        .where(WeatherForecast.fetched_at == fetched_at, WeatherForecast.forecast_time >= lo, WeatherForecast.forecast_time < hi)
        .order_by(WeatherForecast.forecast_time)
    )
    return fetched_at, [_to_hourly(r) for r in rows]


def save_actuals(db: Session, rows: Sequence[HourlyWeather], source: Literal["archive", "historical_forecast"]) -> int:
    values = [dict(observed_time=r.time, weather_code=r.weather_code, temperature=r.temperature,
                   precipitation_probability=r.precipitation_probability, precipitation=r.precipitation, source=source)
              for r in rows]
    for i in range(0, len(values), _CHUNK):
        stmt = insert(WeatherActual).values(values[i : i + _CHUNK])
        db.execute(stmt.on_conflict_do_update(
            index_elements=["observed_time"],
            set_={k: getattr(stmt.excluded, k) for k in
                  ("weather_code", "temperature", "precipitation_probability", "precipitation", "source", "updated_at")},
        ))
    db.flush()
    return len(values)
