"""予測とベースラインへの切替(詳細設計書「予測モデルのインターフェース定義」)。"""
import numpy as np
import pytest

from smdx_api.predictor.predict import (
    BASELINE_VERSION,
    TIME_BANDS_CHANGED,
    apply_inference_rules,
    baseline_values,
    predict,
)
from smdx_features.columns import sample_frame
from predictor_helpers import ConstModel, SometimesNaNModel, SpyModel, model_dict


def feats(lag, avg, granularity="daily"):
    df = sample_frame(granularity, rows=len(lag))
    df["sales_lag_7d"] = np.array(lag, dtype=float)
    df["sales_avg_7d"] = np.array(avg, dtype=float)
    return df


def test_baseline_values():
    # 前週同曜日、欠けていれば直近7日平均、両方無ければ0と「実績なし」
    assert baseline_values(feats([3.0, np.nan, np.nan], [9.0, 4.0, np.nan])) == ([3.0, 4.0, 0.0], [False, False, True])


def test_predict_uses_model_and_zero_for_no_history(registry_with):
    reg = registry_with(model_dict())
    b = predict(reg, "daily", feats([3.0, np.nan], [9.0, np.nan]), weather_available=True, current_time_bands=None)
    assert b.values == [5.0, 0.0] and b.no_history == [False, True]
    assert (b.model_version, b.is_baseline, b.notice) == ("daily-2026.11.01-1", False, None)


def test_model_gets_only_feature_columns(registry_with):
    reg = registry_with(model_dict(model=SpyModel(1.0)))
    f = feats([3.0], [3.0])
    f["target_date"] = None  # 付随列は推論器に渡さない
    predict(reg, "daily", f, weather_available=True, current_time_bands=None)
    assert SpyModel.last_columns and "target_date" not in SpyModel.last_columns


def test_negative_output_clipped(registry_with):
    reg = registry_with(model_dict(model=ConstModel(-2.0)))
    assert predict(reg, "daily", feats([3.0], [3.0]), weather_available=True, current_time_bands=None).values == [0.0]


def test_baseline_when_no_model(tmp_path):
    from smdx_api.predictor.registry import ModelRegistry

    reg = ModelRegistry({"daily": tmp_path / "none", "time_band": tmp_path / "none2"})
    b = predict(reg, "daily", feats([3.0], [9.0]), weather_available=True, current_time_bands=None)
    assert (b.values, b.model_version, b.is_baseline, b.notice) == ([3.0], BASELINE_VERSION, True, None)
    assert b.loaded_version == BASELINE_VERSION


def test_baseline_when_weather_missing(registry_with):
    b = predict(registry_with(model_dict()), "daily", feats([3.0], [9.0]), weather_available=False, current_time_bands=None)
    assert (b.values, b.model_version, b.is_baseline) == ([3.0], "baseline", True)
    # 予測はベースラインでも、読み込んでいたモデルの版は同じ予測の中で取ったものを返す(最新性判定に使う)
    assert b.loaded_version == "daily-2026.11.01-1"


def test_baseline_when_time_bands_changed(registry_with):
    reg = registry_with(model_dict("time_band"), granularity="time_band")
    b = predict(reg, "time_band", feats([2.0], [2.0], "time_band"), weather_available=True, current_time_bands=[10, 12, 16])
    assert b.is_baseline and b.values == [2.0] and b.notice == TIME_BANDS_CHANGED == "時間帯の設定が変わったため再学習が必要です"


def test_same_time_bands_uses_model(registry_with):
    reg = registry_with(model_dict("time_band"), granularity="time_band")
    b = predict(reg, "time_band", feats([2.0], [2.0], "time_band"), weather_available=True, current_time_bands=[10, 11, 14, 17])
    assert not b.is_baseline and b.values == [5.0]


def test_runtime_nan_falls_back_to_baseline(registry_with):
    reg = registry_with(model_dict(model=SometimesNaNModel(5.0)))
    b = predict(reg, "daily", feats([3.0, 4.0], [3.0, 4.0]), weather_available=True, current_time_bands=None)
    assert (b.values, b.is_baseline) == ([3.0, 4.0], True)


def test_rows_without_weather_use_baseline_row_by_row(registry_with):
    # 予報が一部の日にしか無い場合: 気象の欠けた行は中央値で埋めて推論せず、その行だけベースラインにする
    import pandas as pd

    f = feats([3.0, 4.0, 6.0], [3.0, 4.0, 6.0])
    f["weather_code"] = pd.array([1, None, 3], dtype="Int64")
    f.loc[2, "temperature"] = np.nan
    b = predict(registry_with(model_dict()), "daily", f, weather_available=True, current_time_bands=None)
    assert b.values == [5.0, 4.0, 6.0]
    assert b.row_is_baseline == [False, True, True]
    assert (b.is_baseline, b.model_version) == (False, "daily-2026.11.01-1")


def test_all_rows_without_weather_is_baseline(registry_with):
    import pandas as pd

    f = feats([3.0], [3.0])
    f["weather_code"] = pd.array([None], dtype="Int64")
    b = predict(registry_with(model_dict()), "daily", f, weather_available=True, current_time_bands=None)
    assert (b.values, b.row_is_baseline, b.is_baseline, b.model_version) == ([3.0], [True], True, "baseline")


def test_row_is_baseline_for_whole_batch_fallbacks(registry_with, tmp_path):
    b = predict(registry_with(model_dict()), "daily", feats([3.0, 4.0], [3.0, 4.0]), weather_available=False, current_time_bands=None)
    assert b.row_is_baseline == [True, True]
    ok = predict(registry_with(model_dict()), "daily", feats([3.0, 4.0], [3.0, 4.0]), weather_available=True, current_time_bands=None)
    assert ok.row_is_baseline == [False, False]


def test_time_band_predict_requires_current_time_bands(registry_with):
    # 区切りを渡さないと適合確認が飛ばされるため、呼び出しの誤りとする(PR #4 本文の軽微な課題)
    reg = registry_with(model_dict("time_band"), granularity="time_band")
    with pytest.raises(ValueError, match="時間帯の区切り"):
        predict(reg, "time_band", feats([2.0], [2.0], "time_band"), weather_available=True, current_time_bands=None)


def test_apply_inference_rules():
    # 本体の推論と同じ規則: 実績なしの行は0、気象の欠けた行はベースライン、負の値は0(学習の評価でも使う。PR #4 指摘4)
    f = feats([3.0, np.nan, 4.0, 6.0], [9.0, np.nan, 4.0, 6.0])
    f.loc[2, "temperature"] = np.nan
    values, row_is_baseline = apply_inference_rules(f, np.array([7.0, 8.0, 9.0, -1.0]))
    assert values == [7.0, 0.0, 4.0, 0.0]
    assert row_is_baseline == [False, False, True, False]
