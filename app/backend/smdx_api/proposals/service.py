"""一覧APIの裏で行う判定とジョブの起動(詳細設計書「きっかけ」「自動再計算の対象と判定」)。"""
from collections.abc import Callable
from datetime import date, datetime, timedelta

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.clock import JST
from smdx_api.db.models import Department, Proposal
from smdx_api.predictor.predict import BASELINE_VERSION
from smdx_api.proposals.compute_fresh import ComputeServices, FreshTargets, department_products, fresh_target_dates
from smdx_api.proposals.inputs import freshness_context
from smdx_api.proposals.jobs import run_job
from smdx_api.proposals.rules import ProposalFreshness, is_stale
from smdx_api.settings.values import AppSettings


def job_target_date(department: Department, now: datetime, settings: AppSettings, targets: FreshTargets) -> date:
    """ジョブを区別する対象日。生鮮の既定表示は発注日(締め時刻より前は当日、以後は翌日)、対象日の指定はその日。"""
    if targets.explicit_date is not None:
        return targets.explicit_date
    local = now.astimezone(JST)
    return local.date() if local.time() < settings.order_cutoff[department.code] else local.date() + timedelta(days=1)


def current_model_version(services: ComputeServices) -> str:
    loaded = services.registry.get("daily")
    return loaded.version if loaded else BASELINE_VERSION


def _fetched_at(basis: dict) -> datetime | None:
    v = (basis or {}).get("weather_fetched_at")
    return datetime.fromisoformat(v) if v else None


def needs_auto_recalc(
    db: Session, department: Department, now: datetime, settings: AppSettings, services: ComputeServices,
    targets: FreshTargets,
) -> bool:
    """対象のいずれかの提案が未作成、または未承認・修正なしの提案が古ければ True。"""
    target_by_id = fresh_target_dates(department_products(db, department), now, settings, targets)
    if not target_by_id:
        return False
    rows = db.scalars(select(Proposal).where(
        Proposal.department_id == department.id, Proposal.product_id.in_(target_by_id), Proposal.time_band.is_(None),
        Proposal.target_date.in_(set(target_by_id.values())),
    ))
    found = {(p.product_id, p.target_date): p for p in rows}
    if any((pid, d) not in found for pid, d in target_by_id.items()):
        return True
    ctx = freshness_context(db, department.id, current_model_version(services), settings.weather_stale_hours)
    for pid, d in target_by_id.items():
        p = found[(pid, d)]
        if p.status != "pending" or p.is_adjusted:
            continue
        basis = p.basis or {}
        version = basis.get("loaded_model_version", basis.get("model_version", BASELINE_VERSION))
        freshness = ProposalFreshness(p.calculated_at, version, _fetched_at(basis))
        if is_stale(freshness, ctx, now):
            return True
    return False


class JobLauncher:
    """ジョブを FastAPI の BackgroundTasks に積む(同じプロセスのスレッドで実行する)。"""

    def __init__(self, session_factory: Callable[[], Session], services: ComputeServices, now_fn: Callable[[], datetime]) -> None:
        self.session_factory = session_factory
        self.services = services
        self.now_fn = now_fn

    def launch(self, background_tasks: BackgroundTasks, job_id: int, targets: FreshTargets) -> None:
        background_tasks.add_task(run_job, job_id, targets, self.session_factory, self.services, self.now_fn)
