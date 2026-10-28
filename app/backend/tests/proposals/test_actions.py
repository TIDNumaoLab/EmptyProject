"""提案の操作(詳細設計書「提案の状態遷移」の操作の表)。"""
from datetime import timedelta

import pytest
from sqlalchemy import select

from smdx_api.db.models import ProposalHistory
from smdx_api.proposals.actions import (
    ProposalNotFound,
    adjust,
    adopt_recalculated,
    approve,
    approve_bulk,
    cancel_approval,
)
from smdx_api.proposals.rules import InputError, StateError
from tests.conftest import jst


@pytest.fixture
def user(user_factory):
    return user_factory(departments=("VEG",))


def last_history(db, p):
    return db.scalars(select(ProposalHistory).where(ProposalHistory.proposal_id == p.id)
                      .order_by(ProposalHistory.id.desc()).limit(1)).one()


@pytest.mark.db
def test_adjust_records_history_and_keeps_original(db, proposal_factory, fixed_now, user):
    p = proposal_factory(qty=24)
    adjust(db, p.id, 18, "weather", "雨予報", user.id, fixed_now.value)
    assert (p.proposed_qty, p.original_qty, p.is_adjusted, p.adjust_reason, p.adjust_note) == (18, 24, True, "weather", "雨予報")
    h = last_history(db, p)
    assert (h.action, h.qty_before, h.qty_after, h.reason, h.actor_id, h.occurred_at) == (
        "adjust", 24, 18, "weather", user.id, fixed_now.value)


@pytest.mark.db
def test_adjust_approved_is_rejected(db, proposal_factory, fixed_now, user):
    p = proposal_factory(status="approved")
    with pytest.raises(StateError, match="承認済みの提案は修正できません"):
        adjust(db, p.id, 3, "other", None, user.id, fixed_now.value)


@pytest.mark.db
def test_expired_proposal_cannot_be_approved(db, proposal_factory, user):
    p = proposal_factory(deadline=jst(2026, 10, 16, 20))
    with pytest.raises(StateError, match="未承認の提案ではありません"):
        approve(db, p.id, 10, False, user.id, jst(2026, 10, 16, 20))
    assert p.status == "expired"


@pytest.mark.db
def test_approve_sets_approver(db, proposal_factory, fixed_now, user):
    p = proposal_factory()
    approve(db, p.id, 10, False, user.id, fixed_now.value)
    assert (p.status, p.approved_by, p.approved_at) == ("approved", user.id, fixed_now.value)
    assert last_history(db, p).action == "approve"


@pytest.mark.db
def test_approve_with_warning_needs_confirmation(db, proposal_factory, fixed_now, user):
    p = proposal_factory(warnings=["NO_INVENTORY"])
    with pytest.raises(InputError, match="警告を確認してください"):
        approve(db, p.id, 10, False, user.id, fixed_now.value)
    approve(db, p.id, 10, True, user.id, fixed_now.value)
    assert p.status == "approved"


@pytest.mark.db
def test_approve_bulk_skips_warnings_and_non_pending(db, proposal_factory, user, fixed_now):
    ok = proposal_factory()
    warn = proposal_factory(warnings=["NO_INVENTORY"], product_offset=1)
    done = proposal_factory(status="approved", product_offset=2)
    approved, skipped = approve_bulk(db, [(ok.id, 10), (warn.id, 10), (done.id, 10), (999999, 0)], user.id, fixed_now.value)
    assert approved == [ok.id]
    assert skipped == [(warn.id, "警告があるため一括承認から除外しました"), (done.id, "未承認ではありません"),
                       (999999, "対象が見つかりません")]
    assert (ok.status, warn.status) == ("approved", "pending")


@pytest.mark.db
def test_approve_rejects_quantity_changed_since_shown(db, proposal_factory, fixed_now, user):
    # 画面を開いた後に裏の再計算で 20 → 24 に変わった
    p = proposal_factory(qty=24)
    with pytest.raises(StateError, match="数量が更新されました。一覧を取り直してから承認してください"):
        approve(db, p.id, 20, True, user.id, fixed_now.value)
    assert p.status == "pending"


@pytest.mark.db
def test_approve_bulk_skips_quantity_changed_since_shown(db, proposal_factory, user, fixed_now):
    ok = proposal_factory(qty=24)
    moved = proposal_factory(qty=30, product_offset=1)
    approved, skipped = approve_bulk(db, [(ok.id, 24), (moved.id, 28), (ok.id, 99)], user.id, fixed_now.value)
    assert approved == [ok.id]
    assert skipped == [(moved.id, "数量が更新されたため一括承認から除外しました")]
    assert moved.status == "pending"


@pytest.mark.db
def test_cancel_then_adopt(db, proposal_factory, user, fixed_now):
    p = proposal_factory(status="approved", recalculated_qty=30, qty=24, approved_by=user.id)
    cancel_approval(db, p.id, user.id, fixed_now.value)
    assert (p.status, p.is_adjusted, p.approved_by, p.approved_at) == ("pending", True, None, None)
    assert last_history(db, p).action == "cancel"
    p.adjust_reason = "inventory"
    adopt_recalculated(db, p.id, user.id, fixed_now.value)
    assert (p.proposed_qty, p.original_qty, p.recalculated_qty, p.is_adjusted, p.adjust_reason, p.status) == (
        30, 30, None, False, None, "pending")
    h = last_history(db, p)
    assert (h.action, h.qty_before, h.qty_after, h.reason, h.actor_id) == ("adopt", 24, 30, "inventory", user.id)


@pytest.mark.db
def test_adopt_on_approved_before_deadline_returns_to_pending(db, proposal_factory, user, fixed_now):
    p = proposal_factory(status="approved", recalculated_qty=12, approved_by=user.id)
    adopt_recalculated(db, p.id, user.id, fixed_now.value)
    assert (p.status, p.proposed_qty, p.approved_by, p.approved_at) == ("pending", 12, None, None)


@pytest.mark.db
def test_cancel_at_deadline_is_rejected(db, proposal_factory, user):
    p = proposal_factory(status="approved", deadline=jst(2026, 10, 16, 20))
    # 期限ちょうど: 期限経過の更新で確定になり、取り消せない
    with pytest.raises(StateError):
        cancel_approval(db, p.id, user.id, jst(2026, 10, 16, 20))
    assert p.status == "confirmed"
    q = proposal_factory(status="approved", deadline=jst(2026, 10, 16, 20), product_offset=5)
    cancel_approval(db, q.id, user.id, jst(2026, 10, 16, 20) - timedelta(seconds=1))
    assert q.status == "pending"


@pytest.mark.db
def test_missing_proposal(db, user, fixed_now):
    with pytest.raises(ProposalNotFound):
        approve(db, 999999, 0, False, user.id, fixed_now.value)
