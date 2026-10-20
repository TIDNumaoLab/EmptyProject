from datetime import date, timedelta

import numpy as np
import pandas as pd

from smdx_sample.products import PRODUCTS
from smdx_sample.simulate import simulate

D0 = date(2026, 10, 1)


def _fresh_demand(code: str, demands: list[int]) -> pd.DataFrame:
    df = pd.DataFrame({
        "date": [D0 + timedelta(days=i) for i in range(len(demands))],
        "time_band": pd.array([None] * len(demands), dtype="Int64"),
        "product_code": code,
        "demand": demands,
    })
    return df


def _products(*codes):
    return [p for p in PRODUCTS if p.code in codes]


def _by_day(df: pd.DataFrame, col: str, date_col: str, code: str) -> dict:
    sub = df[df.product_code == code]
    return dict(zip(sub[date_col], sub[col]))


def test_fresh_no_carry_waste_is_leftover():
    # FISH-001: 入数1・持越不可・基準数量25。最初の7日は 1.1×25 → 28 発注、8日目以降は 1.1×10 → 11 発注
    r = simulate(_fresh_demand("FISH-001", [10] * 10), _products("FISH-001"), np.random.default_rng(0))
    waste = _by_day(r.waste, "quantity", "waste_date", "FISH-001")
    assert [waste[D0 + timedelta(days=i)] for i in range(10)] == [18] * 7 + [1] * 3
    sold = _by_day(r.pos, "quantity", "sales_date", "FISH-001")
    assert all(v == 10 for v in sold.values()) and len(sold) == 10
    inv = r.inventory[r.inventory.product_code == "FISH-001"]
    assert len(inv) == 10 and (inv.quantity == 0).all()        # 持越不可は閉店時在庫0
    assert inv.based_at.iloc[0] == "2026-10-01 20:00"
    assert r.stockout.empty


def test_fresh_carry_over_reduces_order():
    # VEG-001: 入数6・持越可・基準数量40、需要30
    # 1〜7日目: 1.1×40=44 − 閉店時在庫 → 1日目 48 発注(在庫18)、以降 44−18=26 → 30 発注(在庫18)
    # 8日目以降: 1.1×30=33 − 18 = 15 → 18 発注(在庫6)、9日目 33−6=27 → 30 発注(在庫6)
    r = simulate(_fresh_demand("VEG-001", [30] * 10), _products("VEG-001"), np.random.default_rng(0))
    inv = _by_day(r.inventory, "quantity", "based_at", "VEG-001")
    assert inv["2026-10-01 20:00"] == 18 and inv["2026-10-07 20:00"] == 18
    assert inv["2026-10-08 20:00"] == 6 and inv["2026-10-10 20:00"] == 6
    assert r.waste[r.waste.product_code == "VEG-001"].empty


def test_stockout_when_demand_exceeds_stock():
    r = simulate(_fresh_demand("FISH-001", [10] * 7 + [50]), _products("FISH-001"), np.random.default_rng(0))
    day8 = D0 + timedelta(days=7)
    assert _by_day(r.pos, "quantity", "sales_date", "FISH-001")[day8] == 11
    so = r.stockout[r.stockout.product_code == "FISH-001"]
    assert list(zip(so.date, so.quantity)) == [(day8, 39)]


def test_deli_hourly_pos_sums_to_band_sales():
    days = [D0, D0 + timedelta(days=1)]
    rows = [(d, b, "DELI-001", q) for d in days for b, q in [(10, 3), (11, 12), (14, 6), (17, 15)]]
    td = pd.DataFrame(rows, columns=["date", "time_band", "product_code", "demand"])
    td["time_band"] = td["time_band"].astype("Int64")
    r = simulate(td, _products("DELI-001"), np.random.default_rng(0))
    pos = r.pos[r.pos.product_code == "DELI-001"]
    hours = pos.sales_time.str[:2].astype(int)
    assert set(pos.sales_time.str[2:]) == {":00"} and hours.between(10, 19).all()
    # 最初の7日は 基準数量40 × 構成比 を切り上げて製造(10時帯 4、11時帯 12、14時帯 8、17時帯 16)→ 需要をすべて満たす
    first = pos[pos.sales_date == D0]
    band = hours[first.index].map(lambda h: 10 if h < 11 else 11 if h < 14 else 14 if h < 17 else 17)
    assert first.groupby(band.values).quantity.sum().to_dict() == {10: 3, 11: 12, 14: 6, 17: 15}
    # 前の時間帯の売れ残りは次の時間帯で売れ、閉店時の残りは全数廃棄: 製造40 − 販売36 = 4
    assert _by_day(r.waste, "quantity", "waste_date", "DELI-001")[D0] == 4
