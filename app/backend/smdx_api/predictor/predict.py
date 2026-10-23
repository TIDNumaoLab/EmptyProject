"""推論とベースライン予測への切替。

ベースライン = sales_lag_7d(欠けていれば sales_avg_7d)。両方無い行(新商品など)はモデル・ベースラインのどちらでも0とし、
no_history として返す(呼び出し側が NO_HISTORY 警告を付ける)。
次の場合はモデルを使わずベースラインで予測する: モデルが無い・不適合、気象データが取得できない、
時間帯別モデルの time_bands が現在の設定と異なる(notice に再学習が必要な旨を入れる)、推論の出力が数値でない。
"""
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from smdx_api.predictor.loader import Granularity
from smdx_api.predictor.registry import ModelRegistry

BASELINE_VERSION = "baseline"
TIME_BANDS_CHANGED = "時間帯の設定が変わったため再学習が必要です"


@dataclass(frozen=True)
class PredictionBatch:
    values: list[float]
    no_history: list[bool]
    model_version: str
    is_baseline: bool
    notice: str | None


def baseline_values(features: pd.DataFrame) -> tuple[list[float], list[bool]]:
    lag = features["sales_lag_7d"].astype(float)
    avg = features["sales_avg_7d"].astype(float)
    base = lag.where(lag.notna(), avg)
    no_history = base.isna()
    return [0.0 if nh else float(v) for v, nh in zip(base, no_history)], [bool(x) for x in no_history]


def predict(
    registry: ModelRegistry,
    granularity: Granularity,
    features: pd.DataFrame,
    *,
    weather_available: bool,
    current_time_bands: Sequence[int] | None,
) -> PredictionBatch:
    base, no_history = baseline_values(features)
    baseline = PredictionBatch(base, no_history, BASELINE_VERSION, True, None)
    loaded = registry.get(granularity)
    if loaded is None or not weather_available or features.empty:
        return baseline
    if granularity == "time_band" and current_time_bands is not None and sorted(loaded.time_bands or []) != sorted(current_time_bands):
        return PredictionBatch(base, no_history, BASELINE_VERSION, True, TIME_BANDS_CHANGED)
    try:
        out = np.asarray(loaded.model.predict(features[loaded.feature_columns]), dtype=float).ravel()
    except Exception:
        return baseline
    if len(out) != len(features) or not np.isfinite(out).all():
        return baseline
    values = [0.0 if nh else max(0.0, float(v)) for v, nh in zip(out, no_history)]
    return PredictionBatch(values, no_history, loaded.version, False, None)
