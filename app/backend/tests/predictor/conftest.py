"""予測の試験の fixture。推論器とモデルファイルの中身は predictor_helpers に置く。"""
from pathlib import Path

import joblib
import pytest

from smdx_api.predictor.registry import ModelRegistry


@pytest.fixture
def registry_with(tmp_path: Path):
    """obj を保存したモデルファイルを読む ModelRegistry を作る。"""

    def make(obj, granularity: str = "daily") -> ModelRegistry:
        p = tmp_path / f"{granularity}.joblib"
        joblib.dump(obj, p)
        other = "time_band" if granularity == "daily" else "daily"
        return ModelRegistry({granularity: p, other: tmp_path / "missing.joblib"})

    return make
