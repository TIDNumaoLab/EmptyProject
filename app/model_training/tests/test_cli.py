"""モデル作成コマンド(評価レポートは常に出力、採用モデルがあるときだけモデルファイルを保存)。"""
import dataclasses

import joblib

from smdx_api.predictor.loader import check_model_object
from smdx_training import __main__ as cli
from smdx_training.__main__ import main


def _run(sample_dir, out, granularity="daily"):
    return main(["run", "--data", str(sample_dir), "--granularity", granularity, "--out", str(out)])


def test_cli_writes_report_and_model(sample_dir, tmp_path, capsys):
    assert _run(sample_dir, tmp_path) == 0
    reports = list(tmp_path.glob("report-daily-*.md"))
    assert len(reports) == 1
    text = reports[0].read_text(encoding="utf-8")
    for heading in ["学習期間", "検証期間", "WAPE", "MAE", "ベースライン", "雨天日", "祝日・行事日", "バックテスト", "廃棄", "欠品"]:
        assert heading in text, heading
    out = capsys.readouterr().out
    model = tmp_path / "daily.joblib"
    if "採用しません" in out:
        assert not model.exists()
    else:
        assert check_model_object(joblib.load(model), "daily").version == reports[0].stem.removeprefix("report-")


def test_cli_time_band(sample_dir, tmp_path):
    assert _run(sample_dir, tmp_path, "time_band") == 0
    assert list(tmp_path.glob("report-time_band-*.md"))


def test_cli_does_not_overwrite_model_when_none_beats_baseline(sample_dir, tmp_path, monkeypatch, capsys):
    (tmp_path / "daily.joblib").write_bytes(b"old")
    real = cli.evaluate
    monkeypatch.setattr(cli, "evaluate", lambda *a, **k: dataclasses.replace(real(*a, **k), selected=None))
    assert _run(sample_dir, tmp_path) == 0
    assert (tmp_path / "daily.joblib").read_bytes() == b"old"
    assert "ベースラインを上回るモデルがないため採用しません" in capsys.readouterr().out


def test_report_notes_censored_stockout_without_true_demand(sample_dir, tmp_path):
    import shutil

    data = tmp_path / "data"
    shutil.copytree(sample_dir, data)
    (data / "true_demand.csv").unlink()
    assert _run(data, tmp_path / "out") == 0
    text = next((tmp_path / "out").glob("report-*.md")).read_text(encoding="utf-8")
    assert "欠品数は過小評価" in text


def test_report_states_demand_kind_and_rainy_definition(sample_dir, tmp_path):
    # 需要の種類、雨天の WAPE の数え方、青果の廃棄が0になる理由をレポートに明記する(PR #4 本文の軽微な課題)
    assert _run(sample_dir, tmp_path, "time_band") == 0
    text = next(tmp_path.glob("report-time_band-*.md")).read_text(encoding="utf-8")
    assert "需要: 真の需要(true_demand.csv)" in text
    assert "降水を伴う時間帯" in text
    assert _run(sample_dir, tmp_path / "d") == 0
    text = next((tmp_path / "d").glob("report-daily-*.md")).read_text(encoding="utf-8")
    assert "持越可の商品は売れ残りを翌日に持ち越すため、廃棄は0になる" in text


def test_model_predictions_follow_inference_rules():
    # 評価の予測にも本体の推論と同じ規則を当てはめる(PR #4 指摘4)
    import numpy as np

    from smdx_features.columns import feature_columns, sample_frame
    from smdx_training.__main__ import model_predictions

    class Const:
        def predict(self, X):
            return np.full(len(X), 5.0)

    valid = sample_frame("daily", rows=3)
    valid["sales_lag_7d"] = [3.0, np.nan, 4.0]
    valid["sales_avg_7d"] = [3.0, np.nan, 4.0]
    valid.loc[2, "weather_code"] = np.nan
    out = model_predictions({"m": Const()}, valid, feature_columns("daily"))
    assert out["m"].tolist() == [5.0, 0.0, 4.0]


def test_main_without_subcommand_returns_2():
    assert main([]) == 2



def test_cli_passes_store_settings(sample_dir, tmp_path, monkeypatch):
    # 店舗の設定(時間帯の区切り・営業時間・安全係数)を変えたら、それに合わせて作り直せること
    seen = {}
    real_build, real_bt, real_eval = cli.build_training_table, cli.run_backtest, cli.evaluate

    def spy_build(*a, **k):
        seen["build"] = k
        return real_build(*a, **k)

    def spy_bt(*a, **k):
        seen["safety"] = k.get("safety_factor")
        return real_bt(*a, **k)

    monkeypatch.setattr(cli, "build_training_table", spy_build)
    monkeypatch.setattr(cli, "run_backtest", spy_bt)
    monkeypatch.setattr(cli, "evaluate", lambda *a, **k: dataclasses.replace(real_eval(*a, **k), selected="lightgbm"))
    args = ["run", "--data", str(sample_dir), "--granularity", "time_band", "--out", str(tmp_path),
            "--time-bands", "10,12,16", "--business-hours", "10-20", "--safety-factor", "1.2"]
    assert main(args) == 0
    assert seen["build"]["time_bands"] == [10, 12, 16] and seen["build"]["business_hours"] == (10, 20)
    assert seen["safety"] == 1.2
    meta = joblib.load(tmp_path / "time_band.joblib")["meta"]
    assert meta["time_bands"] == [10, 12, 16]
    assert "安全係数1.2" in next(tmp_path.glob("report-*.md")).read_text(encoding="utf-8")


def test_cli_defaults_follow_design(sample_dir, tmp_path, monkeypatch):
    seen = {}
    real_build = cli.build_training_table
    monkeypatch.setattr(cli, "build_training_table", lambda *a, **k: (seen.update(k), real_build(*a, **k))[1])
    assert _run(sample_dir, tmp_path) == 0
    assert seen["time_bands"] == [10, 11, 14, 17] and seen["business_hours"] == (10, 20)


import pytest  # noqa: E402


@pytest.mark.parametrize("opt,value,msg", [
    ("--time-bands", "10,x", "時間帯の区切り"),
    ("--time-bands", "11,10", "時間帯の区切り"),
    ("--business-hours", "20-10", "営業時間"),
    ("--safety-factor", "0", "安全係数"),
])
def test_cli_rejects_bad_settings(sample_dir, tmp_path, capsys, opt, value, msg):
    with pytest.raises(SystemExit) as e:
        main(["run", "--data", str(sample_dir), "--granularity", "daily", "--out", str(tmp_path), opt, value])
    assert e.value.code == 2 and msg in capsys.readouterr().err
