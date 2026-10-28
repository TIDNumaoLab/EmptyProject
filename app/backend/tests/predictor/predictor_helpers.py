"""予測の試験で使う推論器とモデルファイルの中身。

conftest から import すると、pytest に渡すフォルダの順によっては収集の段階で失敗するため、普通のモジュールに置く。
名前は他の試験フォルダと重ならないものにする(各試験フォルダが sys.path に加わるため)。
"""
from datetime import date

import numpy as np

from smdx_features.columns import feature_columns


class ConstModel:
    """常に同じ値を返す推論器。"""

    def __init__(self, v: float) -> None:
        self.v = v

    def predict(self, X):
        return np.full(len(X), self.v, dtype=float)


class SpyModel(ConstModel):
    """推論器に渡された列を記録する(joblib で保存するためモジュールの直下に置く)。"""

    last_columns: list[str] = []

    def predict(self, X):
        SpyModel.last_columns = list(X.columns)
        return super().predict(X)


class SometimesNaNModel(ConstModel):
    """適合確認(3行)は通り、運用時(2行)だけ NaN を返す。"""

    def predict(self, X):
        out = super().predict(X)
        if len(X) == 2:
            out[1] = np.nan
        return out


def model_dict(granularity: str = "daily", **over) -> dict:
    meta = {
        "version": f"{granularity}-2026.11.01-1",
        "granularity": granularity,
        "feature_columns": feature_columns(granularity),
        "trained_from": date(2025, 9, 1),
        "trained_to": date(2026, 10, 31),
        "time_bands": None if granularity == "daily" else [10, 11, 14, 17],
        "metrics": {"wape": 0.2, "mae": 1.0, "baseline_wape": 0.3},
    }
    meta.update(over.pop("meta", {}))
    d = {"model": ConstModel(5.0), "meta": meta}
    d.update(over)
    return d
