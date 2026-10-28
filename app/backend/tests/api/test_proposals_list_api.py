"""提案一覧・手動再計算・ジョブ進捗の API(詳細設計書「きっかけ」「API仕様」「鮮度の表示」)。"""
from datetime import date

import pytest
from sqlalchemy import select

from smdx_api.db.models import Proposal, ProposalJob
from tests.conftest import dept, jst


def list_veg(client, **params):
    res = client.get("/api/proposals", params={"department_code": "VEG", **params})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.db
def test_first_open_starts_job_then_returns_proposals(client, login, user_factory, veg_setup, test_services):
    login(client, user_factory(departments=("VEG",)))
    first = list_veg(client)
    assert first["proposals"] == [] and first["job"]["status"] == "running" and first["job"]["total"] == 1
    assert first["freshness"] == {"calculated_at": None, "weather_fetched_at": None, "inventory_based_at": None}
    # TestClient は応答後に BackgroundTasks を実行する → ジョブ完了
    job = client.get(f"/api/proposals/jobs/{first['job']['id']}").json()
    assert job == {"id": first["job"]["id"], "status": "succeeded", "processed": 1, "total": 1, "error": None,
                   "notice": None}
    second = list_veg(client)
    assert second["job"] is None and second["notice"] is None
    p = second["proposals"][0]
    assert p["product_code"] == "VEG-001" and p["proposed_qty"] == 24 and p["order_unit"] == 6
    assert p["department_code"] == "VEG" and p["target_date"] == "2026-10-17" and p["status"] == "pending"
    assert p["deadline"] == "2026-10-16T20:00:00+09:00" and p["calculated_at"] == "2026-10-16T15:00:00+09:00"
    assert p["carry_over_qty"] == pytest.approx(2.5) and p["is_baseline"] is True and p["weather_label"] == "晴れ"
    assert p["approved_by_name"] is None and p["warnings"] == []
    assert second["freshness"] == {"calculated_at": "2026-10-16T15:00:00+09:00",
                                   "weather_fetched_at": "2026-10-16T15:00:00+09:00",
                                   "inventory_based_at": "2026-10-16T14:30:00+09:00"}


@pytest.mark.db
def test_out_of_range_target_is_400(client, login, user_factory, fixed_now):
    login(client, user_factory(departments=("VEG",)))
    for d in ("2026-11-01", "2026-10-15"):
        res = client.get("/api/proposals", params={"department_code": "VEG", "target_date": d})
        assert res.status_code == 400 and res.json()["detail"] == "対象日は当日から15日先までを指定してください"
    res = client.post("/api/proposals/recalculate", json={"department_code": "VEG", "target_date": "2026-11-01"})
    assert res.status_code == 400


@pytest.mark.db
def test_target_range_uses_jst_today(client, login, user_factory, fixed_now):
    # 現在時刻が UTC で渡されても、当日は日本時間で決める(UTC 10/16 15:30 = 日本時間 10/17 0:30。PR #6 の軽微な課題)
    from datetime import datetime, timezone

    fixed_now.set(datetime(2026, 10, 16, 15, 30, tzinfo=timezone.utc))
    login(client, user_factory(departments=("VEG",)))
    res = client.get("/api/proposals", params={"department_code": "VEG", "target_date": "2026-10-16"})
    assert res.status_code == 400


@pytest.mark.db
def test_other_department_is_403_and_requires_login(client, login, user_factory, app):
    from fastapi.testclient import TestClient

    assert TestClient(app).get("/api/proposals", params={"department_code": "VEG"}).status_code == 401
    login(client, user_factory(departments=("VEG",)))
    assert client.get("/api/proposals", params={"department_code": "FISH"}).status_code == 403
    assert client.post("/api/proposals/recalculate", json={"department_code": "FISH"}).status_code == 403


@pytest.mark.db
def test_recalculate_requires_csrf_header(app, login, user_factory):
    from fastapi.testclient import TestClient

    c = TestClient(app)
    u = user_factory(departments=("VEG",))
    c.post("/api/auth/login", json={"login_id": u.login_id, "password": "pass1234"}, headers={"X-Requested-With": "smdx"})
    assert c.post("/api/proposals/recalculate", json={"department_code": "VEG"}).status_code == 403


