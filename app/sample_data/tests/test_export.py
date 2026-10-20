from datetime import date

import pandas as pd

from smdx_sample.__main__ import main
from smdx_sample.export import generate

FILES = {"products.csv", "pos_sales.csv", "inventory.csv", "waste.csv", "weather.csv",
         "calendar.csv", "promotions.csv", "true_demand.csv"}


def _header(path):
    return path.read_text(encoding="utf-8").splitlines()[0]


def test_generate_outputs_and_headers(tmp_path):
    counts = generate(date(2026, 10, 15), tmp_path, days=30)
    assert set(counts) == FILES
    assert _header(tmp_path / "products.csv") == (
        "product_code,product_name,department_code,order_unit,lead_time_days,can_carry_over,cost_price,selling_price")
    assert _header(tmp_path / "pos_sales.csv") == "sales_date,sales_time,product_code,quantity"
    assert _header(tmp_path / "inventory.csv") == "based_at,product_code,quantity"
    assert _header(tmp_path / "waste.csv") == "waste_date,product_code,quantity"
    assert _header(tmp_path / "weather.csv") == "observed_time,weather_code,temperature,precipitation_probability,precipitation"
    assert _header(tmp_path / "calendar.csv") == "date,kind,name"
    assert _header(tmp_path / "promotions.csv") == "product_code,start_date,end_date,description"
    assert _header(tmp_path / "true_demand.csv") == "date,time_band,product_code,demand"
    assert counts["weather.csv"] == 30 * 24 and counts["products.csv"] == 15
    pos = pd.read_csv(tmp_path / "pos_sales.csv", dtype=str, keep_default_na=False)
    assert pos.sales_date.min() == "2026-09-16" and pos.sales_date.max() == "2026-10-15"
    # 生鮮は日計(時刻なし)、惣菜は1時間ごとの時刻つき
    assert (pos[pos.product_code.str.startswith("VEG")].sales_time == "").all()
    assert (pos[pos.product_code.str.startswith("DELI")].sales_time != "").all()
    products = (tmp_path / "products.csv").read_text(encoding="utf-8").splitlines()
    assert products[1] == "VEG-001,キャベツ,VEG,6,1,1,98,158"
    weather = (tmp_path / "weather.csv").read_text(encoding="utf-8").splitlines()
    assert weather[1].startswith("2026-09-16 00:00,")


def test_inventory_only_fresh_at_close(tmp_path):
    generate(date(2026, 10, 15), tmp_path, days=10)
    inv = pd.read_csv(tmp_path / "inventory.csv", dtype=str)
    assert not inv.product_code.str.startswith("DELI").any()
    assert inv.based_at.str.endswith(" 20:00").all()
    assert len(inv) == 10 * 10


def test_generate_is_reproducible(tmp_path):
    generate(date(2026, 10, 15), tmp_path / "a", days=30)
    generate(date(2026, 10, 15), tmp_path / "b", days=30)
    for f in (tmp_path / "a").iterdir():
        assert f.read_bytes() == (tmp_path / "b" / f.name).read_bytes(), f.name


def test_default_days_is_400(tmp_path):
    assert generate(date(2026, 10, 15), tmp_path)["weather.csv"] == 400 * 24


def test_cli(tmp_path, capsys):
    assert main(["--out", str(tmp_path), "--end-date", "2026-10-15", "--days", "14"]) == 0
    assert (tmp_path / "true_demand.csv").exists()
    assert "weather.csv" in capsys.readouterr().out


def test_cli_does_not_crash_on_non_utf8_console(tmp_path, monkeypatch):
    import io
    import sys

    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))
    assert main(["--out", str(tmp_path), "--end-date", "2026-10-15", "--days", "3"]) == 0
