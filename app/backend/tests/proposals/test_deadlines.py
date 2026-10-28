"""期限経過による状態更新(詳細設計書「提案の状態遷移」)。"""
from datetime import date

import pytest
from sqlalchemy import select

from smdx_api.db.models import ProposalHistory
from smdx_api.proposals.deadlines import apply_deadlines
from tests.conftest import dept, jst


@pytest.mark.db
def test_apply_deadlines(db, proposal_factory):
    a = proposal_factory(status="pending", deadline=jst(2026, 10, 16, 20))
    b = proposal_factory(status="approved", deadline=jst(2026, 10, 16, 20), product_offset=1)
    c = proposal_factory(status="approved", deadline=jst(2026, 10, 17, 20), product_offset=2)
    assert apply_deadlines(db, jst(2026, 10, 16, 20)) == 2
    for x in (a, b, c):
        db.refresh(x)
    assert [x.status for x in (a, b, c)] == ["expired", "confirmed", "approved"]
    hs = list(db.scalars(select(ProposalHistory)))
    assert {(h.proposal_id, h.action, h.actor_id, h.occurred_at) for h in hs} == {
        (a.id, "expire", None, jst(2026, 10, 16, 20)), (b.id, "confirm", None, jst(2026, 10, 16, 20))}
    assert apply_deadlines(db, jst(2026, 10, 16, 21)) == 0


@pytest.mark.db
def test_apply_deadlines_by_department(db, proposal_factory, product_factory):
    v = proposal_factory(status="pending", deadline=jst(2026, 10, 16, 20))
    f = proposal_factory(product_factory(code="FISH-001", department="FISH"), status="pending",
                         deadline=jst(2026, 10, 16, 20), target=date(2026, 10, 17))
    assert apply_deadlines(db, jst(2026, 10, 16, 21), dept(db, "FISH").id) == 1
    db.refresh(v)
    db.refresh(f)
    assert (v.status, f.status) == ("pending", "expired")
