"""提案の状態遷移と操作の条件、最新性判定(詳細設計書「提案の状態遷移」「自動再計算の対象と判定」)。"""
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from smdx_api.clock import JST
from smdx_api.proposals.codes import BULK_EXCLUDED, WARNING_CODES
from smdx_api.proposals.rules import (
    FreshnessContext,
    InputError,
    ProposalFreshness,
    ProposalState,
    StateError,
    bulk_skip_reason,
    check_adjust,
    check_adopt,
    check_approve,
    check_cancel,
    deadline_transition,
    is_protected,
    is_stale,
)


def jst(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=JST)


D = jst(2026, 10, 16, 20)


def st(status="pending", adj=False, warnings=(), recalc=None):
    return ProposalState(status, adj, D, tuple(warnings), recalc)


def test_all_warnings_excluded_from_bulk():
    assert BULK_EXCLUDED == set(WARNING_CODES) == {"NO_INVENTORY", "NO_HISTORY", "NO_WEATHER", "STALE_POS"}


def test_adjust_rules():
    check_adjust(st())
    check_adjust(st(adj=True))
    with pytest.raises(StateError, match="承認済みの提案は修正できません"):
        check_adjust(st("approved"))
    for s in ("confirmed", "expired"):
        with pytest.raises(StateError, match="この提案は修正できません"):
            check_adjust(st(s))


def test_approve_requires_confirmation_with_warnings():
    with pytest.raises(InputError, match="警告を確認してください"):
        check_approve(st(warnings=["NO_INVENTORY"]), False)
    check_approve(st(warnings=["NO_INVENTORY"]), True)
    check_approve(st(), False)
    with pytest.raises(StateError, match="未承認の提案ではありません"):
        check_approve(st("approved"), True)


def test_bulk_skip_reason():
    assert bulk_skip_reason(st()) is None
    assert bulk_skip_reason(st(warnings=["STALE_POS"])) == "警告があるため一括承認から除外しました"
    assert bulk_skip_reason(st("approved")) == "未承認ではありません"


def test_cancel_until_deadline():
    check_cancel(st("approved"), D - timedelta(minutes=1))
    with pytest.raises(StateError, match="期限を過ぎているため取り消せません"):
        check_cancel(st("approved"), D)
    with pytest.raises(StateError, match="承認済みの提案ではありません"):
        check_cancel(st(), D - timedelta(minutes=1))


def test_adopt_rules():
    check_adopt(st(adj=True, recalc=5), D - timedelta(hours=1))
    check_adopt(st("approved", recalc=5), D - timedelta(hours=1))
    with pytest.raises(StateError, match="再計算値がありません"):
        check_adopt(st(adj=True), D)
    with pytest.raises(StateError, match="この提案には再計算値を採用できません"):
        check_adopt(st("confirmed", recalc=5), D)
    with pytest.raises(StateError, match="この提案には再計算値を採用できません"):
        check_adopt(st("approved", recalc=5), D)  # 期限ちょうどは期限後


def test_deadline_transition():
    assert deadline_transition(st(), D) == "expired"
    assert deadline_transition(st("approved"), D) == "confirmed"
    assert deadline_transition(st("approved"), D - timedelta(seconds=1)) is None
    assert deadline_transition(st("confirmed"), D + timedelta(days=1)) is None
    assert deadline_transition(st("expired"), D + timedelta(days=1)) is None


def test_is_protected():
    assert not is_protected(st())
    assert is_protected(st(adj=True))
    assert is_protected(st("approved"))
    assert not is_protected(st("confirmed"))


CALC = jst(2026, 10, 16, 18)
CTX = FreshnessContext(None, None, "daily-2026.11.01-1", 3)
P = ProposalFreshness(CALC, "daily-2026.11.01-1", CALC)


@pytest.mark.parametrize("p,ctx,now,stale", [
    (P, CTX, CALC + timedelta(hours=2, minutes=59), False),
    (P, CTX, CALC + timedelta(hours=3), True),                                           # 予報の経過
    (P, replace(CTX, data_changed_at=CALC + timedelta(minutes=1)), CALC + timedelta(hours=1), True),
    (P, replace(CTX, events_changed_at=CALC + timedelta(minutes=1)), CALC + timedelta(hours=1), True),
    (P, replace(CTX, current_model_version="daily-2026.11.08-1"), CALC + timedelta(hours=1), True),
    (replace(P, weather_fetched_at=None), CTX, CALC + timedelta(minutes=1), True),       # 予報なしで作った提案
    (P, replace(CTX, data_changed_at=CALC - timedelta(minutes=1)), CALC + timedelta(hours=1), False),
    (P, replace(CTX, events_changed_at=CALC), CALC + timedelta(hours=1), False),        # 同時刻は「後」ではない
])
def test_is_stale(p, ctx, now, stale):
    assert is_stale(p, ctx, now) is stale
