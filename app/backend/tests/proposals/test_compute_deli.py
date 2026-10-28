"""惣菜の製造計画の計算(詳細設計書「発注数・製造数の計算(惣菜)」「欠損時の扱い」「情報の時点」)。"""
from datetime import date

import pytest
from sqlalchemy import update

from smdx_api.db.models import PosSale, Setting
from smdx_api.predictor.predict import TIME_BANDS_CHANGED
from smdx_api.proposals.compute_deli import compute_deli, latest_display_stock
from smdx_api.proposals.compute_fresh import ComputeServices
from smdx_api.settings.service import load_settings
from tests.conftest import dept, jst
from tests.fake_models import band_registry
from tests.fakes import FakeWeatherClient

DAY = date(2026, 10, 16)


def run(db, now, services, target=DAY):
    return compute_deli(db, dept(db, "DELI"), now, load_settings(db), services, target)


def by_band(items, product_id):
    return {c.time_band: c for c in items if c.product_id == product_id}


@pytest.mark.db
def test_compute_deli_bands_and_baseline(db, deli_setup, fixed_now, baseline_services):
    items, notice = run(db, fixed_now.value, baseline_services)
    rows = by_band(items, deli_setup.id)
    assert sorted(rows) == [10, 11, 14, 17]
    # 前週同曜日(10/09)の時間帯の合計: 10時帯 1、11時帯 6、14時帯 3、17時帯 9 → ×1.1 を切り上げ
    assert [rows[b].qty for b in (10, 11, 14, 17)] == [2, 7, 4, 10]
    assert rows[14].deadline == jst(2026, 10, 16, 13) and rows[14].warnings == ()
    assert rows[14].target_date == DAY and rows[14].model_version == "baseline"
    basis = rows[14].basis
    assert basis["inventory_qty"] is None and basis["backlog_qty"] is None and basis["carry_over_qty"] is None
    assert basis["expected_sales_qty"] is None and basis["display_stock_qty"] == 0
    assert basis["sales_lag_7d"] == 3 and basis["is_baseline"] is True and basis["weather_label"] == "晴れ"
    assert notice is None


@pytest.mark.db
def test_display_stock_reduces_only_next_band(db, deli_setup, fixed_now, baseline_services, add_display_stock):
    add_display_stock(deli_setup, DAY, jst(2026, 10, 16, 10, 30), 3)
    fixed_now.set(jst(2026, 10, 16, 10, 40))
    rows = by_band(run(db, fixed_now.value, baseline_services)[0], deli_setup.id)
    # 11時帯は製造開始 10:00 を過ぎているので作らない
    assert sorted(rows) == [14, 17]
    # 直後の時間帯は 11時帯(締め切り済み)なので、14時帯・17時帯からは差し引かない
    assert rows[14].qty == 4 and rows[14].basis["display_stock_qty"] == 0


@pytest.mark.db
def test_display_stock_before_band(db, deli_setup, fixed_now, baseline_services, add_display_stock):
    add_display_stock(deli_setup, DAY, jst(2026, 10, 16, 12, 0), 3)
    fixed_now.set(jst(2026, 10, 16, 12, 10))
    rows = by_band(run(db, fixed_now.value, baseline_services)[0], deli_setup.id)
    assert rows[14].qty == 1 and rows[14].basis["display_stock_qty"] == 3   # ceil(3.3 − 3)
    assert rows[17].qty == 10 and rows[17].basis["display_stock_qty"] == 0


@pytest.mark.db
def test_latest_display_stock_uses_newest_entry_up_to_now(db, deli_setup, add_display_stock):
    add_display_stock(deli_setup, DAY, jst(2026, 10, 16, 11, 30), 5)
    add_display_stock(deli_setup, DAY, jst(2026, 10, 16, 12, 0), 3)
    add_display_stock(deli_setup, DAY, jst(2026, 10, 16, 12, 30), 9)        # まだ先の時刻
    add_display_stock(deli_setup, date(2026, 10, 15), jst(2026, 10, 15, 12, 40), 7)  # 別の日
    found = latest_display_stock(db, [deli_setup.id], DAY, jst(2026, 10, 16, 12, 10))
    assert found == {deli_setup.id: (3, jst(2026, 10, 16, 12, 0))}


