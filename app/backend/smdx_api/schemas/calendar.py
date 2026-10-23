"""祝日・行事日 API の入出力。"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class CalendarDayIn(BaseModel):
    date: date
    kind: Literal["holiday", "event"]
    name: str = Field(min_length=1, max_length=64)


class CalendarDayOut(CalendarDayIn):
    id: int
