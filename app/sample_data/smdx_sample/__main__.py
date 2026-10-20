"""サンプルデータの生成コマンド。

python -m smdx_sample --out output/ [--end-date YYYY-MM-DD] [--days 400] [--seed 42]
終端日の既定は実行日(日本時間)の前日。
"""
import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from smdx_sample.export import DEFAULT_DAYS, DEFAULT_SEED, generate
from smdx_sample.tz import JST


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m smdx_sample", description="研究用サンプルデータを生成する")
    parser.add_argument("--out", required=True, type=Path, help="出力先フォルダ")
    parser.add_argument("--end-date", type=date.fromisoformat, help="期間の終端日(既定は実行日の前日)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"日数(既定 {DEFAULT_DAYS})")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"乱数シード(既定 {DEFAULT_SEED})")
    args = parser.parse_args(argv)
    end = args.end_date or (datetime.now(JST).date() - timedelta(days=1))
    counts = generate(end, args.out, days=args.days, seed=args.seed)
    print(f"出力しました: {args.out}(期間の終端日 {end.isoformat()}、{args.days}日)")
    for name, n in counts.items():
        print(f"  {name}: {n}行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
