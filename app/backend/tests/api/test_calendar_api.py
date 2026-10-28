"""祝日・行事日カレンダー(PostgreSQL が必要)。"""
from datetime import date

import pytest

from smdx_api.db.models import CalendarDay
from smdx_api.settings.service import EVENTS_CHANGED_KEY, read_internal_datetime


def test_calendar_requires_login(client):
    assert client.get("/api/calendar", params={"year": 2026}).status_code == 401


@pytest.mark.db
def test_calendar_manager_crud_and_holiday_protection(client, login, user_factory, db):
    login(client, user_factory(role="manager", departments=()))
    ev = client.post("/api/calendar", json={"date": "2026-07-24", "kind": "event", "name": "土用の丑の日"})
    assert ev.status_code == 200 and ev.json()["name"] == "土用の丑の日"
    dup = client.post("/api/calendar", json={"date": "2026-07-24", "kind": "event", "name": "x"})
    assert dup.status_code == 409 and dup.json()["detail"] == "既に登録されています"
    # 祝日は管理コマンド(import_holidays)でのみ登録する
    hol = CalendarDay(date=date(2026, 11, 3), kind="holiday", name="文化の日")
    db.add(hol)
    db.flush()
    res = client.delete(f"/api/calendar/{hol.id}")
    assert res.status_code == 409 and res.json()["detail"] == "祝日は削除できません"
    assert client.delete(f"/api/calendar/{ev.json()['id']}").status_code == 204
    assert client.delete("/api/calendar/999999").status_code == 404
    assert [d["name"] for d in client.get("/api/calendar", params={"year": 2026}).json()] == ["文化の日"]
    assert client.get("/api/calendar", params={"year": 2025}).json() == []


@pytest.mark.db
def test_calendar_list_is_sorted_and_visible_to_staff(client, login, user_factory, db):
    for d, k, n in [(date(2026, 12, 31), "event", "大晦日"), (date(2026, 1, 1), "holiday", "元日"), (date(2026, 1, 1), "event", "初売り")]:
        db.add(CalendarDay(date=d, kind=k, name=n))
    db.flush()
    login(client, user_factory(departments=("VEG",)))
    days = client.get("/api/calendar", params={"year": 2026}).json()
    assert [(d["date"], d["kind"]) for d in days] == [("2026-01-01", "event"), ("2026-01-01", "holiday"), ("2026-12-31", "event")]


@pytest.mark.db
@pytest.mark.parametrize("call", [
    lambda c: c.post("/api/calendar", json={"date": "2026-07-24", "kind": "event", "name": "x"}),
    lambda c: c.delete("/api/calendar/1"),
])
def test_calendar_changes_are_manager_only(client, login, user_factory, call):
    login(client, user_factory(departments=("VEG",)))
    assert call(client).status_code == 403


@pytest.mark.db
@pytest.mark.parametrize("body", [
    {"date": "2026-07-24", "kind": "festival", "name": "x"},
    # 祝日は API では登録できない(PR #2 指摘9)
    {"date": "2026-07-24", "kind": "holiday", "name": "x"},
    {"date": "2026-07-24", "kind": "event", "name": ""},
    {"date": "2026-07-24", "kind": "event", "name": "x" * 65},
])
def test_calendar_input_validation(client, login, user_factory, body):
    login(client, user_factory(role="manager", departments=()))
    assert client.post("/api/calendar", json=body).status_code == 422


@pytest.mark.db
def test_calendar_changes_touch_events_marker(client, login, user_factory, db, fixed_now):
    login(client, user_factory(role="manager", departments=()))
    ev = client.post("/api/calendar", json={"date": "2026-07-24", "kind": "event", "name": "土用の丑の日"}).json()
    assert read_internal_datetime(db, EVENTS_CHANGED_KEY) == fixed_now.value
    fixed_now.advance(minutes=5)
    client.delete(f"/api/calendar/{ev['id']}")
    assert read_internal_datetime(db, EVENTS_CHANGED_KEY) == fixed_now.value


@pytest.mark.db
@pytest.mark.parametrize("year", [0, -1, 10000])
def test_calendar_year_out_of_range_is_422(client, login, user_factory, year):
    # date(year, 1, 1) が作れない年で 500 にしない(PR #2 指摘3)
    login(client, user_factory(departments=("VEG",)))
    assert client.get("/api/calendar", params={"year": year}).status_code == 422