@pytest.mark.db
def test_job_progress_permissions(client, login, user_factory, db, fixed_now):
    from smdx_api.proposals.jobs import JobKey, start_or_get_job

    job, _ = start_or_get_job(db, dept(db, "FISH"), JobKey("default", date(2026, 10, 16)), fixed_now.value, total=2)
    login(client, user_factory(departments=("VEG",)))
    assert client.get(f"/api/proposals/jobs/{job.id}").status_code == 403
    assert client.get("/api/proposals/jobs/999999").status_code == 404


@pytest.mark.db
def test_inventory_update_triggers_recalc_but_adjusted_keeps_qty(client, login, user_factory, veg_setup, test_services, db,
                                                                 product_factory):
    product_factory(code="VEG-002")
    login(client, user_factory(departments=("VEG",)))
    list_veg(client)  # 作成
    p = db.scalars(select(Proposal).join(Proposal.product).where(Proposal.product_id == veg_setup.id)).one()
    p.is_adjusted, p.proposed_qty, p.adjust_reason = True, 18, "weather"
    db.flush()
    # 在庫を手入力(14:50 に 30)→ 次に一覧を開くと、修正の無い VEG-002 が古くなったため再計算ジョブが始まる
    # (修正ありの提案だけなら自動では再計算しない)
    res = client.put("/api/inventory", json={"department_code": "VEG", "based_at": "2026-10-16T14:50:00+09:00",
                                             "items": [{"product_code": "VEG-001", "quantity": 30}]})
    assert res.status_code == 200
    after = list_veg(client)
    assert after["job"] is not None
    row = next(r for r in list_veg(client)["proposals"] if r["product_code"] == "VEG-001")
    # 修正した提案の数量は変えず、再計算値を差分として持つ
    # (販売見込 10 × (20−14.83)/10 = 5.17 → 持越見込 24.83 > 必要数 22 → 0)
    assert (row["proposed_qty"], row["recalculated_qty"], row["is_adjusted"]) == (18, 0, True)
    assert row["inventory_qty"] == 8  # 根拠は修正時点のまま


@pytest.mark.db
def test_unadjusted_proposal_is_replaced_on_recalc(client, login, user_factory, veg_setup, test_services, add_inventory):
    login(client, user_factory(departments=("VEG",)))
    list_veg(client)
    res = client.post("/api/proposals/recalculate", json={"department_code": "VEG"})
    assert res.status_code == 200 and res.json()["job"]["status"] == "running"
    rows = list_veg(client)["proposals"]
    assert rows[0]["proposed_qty"] == 24 and rows[0]["recalculated_qty"] is None


@pytest.mark.db
def test_manual_recalc_returns_running_job_when_exists(client, login, user_factory, veg_setup, db, fixed_now):
    from smdx_api.proposals.jobs import JobKey, start_or_get_job

    running, _ = start_or_get_job(db, dept(db, "VEG"), JobKey("default", date(2026, 10, 16)), fixed_now.value, total=1)
    login(client, user_factory(departments=("VEG",)))
    res = client.post("/api/proposals/recalculate", json={"department_code": "VEG"})
    assert res.json()["job"]["id"] == running.id
    # 一覧でも実行中のジョブを返し、新しいジョブは作らない
    assert list_veg(client)["job"]["id"] == running.id
    assert len(list(db.scalars(select(ProposalJob)))) == 1


@pytest.mark.db
def test_status_filter_and_order(client, login, user_factory, proposal_factory, db, fixed_now, test_services):
    fixed_now.set(jst(2026, 10, 16, 15))
    a = proposal_factory(product_code="VEG-002", status="approved", calculated_at=fixed_now.value)
    b = proposal_factory(product_code="VEG-001", status="pending", calculated_at=fixed_now.value)
    login(client, user_factory(departments=("VEG",)))
    assert [r["product_code"] for r in list_veg(client)["proposals"]] == ["VEG-001", "VEG-002"]
    assert [r["id"] for r in list_veg(client, status="approved")["proposals"]] == [a.id]
    assert [r["id"] for r in list_veg(client, status="pending")["proposals"]] == [b.id]
    assert client.get("/api/proposals", params={"department_code": "VEG", "status": "bad"}).status_code == 422


