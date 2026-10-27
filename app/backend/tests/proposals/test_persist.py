"""提案の保存(詳細設計書「自動再計算の対象と判定」: 保護される提案は再計算値だけを保存する)。"""
from datetime import date

import pytest
from sqlalchemy import select

from smdx_api.db.models import Forecast, Proposal, ProposalHistory
from smdx_api.proposals.compute_fresh import ComputedProposal
from smdx_api.proposals.persist import apply_computed
from tests.conftest import dept, jst

T0, T1 = jst(2026, 10, 16, 9), jst(2026, 10, 16, 12)


def computed(product, qty, basis=None, warnings=(), target=date(2026, 10, 17)) -> ComputedProposal:
    return ComputedProposal(
        product_id=product.id, product_code=product.product_code, target_date=target, time_band=None, qty=qty,
        deadline=jst(2026, 10, 16, 20), warnings=tuple(warnings), basis=basis or {"inventory_qty": 8},
        predicted_qty=float(qty), model_version="baseline", features={"sales_lag_7d": 20.0}, weather_fetched_at=T0,
    )


def histories(db, p):
    return list(db.scalars(select(ProposalHistory).where(ProposalHistory.proposal_id == p.id).order_by(ProposalHistory.id)))


def get_one(db) -> Proposal:
    return db.scalars(select(Proposal)).one()


@pytest.mark.db
def test_persist_create_then_recalculate(db, product_factory):
    veg, p0 = dept(db, "VEG"), product_factory(code="VEG-001")
    apply_computed(db, veg, [computed(p0, 24, warnings=["NO_INVENTORY"])], T0)
    p = get_one(db)
    assert (p.status, p.proposed_qty, p.original_qty, p.calculated_at, p.warnings) == ("pending", 24, 24, T0, ["NO_INVENTORY"])
    f = db.get(Forecast, p.forecast_id)
    assert (f.predicted_qty, f.model_version, f.features, f.weather_fetched_at) == (24.0, "baseline", {"sales_lag_7d": 20.0}, T0)
    apply_computed(db, veg, [computed(p0, 30)], T1)
    db.refresh(p)
    assert (p.proposed_qty, p.original_qty, p.recalculated_qty, p.calculated_at, p.warnings) == (30, 30, None, T1, [])
    assert p.forecast_id != f.id
    hs = histories(db, p)
    assert [(h.action, h.qty_before, h.qty_after, h.actor_id) for h in hs] == [("create", None, 24, None), ("recalculate", 24, 30, None)]


@pytest.mark.db
def test_recalculate_clears_old_recalculated_value(db, proposal_factory):
    # 採用の後などで未承認・修正なしに戻った提案は、通常の再計算で再計算値を空にする
    p = proposal_factory(qty=20, recalculated_qty=26)
    apply_computed(db, dept(db, "VEG"), [computed(p.product, 22)], T1)
    db.refresh(p)
    assert (p.proposed_qty, p.recalculated_qty) == (22, None)


@pytest.mark.db
@pytest.mark.parametrize("status,adjusted", [("pending", True), ("approved", False)])
def test_persist_protected_only_sets_recalculated(db, status, adjusted, proposal_factory):
    p = proposal_factory(qty=20, status=status, is_adjusted=adjusted, calculated_at=T0, basis={"inventory_qty": 8})
    forecast_id = p.forecast_id
    apply_computed(db, dept(db, "VEG"), [computed(p.product, 26, basis={"inventory_qty": 1})], T1)
    db.refresh(p)
    assert (p.proposed_qty, p.recalculated_qty, p.calculated_at, p.basis["inventory_qty"]) == (20, 26, T0, 8)
    assert p.forecast_id == forecast_id and p.status == status and histories(db, p) == []


@pytest.mark.db
@pytest.mark.parametrize("status", ["confirmed", "expired"])
def test_persist_leaves_closed_untouched(db, status, proposal_factory):
    p = proposal_factory(qty=20, status=status, calculated_at=T0)
    apply_computed(db, dept(db, "VEG"), [computed(p.product, 26)], T1)
    db.refresh(p)
    assert (p.proposed_qty, p.recalculated_qty, p.calculated_at, p.status) == (20, None, T0, status)


@pytest.mark.db
def test_persist_reports_progress(db, product_factory):
    a, b = product_factory(code="VEG-001"), product_factory(code="VEG-002")
    seen = []
    apply_computed(db, dept(db, "VEG"), [computed(a, 1), computed(b, 2)], T0, on_progress=seen.append)
    assert seen == [1, 2]


@pytest.mark.db
def test_persist_rereads_state_before_saving(db, proposal_factory):
    """計算中に担当者が修正した提案を上書きしない(保存の直前に状態を読み直す)。"""
    p = proposal_factory(qty=20)
    db.expire_all()
    # 計算後・保存前に、別の操作で修正された
    db.execute(Proposal.__table__.update().where(Proposal.id == p.id).values(is_adjusted=True, proposed_qty=15))
    apply_computed(db, dept(db, "VEG"), [computed(p.product, 26)], T1)
    db.refresh(p)
    assert (p.proposed_qty, p.recalculated_qty, p.is_adjusted) == (15, 26, True)
