"""提案の根拠のスナップショット(proposals.basis)。JSON に保存するため、日時は ISO 8601 文字列、欠損は None にする。"""
import math
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import pandas as pd

from smdx_api.clock import JST
from smdx_api.weather_client.codes import weather_label

BASIS_KEYS = (
    "predicted_qty", "model_version", "is_baseline", "weather_code", "weather_label", "temperature", "precipitation",
    "precipitation_probability", "is_holiday", "is_event_day", "holiday_name", "is_promotion", "sales_lag_7d",
    "inventory_qty", "inventory_based_at", "backlog_qty", "carry_over_qty", "expected_sales_qty", "display_stock_qty",
    "weather_fetched_at",
)


def plain(v: Any) -> Any:
    """numpy・pandas の値を JSON にできる値へ。NaN・欠損は None。"""
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def iso(v: datetime | None) -> str | None:
    return None if v is None else v.astimezone(JST).isoformat()


def build_basis(
    *,
    features: Mapping[str, Any],
    predicted_qty: float,
    model_version: str,
    is_baseline: bool,
    precipitation_probability: float | None,
    inventory_qty: int | None,
    inventory_based_at: datetime | None,
    backlog_qty: int | None,
    carry_over_qty: float | None,
    expected_sales_qty: float | None,
    display_stock_qty: int | None,
    weather_fetched_at: datetime | None,
) -> dict[str, Any]:
    code = plain(features.get("weather_code"))
    return {
        "predicted_qty": float(predicted_qty),
        "model_version": model_version,
        "is_baseline": is_baseline,
        "weather_code": code,
        "weather_label": None if code is None else weather_label(code),
        "temperature": plain(features.get("temperature")),
        # 特徴量の precipitation は当面は降水量(mm)。画面の降水確率は予報の値を別に持つ
        "precipitation": plain(features.get("precipitation")),
        "precipitation_probability": plain(precipitation_probability),
        "is_holiday": bool(plain(features.get("is_holiday"))),
        "is_event_day": bool(plain(features.get("is_event_day"))),
        "holiday_name": plain(features.get("holiday_name")),
        "is_promotion": bool(plain(features.get("is_promotion"))),
        "sales_lag_7d": plain(features.get("sales_lag_7d")),
        "inventory_qty": inventory_qty,
        "inventory_based_at": iso(inventory_based_at),
        "backlog_qty": backlog_qty,
        "carry_over_qty": carry_over_qty,
        "expected_sales_qty": expected_sales_qty,
        "display_stock_qty": display_stock_qty,
        "weather_fetched_at": iso(weather_fetched_at),
    }
