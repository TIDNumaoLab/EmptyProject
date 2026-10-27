"""自動再計算の判定とジョブの対象日(詳細設計書「自動再計算の対象と判定」「二重実行防止」)。"""
from datetime import date, timedelta

import pytest

from smdx_api.db.models import ImportLog, InventorySnapshot
from smdx_api.proposals.compute_fresh import ComputeServices, FreshTargets, compute_fresh
from smdx_api.proposals.persist import apply_computed
from smdx_api.proposals.service import job_target_date, needs_auto_recalc
from smdx_api.settings.service import EVENTS_CHANGED_KEY, load_settings, touch_internal
from tests.conftest import dept, jst
from tests.fake_models import const_registry


def create_all(db, services, now, targets=FreshTargets(None)):
    veg = dept(db, "VEG")
    items, _ = compute_fresh(db, veg, now, load_settings(db), services, targets)
    apply_computed(db, veg, items, now)


def needs(db, services, now, targets=FreshTargets(None)):
    return needs_auto_recalc(db, dept(db, "VEG"), now, load_settings(db), services, targets)


@pytest.mark.db
def test_job_target_date(db, fixed_now):
    s, veg = load_settings(db), dept(db, "VEG")
    assert job_target_date(veg, jst(2026, 10, 16, 19, 59), s, FreshTargets(None)) == date(2026, 10, 16)
    # 締め時刻以後の最も早い納品日に向けた発注日は翌日
    assert job_target_date(veg, jst(2026, 10, 16, 20), s, FreshTargets(None)) == date(2026, 10, 17)
    assert job_target_date(veg, jst(2026, 10, 16, 10), s, FreshTargets(date(2026, 10, 20))) == date(2026, 10, 20)


@pytest.mark.db
def test_needs_auto_recalc_when_missing_then_fresh(db, veg_setup, baseline_services, fixed_now, product_factory):
    now = fixed_now.value
    assert needs(db, baseline_services, now)                     # 未作成
    create_all(db, baseline_services, now)
    assert not needs(db, baseline_services, now + timedelta(hours=1))
    product_factory(code="VEG-002")                              # 新しい商品の提案が未作成
    assert needs(db, baseline_services, now + timedelta(hours=1))


@pytest.mark.db
def test_needs_auto_recalc_on_data_change(db, veg_setup, baseline_services, fixed_now):
    now = fixed_now.value
    create_all(db, baseline_services, now)
    db.add(InventorySnapshot(based_at=jst(2026, 10, 16, 15, 30), product_id=veg_setup.id, quantity=3, source="manual",
                             updated_at=now + timedelta(minutes=30)))
    db.flush()
    assert needs(db, baseline_services, now + timedelta(hours=1))


@pytest.mark.db
def test_needs_auto_recalc_on_pos_import_and_events(db, veg_setup, baseline_services, fixed_now):
    now = fixed_now.value
    create_all(db, baseline_services, now)
    touch_internal(db, EVENTS_CHANGED_KEY, now + timedelta(minutes=5))
    assert needs(db, baseline_services, now + timedelta(hours=1))
    create_all(db, baseline_services, now + timedelta(hours=1))
    db.add(ImportLog(kind="pos", department_id=dept(db, "VEG").id, file_name="p.csv", imported_count=1,
                     skipped_count=0, errors=[], finished_at=now + timedelta(hours=1, minutes=1)))
    db.flush()
    assert needs(db, baseline_services, now + timedelta(hours=2))


@pytest.mark.db
def test_needs_auto_recalc_on_weather_age_and_model_change(db, veg_setup, baseline_services, fixed_now, tmp_path):
    now = fixed_now.value
    create_all(db, baseline_services, now)
    assert needs(db, baseline_services, now + timedelta(hours=3))   # 予報の取得から3時間
    model = ComputeServices(const_registry(tmp_path), baseline_services.weather_client)
    assert needs(db, model, now + timedelta(hours=1))               # モデルの版が変わった


@pytest.mark.db
def test_adjusted_or_approved_do_not_trigger(db, veg_setup, baseline_services, fixed_now):
    from sqlalchemy import select

    from smdx_api.db.models import Proposal

    now = fixed_now.value
    create_all(db, baseline_services, now)
    p = db.scalars(select(Proposal)).one()
    p.is_adjusted = True
    db.flush()
    # 修正ありだけが古い → 自動では再計算しない
    assert not needs(db, baseline_services, now + timedelta(hours=4))
    p.is_adjusted, p.status = False, "approved"
    db.flush()
    assert not needs(db, baseline_services, now + timedelta(hours=4))


@pytest.mark.db
def test_needs_auto_recalc_explicit_date(db, veg_setup, baseline_services, fixed_now):
    now = fixed_now.value
    create_all(db, baseline_services, now)
    # 既定表示の提案(10/17)はあるが、10/20 の提案は未作成
    assert needs(db, baseline_services, now, FreshTargets(date(2026, 10, 20)))
    create_all(db, baseline_services, now, FreshTargets(date(2026, 10, 20)))
    assert not needs(db, baseline_services, now, FreshTargets(date(2026, 10, 20)))


@pytest.mark.db
def test_no_weather_proposal_does_not_retrigger_immediately(db, veg_setup, fixed_now, tmp_path):
    """予報が取れずに作った提案を、作った直後に「古い」と判定し続けない(再計算が止まらなくなるため)。"""
    from tests.fakes import FailingWeatherClient

    now = fixed_now.value
    services = ComputeServices(const_registry(tmp_path), FailingWeatherClient())
    create_all(db, services, now)
    assert not needs(db, services, now + timedelta(minutes=1))
    # 判定時間が過ぎたら取り直す
    assert needs(db, services, now + timedelta(hours=3))


@pytest.mark.db
def test_row_baseline_with_loaded_model_is_not_model_change(db, veg_setup, fixed_now, tmp_path):
    """モデルを読み込んでいても行がベースラインで予測された提案は、モデルの版の変更とみなさない。"""
    from smdx_api.db.models import Proposal
    from sqlalchemy import select

    now = fixed_now.value
    services = ComputeServices(const_registry(tmp_path), baseline_services_weather())
    create_all(db, services, now)
    p = db.scalars(select(Proposal)).one()
    p.basis = {**p.basis, "model_version": "baseline"}  # 対象日の行だけ気象が欠けてベースラインになった場合
    db.flush()
    assert not needs(db, services, now + timedelta(minutes=1))


def baseline_services_weather():
    from tests.fakes import FakeWeatherClient
    return FakeWeatherClient()