@pytest.mark.db
def test_explicit_target_date_lists_only_that_day(client, login, user_factory, proposal_factory, fixed_now, test_services):
    fixed_now.set(jst(2026, 10, 16, 15))
    proposal_factory(product_code="VEG-001", target=date(2026, 10, 17))
    other = proposal_factory(product_code="VEG-002", target=date(2026, 10, 20), deadline=jst(2026, 10, 19, 20))
    login(client, user_factory(departments=("VEG",)))
    rows = list_veg(client, target_date="2026-10-20")["proposals"]
    assert [r["id"] for r in rows] == [other.id]


@pytest.mark.db
def test_list_applies_deadlines(client, login, user_factory, proposal_factory, fixed_now, test_services):
    fixed_now.set(jst(2026, 10, 16, 20, 30))
    p = proposal_factory(product_code="VEG-001", target=date(2026, 10, 17), status="approved")
    login(client, user_factory(departments=("VEG",)))
    rows = list_veg(client, target_date="2026-10-17")["proposals"]
    assert [(r["id"], r["status"]) for r in rows] == [(p.id, "confirmed")]


@pytest.mark.db
def test_manager_can_list_any_department(client, login, user_factory, test_services):
    login(client, user_factory(role="manager", departments=()))
    assert client.get("/api/proposals", params={"department_code": "FISH"}).status_code == 200


@pytest.mark.db
def test_no_weather_does_not_loop_jobs(client, login, user_factory, veg_setup, app, job_session_factory, tmp_path):
    """予報が取れない間も、作成直後に一覧を取り直すたびにジョブを始めない(再計算が止まらなくなるのを防ぐ)。"""
    from smdx_api.api.deps import get_compute_services, get_session_factory
    from smdx_api.proposals.compute_fresh import ComputeServices
    from tests.fake_models import const_registry
    from tests.fakes import FailingWeatherClient

    app.dependency_overrides[get_compute_services] = lambda: ComputeServices(const_registry(tmp_path), FailingWeatherClient())
    app.dependency_overrides[get_session_factory] = lambda: job_session_factory
    login(client, user_factory(departments=("VEG",)))
    assert list_veg(client)["job"] is not None
    again = list_veg(client)
    assert again["job"] is None and again["proposals"][0]["warnings"] == ["NO_WEATHER"]


@pytest.mark.db
def test_list_returns_notice_of_last_succeeded_job(client, login, user_factory, db, fixed_now, test_services):
    from smdx_api.proposals.jobs import JobKey, start_or_get_job

    old, _ = start_or_get_job(db, dept(db, "VEG"), JobKey("default", date(2026, 10, 16)), fixed_now.value, total=1)
    old.status, old.notice = "succeeded", "古い注記"
    db.commit()
    fixed_now.advance(seconds=60)
    new, _ = start_or_get_job(db, dept(db, "VEG"), JobKey("default", date(2026, 10, 16)), fixed_now.value, total=1)
    new.status, new.notice = "succeeded", "時間帯の設定が変わったため再学習が必要です"
    db.commit()
    login(client, user_factory(departments=("VEG",)))
    assert list_veg(client)["notice"] == "時間帯の設定が変わったため再学習が必要です"
    assert client.get(f"/api/proposals/jobs/{new.id}").json()["notice"] == "時間帯の設定が変わったため再学習が必要です"
    # 対象日を指定した一覧は別の種別のジョブを見る
    assert client.get("/api/proposals", params={"department_code": "VEG", "target_date": "2026-10-16"}).json()["notice"] is None


@pytest.mark.db
def test_job_progress_reports_timed_out_running_job_as_failed(client, login, user_factory, db, fixed_now):
    """再起動などで止まった実行中のジョブは、10分を超えたら失敗として返す(画面が待ち続けないように)。"""
    from smdx_api.proposals.jobs import JOB_TIMEOUT, JobKey, start_or_get_job

    job, _ = start_or_get_job(db, dept(db, "VEG"), JobKey("default", date(2026, 10, 16)), fixed_now.value, total=2)
    login(client, user_factory(departments=("VEG",)))
    assert client.get(f"/api/proposals/jobs/{job.id}").json()["status"] == "running"
    fixed_now.advance(seconds=JOB_TIMEOUT.total_seconds() + 1)
    body = client.get(f"/api/proposals/jobs/{job.id}").json()
    assert (body["status"], body["error"]) == ("failed", "タイムアウトしました")
