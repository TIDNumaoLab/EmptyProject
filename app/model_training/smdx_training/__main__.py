"""モデル作成コマンド。

python -m smdx_training run --data DIR --granularity daily|time_band --out DIR [--departments VEG,FISH] [--seed 42]

評価レポートは常に out/report-{版}.md に出力する。ベースラインを上回るモデルがあれば out/{daily|time_band}.joblib に保存し、
無ければ既存のファイルを残して「採用しません」と表示する。
"""
import argparse
import sys
from pathlib import Path

import numpy as np

from smdx_features.columns import feature_columns
from smdx_training.backtest import run_backtest
from smdx_training.dataset import DEFAULT_DEPARTMENTS, build_training_table, load_folder, time_split
from smdx_training.evaluate import evaluate
from smdx_training.export import export_model, next_version
from smdx_training.report import write_report
from smdx_training.train import SEED, fit_candidates
from smdx_api.predictor.predict import baseline_values

TIME_BANDS = [10, 11, 14, 17]
NOT_ADOPTED = "ベースラインを上回るモデルがないため採用しません"


def _safe_console() -> None:
    """表示できない文字は ? に置き換える(UTF-8 でない端末で日本語を出しても異常終了しない)。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")


def run(args: argparse.Namespace) -> int:
    g = args.granularity
    departments = [d.strip() for d in args.departments.split(",")] if args.departments else DEFAULT_DEPARTMENTS[g]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = load_folder(Path(args.data))
    table = build_training_table(raw, g, departments, time_bands=TIME_BANDS)
    train, valid = time_split(table)
    cols = feature_columns(g)
    models = fit_candidates(train, g, seed=args.seed)
    predictions = {name: np.clip(m.predict(valid[cols]), 0, None) for name, m in models.items()}
    ev = evaluate(valid, predictions)

    demand = raw.true_demand
    backtests = {"baseline": run_backtest(valid, np.array(baseline_values(valid)[0]), demand, raw.products, g)}
    backtests.update({name: run_backtest(valid, pred, demand, raw.products, g) for name, pred in predictions.items()})

    version = next_version(g, train.target_date.max(), out)
    write_report(out / f"report-{version}.md", version=version, granularity=g,
                 train_period=(train.target_date.min(), train.target_date.max()),
                 valid_period=(valid.target_date.min(), valid.target_date.max()),
                 evaluation=ev, backtests=backtests, selected=ev.selected)
    print(f"評価レポートを出力しました: {out / f'report-{version}.md'}")
    if ev.selected is None:
        print(NOT_ADOPTED)
        return 0
    chosen = ev.candidates[ev.selected]
    metrics = {"wape": chosen["wape"], "mae": chosen["mae"], "baseline_wape": ev.baseline["wape"]}
    path = out / f"{g}.joblib"
    export_model(models[ev.selected], g, version, train.target_date.min(), train.target_date.max(),
                 TIME_BANDS if g == "time_band" else None, metrics, path)
    print(f"採用: {ev.selected}(WAPE {chosen['wape']:.3f}、ベースライン {ev.baseline['wape']:.3f})→ {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _safe_console()
    parser = argparse.ArgumentParser(prog="python -m smdx_training", description="需要予測モデルの学習・評価・バックテスト")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("run", help="学習・評価してモデルと評価レポートを出力する")
    p.add_argument("--data", required=True, help="標準取込形式のフォルダ(サンプル出力と同じ形式)")
    p.add_argument("--granularity", required=True, choices=["daily", "time_band"])
    p.add_argument("--out", required=True, help="出力先フォルダ(model_training/output など)")
    p.add_argument("--departments", default="", help="部門コード(カンマ区切り。既定: daily は VEG,FISH、time_band は DELI)")
    p.add_argument("--seed", type=int, default=SEED)
    p.set_defaults(handler=run)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return 2
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
