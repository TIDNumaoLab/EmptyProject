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


def test_main_without_subcommand_returns_2():
    assert main([]) == 2

