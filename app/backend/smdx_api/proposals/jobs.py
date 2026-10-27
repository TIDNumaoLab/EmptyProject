"""再計算ジョブ(詳細設計書「二重実行防止」)。

同じ部門×対象日(生鮮の既定表示では発注日)で実行中のジョブがあれば新たに開始せず、そのジョブを返す。
開始は部門の行をロックしてから行い、同時に一覧を開いても1件しか作らない。10分を超えた実行中のジョブは失敗とみなす。
"""
from collections.abc import Callable
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from smdx_api.db.models import Department, ProposalJob
from smdx_api.proposals.compute_fresh import ComputeServices, FreshTargets, compute_fresh
from smdx_api.proposals.persist import apply_computed
from smdx_api.settings.service import load_settings

JOB_TIMEOUT = timedelta(minutes=10)
TIMED_OUT = "タイムアウトしました"
ERROR_MAX_CHARS = 500


def start_or_get_job(db: Session, department: Department, target_date: date, now: datetime, total: int) -> tuple[ProposalJob, bool]:
    """実行中のジョブを返すか、新しく開始する。2つ目の戻り値は新しく開始したか。commit する。"""
    db.execute(select(Department.id).where(Department.id == department.id).with_for_update())
    running = list(db.scalars(
        select(ProposalJob).where(ProposalJob.department_id == department.id, ProposalJob.target_date == target_date,
                                  ProposalJob.status == "running")
        .order_by(ProposalJob.started_at.desc())
    ))
    active = next((j for j in running if j.started_at >= now - JOB_TIMEOUT), None)
    if active is not None:
        db.commit()
        return active, False
    for j in running:
        j.status, j.error, j.finished_at = "failed", TIMED_OUT, now
    job = ProposalJob(department_id=department.id, target_date=target_date, status="running", processed=0, total=total,
                      started_at=now)
    db.add(job)
    db.commit()
    return job, True


def run_job(
    job_id: int,
    targets: FreshTargets,
    session_factory: sessionmaker | Callable[[], Session],
    services: ComputeServices,
    now_fn: Callable[[], datetime],
) -> None:
    """新しいセッションで計算・保存する。進捗は1件保存するたびに更新する。例外は外に出さずジョブの失敗にする。"""
    with session_factory() as db:
        job = db.get(ProposalJob, job_id)
        try:
            department = db.get(Department, job.department_id)
            now = now_fn()
            computed, _ = compute_fresh(db, department, now, load_settings(db), services, targets)
            job.total = len(computed)
            db.commit()

            def progress(n: int) -> None:
                job.processed = n
                db.commit()

            apply_computed(db, department, computed, now, on_progress=progress)
            job.status, job.finished_at = "succeeded", now_fn()
            db.commit()
        except Exception as e:
            db.rollback()
            job = db.get(ProposalJob, job_id)
            job.status, job.error, job.finished_at = "failed", str(e)[:ERROR_MAX_CHARS], now_fn()
            db.commit()
