"""推論とベースライン予測への切替。

ベースライン = sales_lag_7d(欠けていれば sales_avg_7d)。両方無い行(新商品など)はモデル・ベースラインのどちらでも0とし、
no_history として返す(呼び出し側が NO_HISTORY 警告を付ける)。
次の場合はモデルを使わずベースラインで予測する: モデルが無い・不適合、気象データが取得できない(weather_available=False)、
時間帯別モデルの time_bands が現在の設定と異なる(notice に再学習が必要な旨を入れる)、推論の出力が数値でない。
気象の列(天候コード・気温)が欠けた行は、欠損を埋めて推論せず、その行だけベースラインにする(row_is_baseline)。
予報が対象の一部の日にしか無い場合でも、残りの行はモデルで予測できる。
行ごとの規則(apply_inference_rules)は、モデル作成用プロジェクトの評価でも同じものを使う(評価の精度を運用時とそろえるため)。
時間帯別の予測では、現在の設定の時間帯の区切りを必ず渡す(渡さなければ ValueError)。
"""
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from smdx_api.predictor.loader import Granularity
from smdx_api.predictor.registry import ModelRegistry

BASELINE_VERSION = "baseline"
TIME_BANDS_CHANGED = "時間帯の設定が変わったため再学習が必要です"
WEATHER_COLUMNS = ("weather_code", "temperature")


@dataclass(frozen=True)
class PredictionBatch:
    values: list[float]
    no_history: list[bool]
    # 行ごとにベースラインで予測したか(提案の「ベースライン予測」表示と予測の版に使う)
    row_is_baseline: list[bool]
    # モデルを1行でも使えばそのモデルの版、全行ベースラインなら "baseline"
    model_version: str
    is_baseline: bool
    notice: str | None
    # 予測のときに読み込んでいたモデルの版(無ければ "baseline")。行がベースラインになったかどうかとは別
    loaded_version: str


def baseline_values(features: pd.DataFrame) -> tuple[list[float], list[bool]]:
    lag = features["sales_lag_7d"].astype(float)
    avg = features["sales_avg_7d"].astype(float)
    base = lag.where(lag.notna(), avg)
    no_history = base.isna()
    return [0.0 if nh else float(v) for v, nh in zip(base, no_history)], [bool(x) for x in no_history]


def _all_baseline(base: list[float], no_history: list[bool], loaded_version: str, notice: str | None = None) -> PredictionBatch:
    return PredictionBatch(base, no_history, [True] * len(base), BASELINE_VERSION, True, notice, loaded_version)


def missing_weather_rows(features: pd.DataFrame) -> np.ndarray:
    """気象の列(天候コード・気温)が欠けた行。"""
    return features[list(WEATHER_COLUMNS)].isna().any(axis=1).to_numpy()


def apply_inference_rules(features: pd.DataFrame, model_values: Sequence[float]) -> tuple[list[float], list[bool]]:
    """モデルの出力(行と同じ並び。気象の欠けた行の値は使わない)に、行ごとの規則を当てはめる。

    実績(sales_lag_7d・sales_avg_7d)が無い行は0、気象の欠けた行はベースライン、負の値は0。
    戻り値は (予測値, 行ごとにベースラインにしたか)。
    """
    base, no_history = baseline_values(features)
    values, row_is_baseline = [], []
    for b, nh, missing, v in zip(base, no_history, missing_weather_rows(features), model_values):
        if missing:
            values.append(b)
            row_is_baseline.append(True)
        else:
            values.append(0.0 if nh else max(0.0, float(v)))
            row_is_baseline.append(False)
    return values, row_is_baseline


def predict(
    registry: ModelRegistry,
    granularity: Granularity,
    features: pd.DataFrame,
    *,
    weather_available: bool,
    current_time_bands: Sequence[int] | None,
) -> PredictionBatch:
    if granularity == "time_band" and current_time_bands is None:
        raise ValueError("時間帯別の予測には、現在の設定の時間帯の区切りを渡してください")
    base, no_history = baseline_values(features)
    loaded = registry.get(granularity)
    loaded_version = loaded.version if loaded else BASELINE_VERSION
    if loaded is None or not weather_available or features.empty:
        return _all_baseline(base, no_history, loaded_version)
    if granularity == "time_band" and sorted(loaded.time_bands or []) != sorted(current_time_bands):
        return _all_baseline(base, no_history, loaded_version, TIME_BANDS_CHANGED)

    missing_weather = missing_weather_rows(features)
    if missing_weather.all():
        return _all_baseline(base, no_history, loaded_version)
    usable = features[~missing_weather]
    try:
        out = np.asarray(loaded.model.predict(usable[loaded.feature_columns]), dtype=float).ravel()
    except Exception:
        return _all_baseline(base, no_history, loaded_version)
    if len(out) != len(usable) or not np.isfinite(out).all():
        return _all_baseline(base, no_history, loaded_version)

    # 推論したのは気象のそろった行だけなので、行の並びに戻す(気象の欠けた行は規則でベースラインになる)
    full = np.full(len(features), np.nan)
    full[~missing_weather] = out
    values, row_is_baseline = apply_inference_rules(features, full)
    return PredictionBatch(values, no_history, row_is_baseline, loaded.version, False, None, loaded_version)
