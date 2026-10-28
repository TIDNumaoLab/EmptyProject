"""祝日の初期取込・再取込(内閣府の祝日CSV syukujitsu.csv)。

kind=holiday の行をすべて置き換える(行事日はそのまま)。
文字コードは UTF-8(BOM可)を先に試し、読めなければ cp932(内閣府のCSVは Shift_JIS)。詳細設計書「管理コマンド」。
"""
import argparse
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from smdx_api.clock import now as clock_now
from smdx_api.commands import CommandError, open_session
from smdx_api.db.models import CalendarDay
from smdx_api.settings.service import EVENTS_CHANGED_KEY, touch_internal

_DATE_RE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("cp932")
    except UnicodeDecodeError:
        raise CommandError("文字コードを読み取れません(UTF-8 か Shift_JIS のファイルを指定してください)") from None


def parse_holidays(data: bytes) -> list[tuple[date, str]]:
    rows = []
    for line_no, cells in enumerate(csv.reader(_decode(data).splitlines()), start=1):
        if not cells or all(not c.strip() for c in cells):
            continue
        if line_no == 1 and not _DATE_RE.match(cells[0].strip()):
            continue  # 見出し行
        m = _DATE_RE.match(cells[0].strip())
        name = cells[1].strip() if len(cells) > 1 else ""
        if not m or not name:
            raise CommandError(f"{line_no}行目: 日付の形式が不正です(YYYY/M/D,名称)")
        try:
            day = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            raise CommandError(f"{line_no}行目: 日付の形式が不正です(YYYY/M/D,名称)") from None
        rows.append((day, name[:64]))
    if not rows:
        # 空のファイルで登録済みの祝日をすべて消さないようにする
        raise CommandError("祝日が1件もありません。ファイルを確かめてください")
    return rows


def import_holidays(db: Session, data: bytes, now: datetime) -> int:
    rows = parse_holidays(data)
    db.execute(delete(CalendarDay).where(CalendarDay.kind == "holiday"))
    db.add_all(CalendarDay(date=d, kind="holiday", name=n) for d, n in rows)
    touch_internal(db, EVENTS_CHANGED_KEY, now)
    db.flush()
    return len(rows)


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("import_holidays", help="祝日を取り込む(内閣府の syukujitsu.csv)")
    p.add_argument("--file", required=True, type=Path, help="祝日CSVのパス")
    p.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    try:
        data = args.file.read_bytes()
    except OSError as e:
        print(f"ファイルを読めません: {e}", file=sys.stderr)
        return 1
    with open_session() as db:
        try:
            n = import_holidays(db, data, clock_now())
        except CommandError as e:
            print(e, file=sys.stderr)
            return 1
        db.commit()
    print(f"祝日を {n} 件取り込みました")
    return 0
