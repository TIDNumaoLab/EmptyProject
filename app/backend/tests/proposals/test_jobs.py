"""再計算ジョブと二重実行防止(詳細設計書「二重実行防止」)。"""
import threading
from datetime import date, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from smdx_api.db.models import Proposal, ProposalJob
from smdx_api.proposals.compute_fresh import ComputeServices, FreshTargets
from smdx_api.proposals.jobs import JOB_TIMEOUT, run_job, start_or_get_job
from tests.conftest import dept, jst
from tests.fake_models import const_registry
from tests.fakes import FakeWeatherClient

DAY = date(2026, 10, 16)


def count_proposals(db) -> int:
    return db.scalar(select(func.count()).select_from(Proposal))


@pytest.mark.db
def test_start_or_get_job_dedups(db, fixed_now):
    j1, created1 = start_or_get_job(db, dept(db, "VEG"), DAY, fixed_now.value, total=6)
    j2, created2 = start_or_get_job(db, dept(db, "VEG"), DAY, fixed_now.value + timedelta(minutes=9), total=6)
    assert created1 and not created2 and j1.id == j2.id
    assert (j1.status, j1.processed, j1.total, j1.started_at) == ("running", 0, 6, fixed_now.value)
    # 部門・対象日が違えば別のジョブ
    j3, created3 = start_or_get_job(db, dept(db, "FISH"), DAY, fixed_now.value, total=1)
    j4, created4 = start_or_get_job(db, dept(db, "VEG"), DAY + timedelta(days=1), fixed_now.value, total=1)
    assert created3 and created4 and len({j1.id, j3.id, j4.id}) == 3


@pytest.mark.db
def test_stale_running_job_is_failed_and_replaced(db, fixed_now):
    j1, _ = start_or_get_job(db, dept(db, "VEG"), DAY, fixed_now.value, total=6)
    later = fixed_now.value + JOB_TIMEOUT + timedelta(seconds=1)
    j2, created = start_or_get_job(db, dept(db, "VEG"), DAY, later, total=6)
    db.refresh(j1)
    assert created and j2.id != j1.id
    assert (j1.status, j1.error, j1.finished_at) == ("failed", "タイムアウトしました", later)


@pytest.mark.db
def test_concurrent_start_creates_one_job(db_engine, fixed_now):
    """2つの別接続から同時に開始しても running の行は1件(部門の行ロックで直列にする)。
    この試験だけは別接続で commit するため、作ったジョブを最後に消す。"""
    barrier = threading.Barrier(2)
    results, errors = [], []

    def worker():
        try:
            with Session(db_engine) as s:
                d = dept(s, "VEG")
                barrier.wait()
                job, created = start_or_get_job(s, d, date(2026, 10, 30), fixed_now.value, total=3)
                results.append((job.id, created))
        except Exception as e:  # pragma: no cover - 失敗の内容を試験の結果に出す
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        assert not errors
        assert len({job_id for job_id, _ in results}) == 1 and sorted(c for _, c in results) == [False, True]
    finally:
        with Session(db_engine) as s:
            s.execute(delete(ProposalJob).where(ProposalJob.target_date == date(2026, 10, 30)))
            s.commit()


@pytest.mark.db
def test_run_job_succeeds_and_creates_proposals(db, veg_setup, job_session_factory, baseline_services, fixed_now):
    job, _ = start_or_get_job(db, dept(db, "VEG"), DAY, fixed_now.value, total=1)
    run_job(job.id, FreshTargets(None), job_session_factory, baseline_services, lambda: fixed_now.value)
    db.expire_all()
    job = db.get(ProposalJob, job.id)
    assert (job.status, job.processed, job.total, job.error) == ("succeeded", 1, 1, None)
    assert job.finished_at == fixed_now.value
    assert count_proposals(db) == 1
    p = db.scalars(select(Proposal)).one()
    assert (p.proposed_qty, p.calculated_at) == (24, fixed_now.value)


@pytest.mark.db
def test_run_job_failure_records_error(db, veg_setup, job_session_factory, tmp_path, fixed_now):
    # 推論の失敗・気象の取得失敗はベースラインに切り替わるため、想定外の例外を気象クライアントから出す
    class ExplodingWeather(FakeWeatherClient):
        def fetch_forecast(self, start, end):
            raise RuntimeError("計算の途中で失敗" + "x" * 600)

    job, _ = start_or_get_job(db, dept(db, "VEG"), DAY, fixed_now.value, total=1)
    run_job(job.id, FreshTargets(None), job_session_factory, ComputeServices(const_registry(tmp_path), ExplodingWeather()),
            lambda: fixed_now.value)
    db.expire_all()
    job = db.get(ProposalJob, job.id)
    assert job.status == "failed" and job.error == "計算中にエラーが発生しました。時間をおいて再計算してください"
    assert job.finished_at == fixed_now.value and count_proposals(db) == 0
