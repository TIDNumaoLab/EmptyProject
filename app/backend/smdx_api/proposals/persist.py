"""計算結果の保存(予測結果を forecasts に、提案と根拠を proposals に)。

保存の直前に対象の行を FOR UPDATE で読み直し、計算中に修正・承認された提案を上書きしない。
- 修正あり・承認取消後の未承認、承認済み: 再計算値(recalculated_qty)だけを更新する。計算日時・根拠・予測は変えない
- 確定・期限切れ: 変更しない
- それ以外: 数量・根拠・警告・予測・期限・計算日時を更新し、再計算値を空にする
"""
from collections.abc import Callable, Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.db.models import Department, Forecast, Proposal, ProposalHistory
from smdx_api.proposals.deadlines import state_of
from smdx_api.proposals.rules import is_protected


def _find(db: Session, department_id: int, c) -> Proposal | None:
    q = select(Proposal).where(Proposal.department_id == department_id, Proposal.product_id == c.product_id,
                               Proposal.target_date == c.target_date)
    q = q.where(Proposal.time_band.is_(None) if c.time_band is None else Proposal.time_band == c.time_band)
    return db.scalar(q.with_for_update().execution_options(populate_existing=True))


def _forecast(db: Session, c) -> Forecast:
    f = Forecast(product_id=c.product_id, target_date=c.target_date, time_band=c.time_band, predicted_qty=c.predicted_qty,
                 model_version=c.model_version, features=c.features, weather_fetched_at=c.weather_fetched_at)
    db.add(f)
    db.flush()
    return f


def apply_computed(
    db: Session,
    department: Department,
    computed: Sequence,
    now: datetime,
    on_progress: Callable[[int], None] | None = None,
) -> None:
    for i, c in enumerate(computed, start=1):
        p = _find(db, department.id, c)
        if p is None:
            f = _forecast(db, c)
            p = Proposal(department_id=department.id, product_id=c.product_id, target_date=c.target_date,
                         time_band=c.time_band, forecast_id=f.id, proposed_qty=c.qty, original_qty=c.qty,
                         is_adjusted=False, status="pending", deadline=c.deadline, warnings=list(c.warnings),
                         calculated_at=now, basis=c.basis)
            db.add(p)
            db.flush()
            db.add(ProposalHistory(proposal_id=p.id, action="create", qty_after=c.qty, occurred_at=now))
        elif p.status in ("confirmed", "expired"):
            pass
        elif is_protected(state_of(p)):
            p.recalculated_qty = c.qty
        else:
            before = p.proposed_qty
            f = _forecast(db, c)
            p.forecast_id = f.id
            p.proposed_qty = p.original_qty = c.qty
            p.recalculated_qty = None
            p.warnings = list(c.warnings)
            p.basis = c.basis
            p.deadline = c.deadline
            p.calculated_at = now
            db.add(ProposalHistory(proposal_id=p.id, action="recalculate", qty_before=before, qty_after=c.qty,
                                   occurred_at=now))
        db.flush()
        if on_progress is not None:
            on_progress(i)