@pytest.mark.db
def test_tomorrow_plan_has_all_bands_and_no_display_stock(db, deli_setup, fixed_now, baseline_services,
                                                          add_display_stock):
    # 前日作成は陳列残数0で全時間帯を計算する(当日の陳列残数は翌日に使わない)
    add_display_stock(deli_setup, DAY, jst(2026, 10, 16, 7, 0), 3)
    fixed_now.set(jst(2026, 10, 16, 15))
    rows = by_band(run(db, fixed_now.value, baseline_services, date(2026, 10, 17))[0], deli_setup.id)
    assert sorted(rows) == [10, 11, 14, 17]
    assert rows[10].qty == 2 and rows[10].basis["display_stock_qty"] == 0
    assert rows[10].deadline == jst(2026, 10, 17, 9)


@pytest.mark.db
def test_plan_date_is_day_before_target(db, deli_setup, fixed_now, baseline_services):
    """計画日 = 対象日 − 1、基準日 = 計画日 − 1(学習用の表と同じ)。10/16 の計画では 10/15 の POS を使わない。"""
    db.execute(update(PosSale).where(PosSale.product_id == deli_setup.id, PosSale.sales_date == date(2026, 10, 15),
                                     PosSale.sales_hour == 17).values(quantity=70))
    items, _ = run(db, fixed_now.value, baseline_services)
    rows = by_band(items, deli_setup.id)
    # 7日平均は 10/08〜10/14(基準日 10/14)の17時帯 = 9
    assert rows[17].features["sales_avg_7d"] == pytest.approx(9)


@pytest.mark.db
def test_stale_pos_is_relative_to_base_day(db, product_factory, add_pos, fixed_now, baseline_services):
    fixed_now.set(jst(2026, 10, 16, 8))
    p = product_factory(code="DELI-002", department="DELI")
    for d in (date(2026, 10, 12), date(2026, 10, 13)):
        add_pos(p, d, 2, 12)
    rows = by_band(run(db, fixed_now.value, baseline_services)[0], p.id)
    # 基準日 10/14 までの POS が無い → POS未更新
    assert all("STALE_POS" in c.warnings for c in rows.values())
    add_pos(p, date(2026, 10, 14), 2, 12)
    rows = by_band(run(db, fixed_now.value, baseline_services)[0], p.id)
    assert all("STALE_POS" not in c.warnings for c in rows.values())


@pytest.mark.db
def test_no_hourly_pos_is_no_history(db, product_factory, add_pos, fixed_now, baseline_services):
    fixed_now.set(jst(2026, 10, 16, 8))
    p = product_factory(code="DELI-003", department="DELI")
    for i in range(14):
        add_pos(p, date(2026, 10, 2 + i), 20)  # 日計だけ
    rows = by_band(run(db, fixed_now.value, baseline_services)[0], p.id)
    assert sorted(rows) == [10, 11, 14, 17]
    assert all(c.qty == 0 and c.warnings == ("NO_HISTORY",) for c in rows.values())
    # 惣菜には在庫(陳列残数)の欠損の警告を付けない
    assert all("NO_INVENTORY" not in c.warnings for c in rows.values())


@pytest.mark.db
def test_band_model_is_used_when_bands_match(db, deli_setup, fixed_now, tmp_path):
    services = ComputeServices(band_registry(tmp_path, [10, 11, 14, 17], value=5.0), FakeWeatherClient())
    items, notice = run(db, fixed_now.value, services)
    rows = by_band(items, deli_setup.id)
    assert {c.qty for c in rows.values()} == {6} and notice is None   # ceil(5 × 1.1)
    assert rows[10].model_version == "time_band-2026.11.01-1"
    assert rows[10].basis["loaded_model_version"] == "time_band-2026.11.01-1"


@pytest.mark.db
def test_time_band_setting_change_notice(db, deli_setup, fixed_now, tmp_path):
    db.add(Setting(key="deli_time_bands", value=[10, 12, 16]))
    db.flush()
    services = ComputeServices(band_registry(tmp_path, [10, 11, 14, 17]), FakeWeatherClient())
    items, notice = run(db, fixed_now.value, services)
    assert notice == TIME_BANDS_CHANGED
    assert {c.time_band for c in items} == {10, 12, 16} and all(c.model_version == "baseline" for c in items)
    # 新しい区切りの時間帯で集計する: 12時帯 = 12〜15時 = 2+2+1+1
    assert by_band(items, deli_setup.id)[12].basis["sales_lag_7d"] == 6
