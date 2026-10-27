"""生鮮の対象日・期限(詳細設計書「対象日の算出」「提案の状態遷移」)。"""
from datetime import date, datetime, time

import pytest

from smdx_api.clock import JST
from smdx_api.proposals.schedule import (
    TargetOutOfRange,
    check_target_range,
    earliest_delivery_date,
    fresh_deadline,
    order_date_for,
)


def jst(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=JST)


@pytest.mark.parametrize("now,lt,expected", [
    (jst(2026, 10, 16, 19, 59), 1, date(2026, 10, 17)),
    (jst(2026, 10, 16, 20, 0), 1, date(2026, 10, 18)),   # 締め時刻ちょうどは以後
    (jst(2026, 10, 16, 0, 30), 2, date(2026, 10, 18)),   # JST 0時台
    (jst(2026, 10, 16, 8, 59), 1, date(2026, 10, 17)),
])
def test_earliest_delivery_date(now, lt, expected):
    assert earliest_delivery_date(now, time(20), lt) == expected


def test_earliest_delivery_date_uses_jst_date_of_utc_input():
    # UTC で前日 15:30 = JST 0:30。日付は JST で決める
    from datetime import timezone
    now = datetime(2026, 10, 15, 15, 30, tzinfo=timezone.utc)
    assert earliest_delivery_date(now, time(20), 1) == date(2026, 10, 17)


def test_order_date_and_deadline():
    assert order_date_for(date(2026, 10, 18), 2) == date(2026, 10, 16)
    assert fresh_deadline(date(2026, 10, 18), 2, time(20)) == jst(2026, 10, 16, 20)


@pytest.mark.parametrize("target,ok", [
    (date(2026, 10, 16), True), (date(2026, 10, 31), True), (date(2026, 11, 1), False), (date(2026, 10, 15), False),
])
def test_target_range(target, ok):
    if ok:
        check_target_range(target, date(2026, 10, 16))
    else:
        with pytest.raises(TargetOutOfRange, match="対象日は当日から15日先までを指定してください"):
            check_target_range(target, date(2026, 10, 16))
