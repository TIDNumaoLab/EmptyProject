"""生鮮の提案の計算(詳細設計書「処理の流れ」「発注数・製造数の計算(生鮮)」「欠損時の扱い」)。

数値は計算式から手で求めた値。ベースライン = 前週同曜日(無ければ7日平均)。
"""
from datetime import date, timedelta

import pytest

from smdx_api.proposals.compute_fresh import ComputeServices, FreshTargets, compute_fresh, fresh_target_dates
from smdx_api.settings.service import load_settings
from tests.conftest import dept, jst, one
from tests.fake_models import MODEL_VERSION, const_registry
from tests.fakes import FailingWeatherClient


def run(db, now, services, targets=FreshTargets(None), code="VEG"):
    return compute_fresh(db, dept(db, code), now, load_settings(db), services, targets)


@pytest.mark.db
def test_compute_fresh_design_flow(db, veg_setup, fixed_now, baseline_services):
    items, notice = run(db, fixed_now.value, baseline_services)
    c = one(items, "VEG-001")
    assert c.target_date == date(2026, 10, 17) and c.deadline == jst(2026, 10, 16, 20) and c.time_band is None
    # 対象日 10/17 の予測 = 前週同曜日 10/10 の 20、当日 10/16 の予測 = 10/09 の 10
    # 残り営業時間比 (20−14.5)/10 = 0.55 → 販売見込 5.5、持越見込 8 − 5.5 = 2.5、必要数 22 → 19.5 → 入数6で 24
    assert c.qty == 24 and c.warnings == ()
    assert c.predicted_qty == pytest.approx(20)
    assert c.basis["carry_over_qty"] == pytest.approx(2.5) and c.basis["expected_sales_qty"] == pytest.approx(5.5)
    assert c.basis["inventory_qty"] == 8 and c.basis["inventory_based_at"] == "2026-10-16T14:30:00+09:00"
    assert c.basis["backlog_qty"] == 0 and c.basis["sales_lag_7d"] == pytest.approx(20)
    assert c.model_version == "baseline" and c.basis["is_baseline"] is True and notice is None
    assert c.weather_fetched_at == fixed_now.value and c.basis["weather_label"] == "晴れ"
    assert c.basis["weather_code"] == 1 and c.basis["temperature"] == pytest.approx(20.0)
    assert c.basis["precipitation_probability"] == pytest.approx(10.0)


@pytest.mark.db
def test_uses_model_when_weather_available(db, veg_setup, fixed_now, tmp_path):
    services = ComputeServices(const_registry(tmp_path, 5.0), baseline_services_weather())
    c = one(run(db, fixed_now.value, services)[0], "VEG-001")
    # 予測はすべて5: 販売見込 5 × 0.55 = 2.75、持越見込 5.25、必要数 5.5 → 0.25 → 6
    assert c.model_version == MODEL_VERSION and c.basis["is_baseline"] is False
    assert c.qty == 6 and c.predicted_qty == pytest.approx(5)


def baseline_services_weather():
    from tests.fakes import FakeWeatherClient
    return FakeWeatherClient()


@pytest.mark.db
def test_hourly_sales_ratio_used_for_remaining(db, veg_setup, fixed_now, baseline_services, add_pos):
    # 前週の金曜(10/09)の時刻つき POS: 10時に 6、15時に 4 → 14:30 以降の比率 = 15時の 0.4
    add_pos(veg_setup, date(2026, 10, 9), 6, hour=10)
    add_pos(veg_setup, date(2026, 10, 9), 4, hour=15)
    c = one(run(db, fixed_now.value, baseline_services)[0], "VEG-001")
    # 10/09 の日計は 10 + 時刻つき 10 = 20 → 当日の予測 20 × 0.4 = 8、持越見込0、必要数 22 → 24
    assert c.basis["expected_sales_qty"] == pytest.approx(8) and c.qty == 24


@pytest.mark.db
def test_no_inventory_warning(db, product_factory, add_pos, fixed_now, baseline_services):
    fixed_now.set(jst(2026, 10, 16, 15))
    p = product_factory(code="VEG-001", order_unit=1)
    for i in range(14):
        add_pos(p, date(2026, 10, 2) + timedelta(days=i), 10)
    c = one(run(db, fixed_now.value, baseline_services)[0], "VEG-001")
    assert c.warnings == ("NO_INVENTORY",)
    assert c.qty == 11 and c.basis["inventory_qty"] is None and c.basis["carry_over_qty"] == 0


@pytest.mark.db
def test_no_weather_warning_and_baseline(db, veg_setup, fixed_now, tmp_path):
    services = ComputeServices(const_registry(tmp_path), FailingWeatherClient())
    c = one(run(db, fixed_now.value, services)[0], "VEG-001")
    assert "NO_WEATHER" in c.warnings and c.model_version == "baseline" and c.weather_fetched_at is None
    assert c.qty == 24 and c.basis["weather_code"] is None and c.basis["weather_fetched_at"] is None


@pytest.mark.db
def test_stale_pos_uses_latest_pos_day(db, product_factory, add_pos, add_inventory, fixed_now, baseline_services):
    fixed_now.set(jst(2026, 10, 16, 15))
    p = product_factory(code="VEG-001")
    for i in range(13):  # 10/02〜10/14(10/15 が未取込)
        d = date(2026, 10, 2) + timedelta(days=i)
        add_pos(p, d, 20 if d == date(2026, 10, 10) else 10)
    add_inventory(p, jst(2026, 10, 16, 14, 30), 8)
    c = one(run(db, fixed_now.value, baseline_services)[0], "VEG-001")
    assert c.warnings == ("STALE_POS",)
    # 基準日が 10/14 になる(10/15 を売上0とみなさない)
    assert c.features["sales_avg_7d"] == pytest.approx(80 / 7)


