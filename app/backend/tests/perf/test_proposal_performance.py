"""性能(要件定義書「非機能要件」: 提案作成処理は対象20品で1分以内、既存提案の表示は2秒以内)。"""
import time
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from smdx_api.db.models import Proposal
from smdx_api.proposals.compute_fresh import ComputeServices, FreshTargets
from smdx_api.proposals.jobs import run_job, start_or_get_job
from tests.conftest import dept, jst
from tests.fake_models import forest_registry
from tests.fakes import FakeWeatherClient

CODES = [f"VEG-{i:03d}" for i in range(1, 21)]


@pytest.fixture
def twenty_products(db, product_factory, add_inventory, fixed_now):
    """VEG に20品。各70日分の日計と時刻つきの POS、当日の在庫。"""
    from smdx_api.db.models import PosSale

    fixed_now.set(jst(2026, 10, 16, 15))
    rows = []
    for n, code in enumerate(CODES):
        p = product_factory(code=code, order_unit=1 + n % 6, lead_time_days=1 + n % 2)
        for i in range(70):
            d = date(2026, 10, 15) - timedelta(days=i)
            rows.append(PosSale(sales_date=d, sales_hour=None, product_id=p.id, quantity=10 + (i + n) % 7))
            rows.append(PosSale(sales_date=d, sales_hour=12, product_id=p.id, quantity=3 + i % 3))
        add_inventory(p, jst(2026, 10, 16, 14, 30), 5 + n)
    db.add_all(rows)
    db.flush()


def count_proposals(db) -> int:
    return db.scalar(select(func.count()).select_from(Proposal))


@pytest.mark.db
def test_job_for_20_products_within_60s(db, twenty_products, job_session_factory, fixed_now, tmp_path):
    services = ComputeServices(forest_registry(tmp_path, CODES), FakeWeatherClient())
    job, _ = start_or_get_job(db, dept(db, "VEG"), fixed_now.value.date(), fixed_now.value, total=20)
    t = time.perf_counter()
    run_job(job.id, FreshTargets(None), job_session_factory, services, lambda: fixed_now.value)
    elapsed = time.perf_counter() - t
    db.expire_all()
    assert count_proposals(db) == 20 and elapsed < 60
    assert {p.basis["is_baseline"] for p in db.scalars(select(Proposal))} == {False}


@pytest.mark.db
def test_list_existing_within_2s(client, login, user_factory, twenty_products, test_services, db):
    login(client, user_factory(departments=("VEG",)))
    client.get("/api/proposals", params={"department_code": "VEG"})  # 作成(応答後のジョブ)
    assert count_proposals(db) == 20
    t = time.perf_counter()
    res = client.get("/api/proposals", params={"department_code": "VEG"})
    elapsed = time.perf_counter() - t
    assert res.status_code == 200 and len(res.json()["proposals"]) == 20 and res.json()["job"] is None
    assert elapsed < 2
