"""サンプルデータ一式の生成と出力。

標準取込形式(products.csv・pos_sales.csv・inventory.csv・waste.csv)と、
weather.csv・calendar.csv・promotions.csv・true_demand.csv(評価用の真の需要)を出力する。
文字コード UTF-8(BOMなし)、改行 LF。同じ終端日・日数・シードなら同じ内容になる。
"""
import csv
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from smdx_sample.calendar import event_days, japanese_holidays
from smdx_sample.demand import generate_promotions, generate_true_demand
from smdx_sample.products import PRODUCTS
from smdx_sample.simulate import simulate
from smdx_sample.weather import generate_weather

DEFAULT_DAYS = 400
DEFAULT_SEED = 42


def _num(v) -> str:
    """整数で表せる数は小数点なしで書く(98.0 → 98)。"""
    f = float(v)
    return str(int(f)) if f.is_integer() else str(f)


def _write(path: Path, header: Sequence[str], rows: Iterable[Sequence]) -> int:
    n = 0
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow(row)
            n += 1
    return n


def _iso(d) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def generate(end_date: date, out_dir: Path, *, days: int = DEFAULT_DAYS, seed: int = DEFAULT_SEED) -> dict[str, int]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    start = end_date - timedelta(days=days - 1)
    # 乱数は1つの生成器を 気象 → 特売 → 需要 → 模擬販売 の順に使う(順序を変えると再現性が崩れる)
    rng = np.random.default_rng(seed)
    weather = generate_weather(start, end_date, rng)
    promotions = generate_promotions(start, end_date, rng)
    holidays = japanese_holidays(start, end_date)
    events = event_days(start, end_date)
    demand = generate_true_demand(start, end_date, weather, holidays, events, promotions, rng)
    sim = simulate(demand, PRODUCTS, rng)

    counts = {}
    counts["products.csv"] = _write(
        out_dir / "products.csv",
        ["product_code", "product_name", "department_code", "order_unit", "lead_time_days", "can_carry_over",
         "cost_price", "selling_price"],
        [(p.code, p.name, p.department_code, p.order_unit, p.lead_time_days, int(p.can_carry_over),
          _num(p.cost_price), _num(p.selling_price)) for p in PRODUCTS],
    )
    pos = sim.pos.sort_values(["sales_date", "product_code", "sales_time"], kind="stable")
    counts["pos_sales.csv"] = _write(
        out_dir / "pos_sales.csv", ["sales_date", "sales_time", "product_code", "quantity"],
        [(_iso(d), t, c, q) for d, t, c, q in pos.itertuples(index=False)],
    )
    inv = sim.inventory.sort_values(["based_at", "product_code"], kind="stable")
    counts["inventory.csv"] = _write(out_dir / "inventory.csv", ["based_at", "product_code", "quantity"], inv.itertuples(index=False))
    waste = sim.waste.sort_values(["waste_date", "product_code"], kind="stable")
    counts["waste.csv"] = _write(
        out_dir / "waste.csv", ["waste_date", "product_code", "quantity"],
        [(_iso(d), c, q) for d, c, q in waste.itertuples(index=False)],
    )
    counts["weather.csv"] = _write(
        out_dir / "weather.csv",
        ["observed_time", "weather_code", "temperature", "precipitation_probability", "precipitation"],
        [(t.strftime("%Y-%m-%d %H:%M"), code, _num(temp), _num(prob), _num(mm))
         for t, code, temp, prob, mm in weather.itertuples(index=False)],
    )
    calendar_rows = sorted([(d.isoformat(), "holiday", n) for d, n in holidays.items()]
                           + [(d.isoformat(), "event", n) for d, n in events.items()])
    counts["calendar.csv"] = _write(out_dir / "calendar.csv", ["date", "kind", "name"], calendar_rows)
    promo = promotions.sort_values(["start_date", "product_code"], kind="stable")
    counts["promotions.csv"] = _write(
        out_dir / "promotions.csv", ["product_code", "start_date", "end_date", "description"],
        [(c, _iso(s), _iso(e), desc) for c, s, e, desc in promo.itertuples(index=False)],
    )
    counts["true_demand.csv"] = _write(
        out_dir / "true_demand.csv", ["date", "time_band", "product_code", "demand"],
        [(_iso(d), "" if pd.isna(b) else int(b), c, int(q)) for d, b, c, q in demand.itertuples(index=False)],
    )
    return counts
