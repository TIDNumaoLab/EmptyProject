"""祝日・行事日カレンダー(F-05)。閲覧は全員、登録・削除は店長のみ。"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.api.deps import NOT_FOUND, current_user, get_db, require_manager
from smdx_api.auth.permissions import Principal
from smdx_api.clock import get_now
from smdx_api.db.models import CalendarDay
from smdx_api.schemas.calendar import CalendarDayIn, CalendarDayOut
from smdx_api.settings.service import EVENTS_CHANGED_KEY, touch_internal

router = APIRouter(prefix="/api")


def _out(d: CalendarDay) -> CalendarDayOut:
    return CalendarDayOut(id=d.id, date=d.date, kind=d.kind, name=d.name)


@router.get("/calendar", response_model=list[CalendarDayOut])
def list_calendar(
    year: int | None = Query(default=None, ge=1, le=9999),
    _: Principal = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = select(CalendarDay).order_by(CalendarDay.date, CalendarDay.kind)
    if year is not None:
        q = q.where(CalendarDay.date >= date(year, 1, 1), CalendarDay.date <= date(year, 12, 31))
    return [_out(d) for d in db.scalars(q)]


@router.post("/calendar", response_model=CalendarDayOut)
def create_calendar_day(
    body: CalendarDayIn, _: Principal = Depends(require_manager), db: Session = Depends(get_db), now: datetime = Depends(get_now)
):
    exists = db.scalar(select(CalendarDay.id).where(CalendarDay.date == body.date, CalendarDay.kind == body.kind))
    if exists is not None:
        raise HTTPException(status_code=409, detail="既に登録されています")
    day = CalendarDay(date=body.date, kind=body.kind, name=body.name)
    db.add(day)
    touch_internal(db, EVENTS_CHANGED_KEY, now)
    db.commit()
    return _out(day)


@router.delete("/calendar/{day_id}", status_code=204)
def delete_calendar_day(
    day_id: int, _: Principal = Depends(require_manager), db: Session = Depends(get_db), now: datetime = Depends(get_now)
) -> Response:
    day = db.get(CalendarDay, day_id)
    if day is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if day.kind == "holiday":
        # 祝日は管理コマンド import_holidays で再取込する
        raise HTTPException(status_code=409, detail="祝日は削除できません")
    db.delete(day)
    touch_internal(db, EVENTS_CHANGED_KEY, now)
    db.commit()
    return Response(status_code=204)
