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
