"""一覧APIの裏で行う判定とジョブの起動(詳細設計書「きっかけ」「自動再計算の対象と判定」)。

部門の business_type で生鮮(order: 商品ごとの最も早い納品日)と惣菜(production: 対象日の時間帯)を振り分ける。
"""
from collections.abc import Callable
from datetime import date, datetime, timedelta

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.clock import JST
from smdx_api.db.models import Department, Proposal
from smdx_api.predictor.predict import BASELINE_VERSION
from smdx_api.proposals.actions import RECALC_PENDING
from smdx_api.proposals.compute_fresh import ComputeServices, FreshTargets, department_products, fresh_target_dates
from smdx_api.proposals.inputs import freshness_context
from smdx_api.proposals.jobs import JobKey, run_job
from smdx_api.proposals.rules import ProposalFreshness, is_stale
from smdx_api.proposals.schedule import deli_default_target, open_bands
from smdx_api.settings.values import AppSettings


def is_production(department: Department) -> bool:
    return department.business_type == "production"


def deli_target(now: datetime, settings: AppSettings, targets: FreshTargets) -> date:
    """製造計画の対象日。指定が無ければ既定の対象日(最初の時間帯の製造開始時刻より前は当日、以後は翌日)。"""
    return targets.explicit_date if targets.explicit_date is not None else deli_default_target(now, settings)


def resolved_targets(department: Department, now: datetime, settings: AppSettings, targets: FreshTargets) -> FreshTargets:
    """ジョブに渡す対象。惣菜は既定表示でも対象日を決めて渡す(ジョブの実行時に日付が変わっても同じ日を計算する)。"""
    return FreshTargets(deli_target(now, settings, targets)) if is_production(department) else targets


def wanted(db: Session, department: Department, now: datetime, settings: AppSettings,
           targets: FreshTargets) -> dict[tuple[int, int | None], date]:
    """計算の対象。(商品ID, 時間帯) → 対象日。生鮮の時間帯は None、惣菜は製造開始時刻を過ぎていない時間帯。"""
    products = department_products(db, department)
    if is_production(department):
        target = deli_target(now, settings, targets)
        return {(p.id, b): target for p in products for b in open_bands(target, now, settings)}
    return {(pid, None): d for pid, d in fresh_target_dates(products, now, settings, targets).items()}


def job_key(department: Department, now: datetime, settings: AppSettings, targets: FreshTargets) -> JobKey:
    """ジョブを区別する種別と日付。生鮮の既定表示は発注日(締め時刻より前は当日、以後は翌日)、対象日の指定はその納品日。
    惣菜は既定表示も1つの対象日を計算し、指定と計算内容が同じなので、いずれも対象日で区別する。"""
    if is_production(department):
        return JobKey("date", deli_target(now, settings, targets))
    if targets.explicit_date is not None:
        return JobKey("date", targets.explicit_date)
    local = now.astimezone(JST)
    order_day = local.date() if local.time() < settings.order_cutoff[department.code] else local.date() + timedelta(days=1)
    return JobKey("default", order_day)


def current_model_version(services: ComputeServices, department: Department) -> str:
    loaded = services.registry.get("time_band" if is_production(department) else "daily")
    return loaded.version if loaded else BASELINE_VERSION


def _fetched_at(basis: dict) -> datetime | None:
    v = (basis or {}).get("weather_fetched_at")
    return datetime.fromisoformat(v) if v else None


def needs_auto_recalc(
    db: Session, department: Department, now: datetime, settings: AppSettings, services: ComputeServices,
    targets: FreshTargets,
) -> bool:
    """対象のいずれかの提案が未作成、または未承認・修正なしの提案が古ければ True。"""
    targets_by_key = wanted(db, department, now, settings, targets)
    if not targets_by_key:
        return False
    rows = db.scalars(select(Proposal).where(
        Proposal.department_id == department.id, Proposal.product_id.in_({pid for pid, _ in targets_by_key}),
        Proposal.target_date.in_(set(targets_by_key.values())),
    ))
    found = {(p.product_id, p.time_band, p.target_date): p for p in rows}
    keys = [(pid, band, d) for (pid, band), d in targets_by_key.items()]
    if any(k not in found for k in keys):
        return True
    ctx = freshness_context(db, department.id, current_model_version(services, department), settings.weather_stale_hours)
    for k in keys:
        p = found[k]
        if p.status != "pending" or p.is_adjusted:
            continue
        basis = p.basis or {}
        version = basis.get("loaded_model_version", basis.get("model_version", BASELINE_VERSION))
        freshness = ProposalFreshness(p.calculated_at, version, _fetched_at(basis), bool(basis.get(RECALC_PENDING)))
        if is_stale(freshness, ctx, now):
            return True
    return False


class JobLauncher:
    """ジョブを FastAPI の BackgroundTasks に積む(同じプロセスのスレッドで実行する)。"""

    def __init__(self, session_factory: Callable[[], Session], services: ComputeServices, now_fn: Callable[[], datetime],
                 clock: Callable[[], datetime] | None = None) -> None:
        self.session_factory = session_factory
        self.services = services
        self.now_fn = now_fn
        self.clock = clock

    def launch(self, background_tasks: BackgroundTasks, job_id: int, targets: FreshTargets) -> None:
        background_tasks.add_task(run_job, job_id, targets, self.session_factory, self.services, self.now_fn, self.clock)
