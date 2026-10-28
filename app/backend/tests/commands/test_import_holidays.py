"""祝日の初期取込・再取込(import_holidays)。"""
from datetime import date

import pytest
from sqlalchemy import func, select

from smdx_api.commands import CommandError
from smdx_api.commands.import_holidays import import_holidays, parse_holidays
from smdx_api.db.models import CalendarDay
from smdx_api.settings.service import EVENTS_CHANGED_KEY, read_internal_datetime

CABINET_CSV = "国民の祝日・休日月日,国民の祝日・休日名称\n2026/1/1,元日\n2026/1/12,成人の日\n"


@pytest.mark.parametrize("encoding", ["cp932", "utf-8", "utf-8-sig"])
def test_parse_holidays_encodings(encoding):
    assert parse_holidays(CABINET_CSV.encode(encoding)) == [(date(2026, 1, 1), "元日"), (date(2026, 1, 12), "成人の日")]


def test_parse_holidays_rejects_bad_line():
    with pytest.raises(CommandError, match="3行目: 日付の形式が不正です"):
        parse_holidays("国民の祝日・休日月日,国民の祝日・休日名称\n2026/1/1,元日\n2026-13-1,x\n".encode())


@pytest.mark.db
def test_import_holidays_replaces_only_holidays(db, fixed_now):
    db.add(CalendarDay(date=date(2025, 1, 1), kind="holiday", name="古い祝日"))
    db.add(CalendarDay(date=date(2026, 7, 24), kind="event", name="土用の丑の日"))
    db.flush()
    data = CABINET_CSV.encode("cp932")
    assert import_holidays(db, data, fixed_now.value) == 2
    assert import_holidays(db, data, fixed_now.value) == 2
    kinds = dict(db.execute(select(CalendarDay.kind, func.count()).group_by(CalendarDay.kind)).all())
    assert kinds == {"holiday": 2, "event": 1}
    assert read_internal_datetime(db, EVENTS_CHANGED_KEY) == fixed_now.value


@pytest.mark.parametrize("data", [b"", "国民の祝日・休日月日,国民の祝日・休日名称\n".encode("cp932")])
def test_parse_holidays_rejects_empty(data):
    # 祝日が1件も無いファイルで、登録済みの祝日を消さない(PR #2 指摘7)
    with pytest.raises(CommandError, match="祝日が1件もありません"):
        parse_holidays(data)


def test_parse_holidays_rejects_undecodable():
    with pytest.raises(CommandError, match="文字コードを読み取れません"):
        parse_holidays(b"\x82\xa0\xff\xfe\x80\x81,\x82\n")
