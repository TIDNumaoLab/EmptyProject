"""惣菜の対象日・時間帯ごとの期限(詳細設計書「対象日の算出」「提案の状態遷移」)。"""
from datetime import date, datetime

import pytest

from smdx_api.clock import JST
from smdx_api.proposals.schedule import deli_deadline, deli_default_target, open_bands
from smdx_api.settings.values import resolve

DEPTS = [("VEG", "order"), ("DELI", "production")]
# 既定: 営業 10:00〜20:00、時間帯 10/11/14/17、製造開始 9:00/10:00/13:00/16:00
S = resolve({}, DEPTS)


def jst(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=JST)


@pytest.mark.parametrize("now,expected", [
    (jst(2026, 10, 16, 8, 59), date(2026, 10, 16)),
    # 最初の時間帯の製造開始時刻ちょうどは翌日
    (jst(2026, 10, 16, 9, 0), date(2026, 10, 17)),
    (jst(2026, 10, 16, 0, 30), date(2026, 10, 16)),
])
def test_deli_default_target(now, expected):
    assert deli_default_target(now, S) == expected


def test_deli_default_target_uses_jst():
    from datetime import timezone

    # UTC 00:30 = 日本時間 9:30(最初の製造開始 9:00 の後)→ 翌日
    assert deli_default_target(datetime(2026, 10, 16, 0, 30, tzinfo=timezone.utc), S) == date(2026, 10, 17)


def test_deli_deadline():
    assert deli_deadline(date(2026, 10, 17), 14, S) == jst(2026, 10, 17, 13)
    assert deli_deadline(date(2026, 10, 17), 10, S) == jst(2026, 10, 17, 9)


def test_open_bands():
    assert open_bands(date(2026, 10, 16), jst(2026, 10, 16, 10, 0), S) == [14, 17]
    assert open_bands(date(2026, 10, 17), jst(2026, 10, 16, 10, 0), S) == [10, 11, 14, 17]
    # 製造開始時刻ちょうどの時間帯は締め切り済み
    assert open_bands(date(2026, 10, 16), jst(2026, 10, 16, 13, 0), S) == [17]
    assert open_bands(date(2026, 10, 16), jst(2026, 10, 16, 8, 0), S) == [10, 11, 14, 17]
