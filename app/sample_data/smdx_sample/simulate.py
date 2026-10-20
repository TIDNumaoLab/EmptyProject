"""在庫制約下の販売・欠品・廃棄の模擬。

ベースライン(前週同曜日の販売数 × 1.1)で日々発注・製造したと仮定する(詳細設計書のサンプル仕様)。
- 生鮮: 日 d の発注数 = 入数で切り上げ(max(0, 1.1 × 販売数(d−7) − 閉店時在庫(d−1)))。前日に発注し当日の開店前に納品。
  開店時在庫 = 持越(持越可のみ)+ 納品。持越不可の売れ残りは全数廃棄。
- 惣菜: 時間帯 t の製造数 = 切り上げ(1.1 × 販売数(d−7, t))。前の時間帯の売れ残りは同じ日の次の時間帯で売れる。
  閉店時の売れ残りは全数廃棄。時間帯の販売数は多項分布でその時間帯の各時刻に割り振る。
最初の7日は前週の販売数が無いため、基準数量(惣菜は × 構成比)を使う。
"""
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from smdx_sample.products import BAND_SHARES, BUSINESS_CLOSE_HOUR, TIME_BANDS, SampleProduct, band_hours

SAFETY = 1.1
LAG_DAYS = 7


@dataclass
class SimulationResult:
    pos: pd.DataFrame        # sales_date(date), sales_time(生鮮は空), product_code, quantity
    inventory: pd.DataFrame  # based_at(YYYY-MM-DD 20:00), product_code, quantity(生鮮のみ)
    waste: pd.DataFrame      # waste_date(date), product_code, quantity(>0 のみ)
    stockout: pd.DataFrame   # date, time_band, product_code, quantity(>0 のみ)


def _ceil_to_unit(qty: float, unit: int) -> int:
    if qty <= 0:
        return 0
    return math.ceil(qty / unit - 1e-9) * unit


def _simulate_fresh(p: SampleProduct, demand: Sequence[tuple[date, int]], out: dict) -> None:
    sold: dict[date, int] = {}
    closing = 0
    for day, dem in demand:
        lag = sold.get(day - timedelta(days=LAG_DAYS), p.base_qty)
        carry = closing if p.can_carry_over else 0
        order = _ceil_to_unit(SAFETY * lag - carry, p.order_unit)
        stock = carry + order
        s = min(dem, stock)
        sold[day] = s
        leftover = stock - s
        if s > 0:
            out["pos"].append((day, "", p.code, s))
        if dem > s:
            out["stockout"].append((day, None, p.code, dem - s))
        if p.can_carry_over:
            closing = leftover
        else:
            if leftover > 0:
                out["waste"].append((day, p.code, leftover))
            closing = 0
        out["inventory"].append((f"{day.isoformat()} {BUSINESS_CLOSE_HOUR:02d}:00", p.code, closing))


def _simulate_deli(p: SampleProduct, demand: dict[date, dict[int, int]], rng: np.random.Generator, out: dict) -> None:
    sold: dict[tuple[date, int], int] = {}
    for day in sorted(demand):
        leftover = 0
        for band in TIME_BANDS:
            dem = demand[day].get(band, 0)
            lag = sold.get((day - timedelta(days=LAG_DAYS), band))
            planned = SAFETY * lag if lag is not None else p.base_qty * BAND_SHARES[p.code][band]
            produced = max(0, math.ceil(planned - 1e-9))
            available = produced + leftover
            s = min(dem, available)
            sold[(day, band)] = s
            leftover = available - s
            if dem > s:
                out["stockout"].append((day, band, p.code, dem - s))
            hours = list(band_hours(band))
            for h, q in zip(hours, rng.multinomial(s, [1 / len(hours)] * len(hours))):
                if q > 0:
                    out["pos"].append((day, f"{h:02d}:00", p.code, int(q)))
        if leftover > 0:
            out["waste"].append((day, p.code, leftover))


def simulate(true_demand: pd.DataFrame, products: Sequence[SampleProduct], rng: np.random.Generator) -> SimulationResult:
    out: dict[str, list] = {"pos": [], "inventory": [], "waste": [], "stockout": []}
    td = true_demand.sort_values(["product_code", "date", "time_band"], na_position="first")
    for p in products:
        rows = td[td.product_code == p.code]
        if p.department_code == "DELI":
            demand: dict[date, dict[int, int]] = {}
            for d, b, q in zip(rows.date, rows.time_band, rows.demand):
                demand.setdefault(d, {})[int(b)] = int(q)
            _simulate_deli(p, demand, rng, out)
        else:
            _simulate_fresh(p, [(d, int(q)) for d, q in zip(rows.date, rows.demand)], out)
    stockout = pd.DataFrame(out["stockout"], columns=["date", "time_band", "product_code", "quantity"])
    stockout["time_band"] = stockout["time_band"].astype("Int64")
    return SimulationResult(
        pos=pd.DataFrame(out["pos"], columns=["sales_date", "sales_time", "product_code", "quantity"]),
        inventory=pd.DataFrame(out["inventory"], columns=["based_at", "product_code", "quantity"]),
        waste=pd.DataFrame(out["waste"], columns=["waste_date", "product_code", "quantity"]),
        stockout=stockout,
    )
