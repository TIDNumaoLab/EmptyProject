"""真の需要と特売の生成。

需要 = 基準数量 × 曜日(土日1.2) × 天候(1 − 0.2 × 降水の時間の割合) × 祝日・行事日(1.3) × 特売(1.5)
       × 気温の効果 × 乱数(0.85〜1.15)
(詳細設計書「研究用サンプルデータ生成仕様」)。惣菜は時間帯ごとの構成比で配分し、天候は時間帯ごとの割合を使う。
"""
from collections.abc import Mapping
from datetime import date, timedelta

import numpy as np
import pandas as pd

from smdx_sample.products import (
    BAND_SHARES,
    BUSINESS_CLOSE_HOUR,
    BUSINESS_OPEN_HOUR,
    PRODUCTS,
    TIME_BANDS,
    SampleProduct,
    band_hours,
)

WEEKEND_FACTOR = 1.2
HOLIDAY_FACTOR = 1.3
PROMOTION_FACTOR = 1.5
RAIN_PENALTY = 0.2
NOISE_LOW, NOISE_HIGH = 0.85, 1.15
PROMOTIONS_PER_MONTH = 2
PROMOTION_DAYS = 3
RAIN_CODE_FROM = 51  # WMO コード 51 以上は降水を伴う


def demand_factor(
    product: SampleProduct,
    day: date,
    *,
    is_weekend: bool,
    is_holiday_or_event: bool,
    is_promotion: bool,
    rainy_share: float,
    max_temp: float,
) -> float:
    """乱数を除いた需要の倍率。"""
    f = 1.0
    if is_weekend:
        f *= WEEKEND_FACTOR
    if is_holiday_or_event:
        f *= HOLIDAY_FACTOR
    if is_promotion:
        f *= PROMOTION_FACTOR
    f *= 1 - RAIN_PENALTY * rainy_share
    if product.temp_effect == "fried":
        f *= min(max(1 + 0.01 * (20 - max_temp), 0.85), 1.2)
    elif product.temp_effect == "hot_decrease":
        f *= max(0.7, 1 - 0.02 * max(0.0, max_temp - 25))
    return f


def generate_promotions(start: date, end: date, rng: np.random.Generator) -> pd.DataFrame:
    """各部門で月2件、期間3日の特売・チラシ。期間は start〜end に収める。"""
    by_dept: dict[str, list[str]] = {}
    for p in PRODUCTS:
        by_dept.setdefault(p.department_code, []).append(p.code)
    rows = []
    month = date(start.year, start.month, 1)
    while month <= end:
        next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        first = max(month, start)
        last_start = min(next_month - timedelta(days=1), end) - timedelta(days=PROMOTION_DAYS - 1)
        if first <= last_start:
            span = (last_start - first).days
            for dept, codes in by_dept.items():
                for _ in range(PROMOTIONS_PER_MONTH):
                    s = first + timedelta(days=int(rng.integers(0, span + 1)))
                    code = codes[int(rng.integers(0, len(codes)))]
                    rows.append((code, s, s + timedelta(days=PROMOTION_DAYS - 1), "チラシ特売"))
        month = next_month
    return pd.DataFrame(rows, columns=["product_code", "start_date", "end_date", "description"])


def _hourly_by_day(weather: pd.DataFrame) -> dict[date, pd.DataFrame]:
    w = weather.assign(_day=weather.observed_time.dt.date, _hour=weather.observed_time.dt.hour)
    return {d: g.set_index("_hour") for d, g in w.groupby("_day")}


def _rainy_share(day_weather: pd.DataFrame, hours: range) -> float:
    codes = day_weather.weather_code.reindex(list(hours)).dropna()
    return float((codes >= RAIN_CODE_FROM).mean()) if len(codes) else 0.0


def generate_true_demand(
    start: date,
    end: date,
    weather: pd.DataFrame,
    holidays: Mapping[date, str],
    events: Mapping[date, str],
    promotions: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """列 date, time_band, product_code, demand。生鮮は time_band 空の日別、惣菜は時間帯別。"""
    by_day = _hourly_by_day(weather)
    business = range(BUSINESS_OPEN_HOUR, BUSINESS_CLOSE_HOUR)
    rows = []
    day = start
    while day <= end:
        dw = by_day[day]
        temps = dw.temperature.reindex(list(business)).dropna()
        max_temp = float(temps.max()) if len(temps) else 20.0
        common = dict(is_weekend=day.weekday() >= 5, is_holiday_or_event=day in holidays or day in events)
        for p in PRODUCTS:
            promo = bool(((promotions.product_code == p.code) & (promotions.start_date <= day) & (promotions.end_date >= day)).any())
            noise = rng.uniform(NOISE_LOW, NOISE_HIGH)
            if p.department_code == "DELI":
                for band in TIME_BANDS:
                    f = demand_factor(p, day, is_promotion=promo, rainy_share=_rainy_share(dw, band_hours(band)),
                                      max_temp=max_temp, **common)
                    rows.append((day, band, p.code, int(round(p.base_qty * BAND_SHARES[p.code][band] * f * noise))))
            else:
                f = demand_factor(p, day, is_promotion=promo, rainy_share=_rainy_share(dw, business), max_temp=max_temp, **common)
                rows.append((day, None, p.code, int(round(p.base_qty * f * noise))))
        day += timedelta(days=1)
    df = pd.DataFrame(rows, columns=["date", "time_band", "product_code", "demand"])
    df["time_band"] = df["time_band"].astype("Int64")
    df["demand"] = df["demand"].astype("int64")
    return df
