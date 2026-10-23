from datetime import date

import numpy as np
import pytest

from smdx_sample.calendar import event_days, japanese_holidays
from smdx_sample.demand import demand_factor, generate_promotions, generate_true_demand
from smdx_sample.products import PRODUCTS
from smdx_sample.weather import generate_weather

BASE = dict(is_weekend=False, is_holiday_or_event=False, is_promotion=False, rainy_share=0.0, max_temp=20.0)


def _p(code):
    return next(p for p in PRODUCTS if p.code == code)


@pytest.mark.parametrize("kw,expected", [
    (dict(), 1.0),
    (dict(is_weekend=True), 1.2),
    (dict(is_weekend=True, is_holiday_or_event=True), 1.2 * 1.3),
    (dict(is_promotion=True), 1.5),
    (dict(rainy_share=1.0), 0.8),
    (dict(rainy_share=0.5), 0.9),
])
def test_demand_factor(kw, expected):
    assert demand_factor(_p("VEG-001"), date(2026, 10, 14), **(BASE | kw)) == pytest.approx(expected)


def test_temperature_effects():
    fried = next(p for p in PRODUCTS if p.temp_effect == "fried")
    hot = next(p for p in PRODUCTS if p.temp_effect == "hot_decrease")
    kw = {k: v for k, v in BASE.items() if k != "max_temp"}
    assert demand_factor(fried, date(2026, 1, 5), max_temp=5, **kw) == pytest.approx(1.15)
    assert demand_factor(fried, date(2026, 1, 5), max_temp=-20, **kw) == pytest.approx(1.2)   # 上限
    assert demand_factor(fried, date(2026, 8, 5), max_temp=40, **kw) == pytest.approx(0.85)   # 下限
    assert demand_factor(hot, date(2026, 8, 5), max_temp=35, **kw) == pytest.approx(0.8)
    assert demand_factor(hot, date(2026, 8, 5), max_temp=50, **kw) == pytest.approx(0.7)      # 下限
    assert demand_factor(hot, date(2026, 1, 5), max_temp=10, **kw) == pytest.approx(1.0)


def test_promotions_two_per_department_per_month():
    pr = generate_promotions(date(2026, 1, 1), date(2026, 3, 31), np.random.default_rng(42))
    assert list(pr.columns) == ["product_code", "start_date", "end_date", "description"]
    dept = pr.product_code.str.split("-").str[0]
    assert dept.value_counts().to_dict() == {"VEG": 6, "FISH": 6, "DELI": 6}
    assert ((pr.end_date - pr.start_date).apply(lambda d: d.days) == 2).all()
    assert (pr.start_date >= date(2026, 1, 1)).all() and (pr.end_date <= date(2026, 3, 31)).all()


def test_true_demand_granularity():
    start, end = date(2026, 10, 1), date(2026, 10, 14)
    rng = np.random.default_rng(42)
    w = generate_weather(start, end, rng)
    d = generate_true_demand(start, end, w, japanese_holidays(start, end), event_days(start, end),
                             generate_promotions(start, end, rng), rng)
    assert list(d.columns) == ["date", "time_band", "product_code", "demand"]
    deli = d[d.product_code.str.startswith("DELI")]
    fresh = d[~d.product_code.str.startswith("DELI")]
    assert set(deli.time_band.unique()) == {10, 11, 14, 17}
    assert len(deli) == 14 * 5 * 4 and len(fresh) == 14 * 10
    assert fresh.time_band.isna().all()
    assert (d.demand >= 0).all() and d.demand.dtype.kind == "i"
    # 平日・雨なし・特売なしなら基準数量の 0.85〜1.15 倍(気温効果のない商品)
    assert fresh[fresh.product_code == "VEG-001"].demand.between(20, 80).all()
