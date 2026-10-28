"""祝日・行事日 API の入出力。"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class CalendarDayIn(BaseModel):
    """API で登録できるのは行事日だけ。祝日は管理コマンド import_holidays で登録する。"""
    date: date
    kind: Literal["event"]
    name: str = Field(min_length=1, max_length=64)


class CalendarDayOut(BaseModel):
    id: int
    date: date
    kind: Literal["holiday", "event"]
    name: str
