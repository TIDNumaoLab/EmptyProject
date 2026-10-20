from datetime import date, timedelta

import numpy as np

from smdx_sample.weather import generate_weather


def _year():
    return generate_weather(date(2026, 1, 1), date(2026, 12, 31), np.random.default_rng(42))


def test_weather_shape_and_columns():
    w = _year()
    assert len(w) == 365 * 24
    assert list(w.columns) == ["observed_time", "weather_code", "temperature", "precipitation_probability", "precipitation"]
    t = w.observed_time.iloc[0]
    assert t.utcoffset() == timedelta(hours=9) and (t.year, t.month, t.day, t.hour) == (2026, 1, 1, 0)


def test_rain_consistency():
    w = _year()
    rainy = w[w.weather_code >= 51]
    assert len(rainy) > 0 and (rainy.precipitation > 0).all()
    assert (w[w.weather_code < 51].precipitation == 0).all()
    assert (rainy.precipitation_probability >= 70).all()
    assert (w[w.weather_code < 51].precipitation_probability <= 20).all()


def test_seasonal_temperature():
    w = _year()
    jan = w[w.observed_time.dt.month == 1].temperature.mean()
    aug = w[w.observed_time.dt.month == 8].temperature.mean()
    assert aug > jan + 10


def test_reproducible_with_same_seed():
    a = generate_weather(date(2026, 1, 1), date(2026, 1, 10), np.random.default_rng(42))
    b = generate_weather(date(2026, 1, 1), date(2026, 1, 10), np.random.default_rng(42))
    assert a.equals(b)