@pytest.mark.db
def test_missing_import_day_is_not_zero(db, product_factory, add_pos, add_inventory, fixed_now, baseline_services):
    # 10/12 に部門の POS が1行も無い(未取込日)→ 7日平均から除く
    fixed_now.set(jst(2026, 10, 16, 15))
    p = product_factory(code="VEG-001")
    for i in range(14):
        d = date(2026, 10, 2) + timedelta(days=i)
        if d != date(2026, 10, 12):
            add_pos(p, d, 10)
    add_inventory(p, jst(2026, 10, 16, 14, 30), 8)
    c = one(run(db, fixed_now.value, baseline_services)[0], "VEG-001")
    assert c.features["sales_avg_7d"] == pytest.approx(10) and c.warnings == ()


@pytest.mark.db
def test_new_product_no_history(db, veg_setup, product_factory, add_inventory, fixed_now, baseline_services):
    p = product_factory(code="VEG-099")
    add_inventory(p, jst(2026, 10, 16, 14), 0)
    c = one(run(db, fixed_now.value, baseline_services)[0], "VEG-099")
    assert c.qty == 0 and c.warnings == ("NO_HISTORY",) and c.predicted_qty == 0


@pytest.mark.db
def test_inactive_and_other_department_excluded(db, veg_setup, product_factory, fixed_now, baseline_services):
    product_factory(code="VEG-090", is_active=False)
    product_factory(code="FISH-001", department="FISH")
    items, _ = run(db, fixed_now.value, baseline_services)
    assert [c.product_code for c in items] == ["VEG-001"]


@pytest.mark.db
def test_lead_time_2_has_middle_day(db, product_factory, add_pos, add_inventory, fixed_now, baseline_services):
    fixed_now.set(jst(2026, 10, 16, 15))
    p = product_factory(code="VEG-002", lead_time_days=2)
    for i in range(14):
        d = date(2026, 10, 2) + timedelta(days=i)
        add_pos(p, d, 20 if d == date(2026, 10, 10) else 10)
    add_inventory(p, jst(2026, 10, 16, 14, 30), 30)
    c = one(run(db, fixed_now.value, baseline_services)[0], "VEG-002")
    assert c.target_date == date(2026, 10, 18) and c.deadline == jst(2026, 10, 16, 20)
    # 当日 10 × 0.55 + 途中の日 10/17(前週 10/10 の 20)= 25.5、持越見込 4.5、必要数 10/18(前週 10/11 の 10)× 1.1 = 11 → 7
    assert c.basis["expected_sales_qty"] == pytest.approx(25.5) and c.qty == 7


@pytest.mark.db
def test_backlog_included_in_carry_over(db, veg_setup, fixed_now, baseline_services, proposal_factory):
    # LT1 の商品で、明日(10/17)向けの確定分は対象日(10/17)より前ではないので入らない。10/16 納品(在庫基準より前)も入らない
    proposal_factory(veg_setup, target=date(2026, 10, 16), qty=30, status="confirmed")
    c = one(run(db, fixed_now.value, baseline_services)[0], "VEG-001")
    assert c.basis["backlog_qty"] == 0 and c.qty == 24


@pytest.mark.db
def test_explicit_target_date(db, veg_setup, fixed_now, baseline_services):
    items, _ = run(db, fixed_now.value, baseline_services, FreshTargets(date(2026, 10, 20)))
    c = one(items, "VEG-001")
    assert c.target_date == date(2026, 10, 20) and c.deadline == jst(2026, 10, 19, 20)
    assert c.warnings == ()


@pytest.mark.db
def test_after_cutoff_moves_to_next_day(db, veg_setup, fixed_now, baseline_services):
    fixed_now.set(jst(2026, 10, 16, 20))
    c = one(run(db, fixed_now.value, baseline_services)[0], "VEG-001")
    assert c.target_date == date(2026, 10, 18) and c.deadline == jst(2026, 10, 17, 20)


@pytest.mark.db
def test_jst_after_midnight_uses_today_inventory(db, veg_setup, add_inventory, fixed_now, baseline_services):
    # 0:30(UTC では前日)。当日 0:10 の在庫を使い、対象日は 10/17
    fixed_now.set(jst(2026, 10, 16, 0, 30))
    add_inventory(veg_setup, jst(2026, 10, 16, 0, 10), 5)
    c = one(run(db, fixed_now.value, baseline_services)[0], "VEG-001")
    assert c.target_date == date(2026, 10, 17) and c.basis["inventory_qty"] == 5
    assert "NO_INVENTORY" not in c.warnings


@pytest.mark.db
def test_fresh_target_dates(db, veg_setup, product_factory, fixed_now):
    p2 = product_factory(code="VEG-002", lead_time_days=3)
    products = [veg_setup, p2]
    s = load_settings(db)
    assert fresh_target_dates(products, fixed_now.value, s, FreshTargets(None)) == {
        veg_setup.id: date(2026, 10, 17), p2.id: date(2026, 10, 19)}
    # 対象日を指定: 最も早い納品日がその日以前の商品だけ
    assert fresh_target_dates(products, fixed_now.value, s, FreshTargets(date(2026, 10, 18))) == {veg_setup.id: date(2026, 10, 18)}
