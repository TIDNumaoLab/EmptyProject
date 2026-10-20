"""予報の取得・保存・再利用(PostgreSQL が必要)。"""
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from smdx_api.db.models import WeatherActual, WeatherForecast
from smdx_api.weather_client.service import fetch_weather_actuals, get_forecast
from tests.fakes import FailingWeatherClient, FakeWeatherClient

D16, D17 = date(2026, 10, 16), date(2026, 10, 17)


@pytest.mark.db
def test_get_forecast_saves_and_reuses_within_stale_hours(db, fixed_now):
    fake = FakeWeatherClient()
    a = get_forecast(db, fake, D16, D17, fixed_now.value, 3)
    b = get_forecast(db, fake, D16, D17, fixed_now.value + timedelta(hours=2), 3)
    c = get_forecast(db, fake, D16, D17, fixed_now.value + timedelta(hours=4), 3)
    assert fake.calls == 2
    assert a.available and a.fetched_at == fixed_now.value and len(a.rows) == 48
    assert a.fetched_at == b.fetched_at != c.fetched_at
    assert db.scalar(select(func.count()).select_from(WeatherForecast)) == 96


@pytest.mark.db
def test_reuse_needs_full_coverage(db, fixed_now):
    fake = FakeWeatherClient()
    get_forecast(db, fake, D16, D16, fixed_now.value, 3)
    # 保存済みは 10/16 だけなので、10/16〜10/17 は取り直す
    r = get_forecast(db, fake, D16, D17, fixed_now.value + timedelta(minutes=10), 3)
    assert fake.calls == 2 and len(r.rows) == 48


@pytest.mark.db
@pytest.mark.parametrize("start,end", [
    (date(2026, 11, 1), date(2026, 11, 1)),   # 16日先
    (date(2026, 10, 15), D16),                # 前日を含む
    (D17, D16),                               # 期間が逆
])
def test_get_forecast_out_of_range(db, fixed_now, start, end):
    fake = FakeWeatherClient()
    r = get_forecast(db, fake, start, end, fixed_now.value, 3)
    assert (r.available, r.fetched_at, r.rows, fake.calls) == (False, None, [], 0)


@pytest.mark.db
def test_get_forecast_last_day_in_range(db, fixed_now):
    assert get_forecast(db, FakeWeatherClient(), date(2026, 10, 31), date(2026, 10, 31), fixed_now.value, 3).available


@pytest.mark.db
def test_get_forecast_failure_is_unavailable_not_exception(db, fixed_now):
    r = get_forecast(db, FailingWeatherClient(), D16, D16, fixed_now.value, 3)
    assert r.available is False and r.rows == []


@pytest.mark.db
def test_fetch_weather_actuals_upserts(db):
    fake = FakeWeatherClient()
    assert fetch_weather_actuals(db, fake, date(2026, 10, 1), date(2026, 10, 2)) == 48
    assert fetch_weather_actuals(db, fake, date(2026, 10, 1), date(2026, 10, 2)) == 48
    assert db.scalar(select(func.count()).select_from(WeatherActual)) == 48
    assert set(db.scalars(select(WeatherActual.source))) == {"archive"}
