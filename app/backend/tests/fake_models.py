"""試験用の推論器とモデルファイル(joblib で保存するため、import できるモジュールに置く)。"""
from datetime import date
from pathlib import Path

import joblib
import numpy as np

from smdx_api.predictor.registry import ModelRegistry
from smdx_features.columns import feature_columns

MODEL_VERSION = "daily-2026.11.01-1"


class ConstModel:
    """常に同じ値を返す推論器。"""

    def __init__(self, v: float) -> None:
        self.v = v

    def predict(self, X):
        return np.full(len(X), self.v, dtype=float)


class BrokenModel(ConstModel):
    """適合確認(3行)は通り、運用時は例外を出す。"""

    def predict(self, X):
        if len(X) != 3:
            raise RuntimeError("試験用の推論の失敗")
        return super().predict(X)


def empty_registry(tmp_path: Path) -> ModelRegistry:
    return ModelRegistry({"daily": tmp_path / "no-daily.joblib", "time_band": tmp_path / "no-band.joblib"})


def const_registry(tmp_path: Path, value: float = 5.0, version: str = MODEL_VERSION) -> ModelRegistry:
    path = tmp_path / "daily.joblib"
    joblib.dump({"model": ConstModel(value), "meta": {
        "version": version, "granularity": "daily", "feature_columns": feature_columns("daily"),
        "trained_from": date(2025, 9, 1), "trained_to": date(2026, 10, 31), "time_bands": None,
        "metrics": {"wape": 0.2, "mae": 1.0, "baseline_wape": 0.3},
    }}, path)
    return ModelRegistry({"daily": path, "time_band": tmp_path / "no-band.joblib"})


def forest_registry(tmp_path: Path, product_codes: list[str], version: str = MODEL_VERSION) -> ModelRegistry:
    """学習側(smdx_training)と同じ形のランダムフォレスト(300本)を、試験用の乱数データで学習して保存する。
    性能試験で、実際のモデルに近い推論時間を測るために使う。"""
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OrdinalEncoder

    from smdx_features.columns import sample_frame

    cols = feature_columns("daily")
    X = sample_frame("daily", rows=2000)[cols]
    rng = np.random.default_rng(0)
    X["product_code"] = rng.choice(product_codes, size=len(X))
    y = X["sales_lag_7d"] + rng.normal(0, 1, len(X))
    pipe = Pipeline([
        ("prep", ColumnTransformer([
            ("product", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), ["product_code"]),
            ("numeric", SimpleImputer(strategy="median"), [c for c in cols if c != "product_code"]),
        ])),
        ("model", RandomForestRegressor(n_estimators=300, random_state=0, n_jobs=-1)),
    ])
    pipe.fit(pd.DataFrame(X), y)
    path = tmp_path / "daily-forest.joblib"
    joblib.dump({"model": pipe, "meta": {
        "version": version, "granularity": "daily", "feature_columns": cols,
        "trained_from": date(2025, 9, 1), "trained_to": date(2026, 10, 31), "time_bands": None,
        "metrics": {"wape": 0.2, "mae": 1.0, "baseline_wape": 0.3},
    }}, path)
    return ModelRegistry({"daily": path, "time_band": tmp_path / "no-band.joblib"})


def band_registry(tmp_path: Path, time_bands: list[int], value: float = 5.0, version: str = "time_band-2026.11.01-1") -> ModelRegistry:
    """時間帯別の定数モデル(学習時の時間帯の区切り time_bands)と、日別はモデルなし。"""
    path = tmp_path / "time_band.joblib"
    joblib.dump({"model": ConstModel(value), "meta": {
        "version": version, "granularity": "time_band", "feature_columns": feature_columns("time_band"),
        "trained_from": date(2025, 9, 1), "trained_to": date(2026, 10, 31), "time_bands": time_bands,
        "metrics": {"wape": 0.2, "mae": 1.0, "baseline_wape": 0.3},
    }}, path)
    return ModelRegistry({"daily": tmp_path / "no-daily.joblib", "time_band": path})
