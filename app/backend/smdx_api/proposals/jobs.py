"""再計算ジョブ(詳細設計書「二重実行防止」)。

同じ部門×種別×対象日(既定表示では発注日、対象日の指定では納品日)で実行中のジョブがあれば新たに開始せず、そのジョブを返す。
開始は部門の行をロックしてから行い、同時に一覧を開いても1件しか作らない。10分を超えた実行中のジョブは失敗とみなす。
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from smdx_api.db.models import Department, ProposalJob
from smdx_api.proposals.compute_fresh import ComputeServices, FreshTargets, compute_fresh
from smdx_api.proposals.persist import apply_computed
from smdx_api.settings.service import load_settings

log = logging.getLogger(__name__)

JOB_TIMEOUT = timedelta(minutes=10)
TIMED_OUT = "タイムアウトしました"
JOB_FAILED = "計算中にエラーが発生しました。時間をおいて再計算してください"


@dataclass(frozen=True)
class JobKey:
    """ジョブを区別する種別と日付。同じ日付でも、発注日(既定表示)と納品日(対象日の指定)では計算する提案が違う。"""
    scope: Literal["default", "date"]
    target_date: date


def start_or_get_job(db: Session, department: Department, key: JobKey, now: datetime, total: int) -> tuple[ProposalJob, bool]:
    """実行中のジョブを返すか、新しく開始する。2つ目の戻り値は新しく開始したか。commit する。"""
    db.execute(select(Department.id).where(Department.id == department.id).with_for_update())
    running = list(db.scalars(
        select(ProposalJob).where(ProposalJob.department_id == department.id, ProposalJob.scope == key.scope,
                                  ProposalJob.target_date == key.target_date, ProposalJob.status == "running")
        .order_by(ProposalJob.started_at.desc())
    ))
    active = next((j for j in running if j.started_at >= now - JOB_TIMEOUT), None)
    if active is not None:
        db.commit()
        return active, False
    for j in running:
        j.status, j.error, j.finished_at = "failed", TIMED_OUT, now
    job = ProposalJob(department_id=department.id, scope=key.scope, target_date=key.target_date, status="running",
                      processed=0, total=total, started_at=now)
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
            computed, notice = compute_fresh(db, department, now, load_settings(db), services, targets)
            job.total, job.notice = len(computed), notice
            db.commit()

            def progress(n: int) -> None:
                job.processed = n
                db.commit()

            apply_computed(db, department, computed, now, on_progress=progress)
            job.status, job.finished_at = "succeeded", now_fn()
            db.commit()
        except Exception:
            # 例外の文言(SQL など)は画面に出さず、ログにだけ残す
            log.exception("提案の再計算ジョブが失敗しました: job_id=%s", job_id)
            db.rollback()
            job = db.get(ProposalJob, job_id)
            job.status, job.error, job.finished_at = "failed", JOB_FAILED, now_fn()
            db.commit()
