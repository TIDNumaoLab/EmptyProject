"""惣菜の製造計画の一覧・再計算(詳細設計書「きっかけ」「対象日の算出(惣菜)」「画面詳細設計(製造計画)」)。"""
import pytest
from sqlalchemy import select

from smdx_api.db.models import ProposalJob, Setting
from smdx_api.predictor.predict import TIME_BANDS_CHANGED
from tests.conftest import jst


def list_deli(client, **params):
    res = client.get("/api/proposals", params={"department_code": "DELI", **params})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.db
def test_production_list_default_target_and_rows(client, login, user_factory, deli_setup, test_services, db):
    login(client, user_factory(departments=("DELI",)))
    first = list_deli(client)  # ジョブ開始(応答の後に完了)
    assert first["proposals"] == [] and first["job"]["status"] == "running" and first["job"]["total"] == 4
    # 提案がまだ無くても、一覧の対象日(既定の対象日)を返す
    assert first["target_date"] == "2026-10-16"
    job = db.get(ProposalJob, first["job"]["id"])
    assert (job.scope, job.target_date.isoformat()) == ("date", "2026-10-16")
    body = list_deli(client)
    assert body["job"] is None and body["notice"] is None
    rows = body["proposals"]
    assert [(p["target_date"], p["time_band"]) for p in rows] == [("2026-10-16", b) for b in (10, 11, 14, 17)]
    assert [p["proposed_qty"] for p in rows] == [2, 7, 4, 10]
    assert rows[2]["deadline"] == "2026-10-16T13:00:00+09:00" and rows[2]["display_stock_qty"] == 0
    assert rows[2]["inventory_qty"] is None and rows[2]["warnings"] == []
    assert body["freshness"]["inventory_based_at"] is None


@pytest.mark.db
def test_default_target_is_tomorrow_from_first_production_start(client, login, user_factory, deli_setup, test_services,
                                                                 fixed_now):
    fixed_now.set(jst(2026, 10, 16, 9, 0))
    login(client, user_factory(departments=("DELI",)))
    assert list_deli(client)["target_date"] == "2026-10-17"
    rows = list_deli(client)["proposals"]
    assert {p["target_date"] for p in rows} == {"2026-10-17"} and len(rows) == 4
    # 状態で絞って0件でも対象日は返す
    empty = list_deli(client, status="expired")
    assert empty["proposals"] == [] and empty["target_date"] == "2026-10-17"


@pytest.mark.db
def test_only_open_bands_are_recalculated_but_all_bands_listed(client, login, user_factory, deli_setup, test_services,
                                                               fixed_now):
    login(client, user_factory(departments=("DELI",)))
    list_deli(client)
    list_deli(client)
    # 10:40 には 10時帯・11時帯の製造開始を過ぎて期限切れになる。手動再計算は残りの時間帯だけを計算する
    fixed_now.set(jst(2026, 10, 16, 10, 40))
    res = client.post("/api/proposals/recalculate", json={"department_code": "DELI", "target_date": "2026-10-16"})
    assert res.status_code == 200 and res.json()["job"]["total"] == 2
    rows = list_deli(client, target_date="2026-10-16")["proposals"]
    assert [(p["time_band"], p["status"]) for p in rows] == [(10, "expired"), (11, "expired"), (14, "pending"),
                                                             (17, "pending")]


@pytest.mark.db
def test_no_job_when_all_bands_closed(client, login, user_factory, deli_setup, test_services, fixed_now):
    login(client, user_factory(departments=("DELI",)))
    # 当日の全時間帯の製造開始を過ぎていれば、当日を指定しても作る提案は無い
    fixed_now.set(jst(2026, 10, 16, 16, 30))
    body = list_deli(client, target_date="2026-10-16")
    assert body["job"] is None and body["proposals"] == []


@pytest.mark.db
def test_time_band_change_rebuilds_with_new_bands(client, login, user_factory, deli_setup, test_services, db):
    login(client, user_factory(departments=("DELI",)))
    list_deli(client)
    assert len(list_deli(client)["proposals"]) == 4
    # 区切りを変えると、新しい区切りの提案が無いので作り直し、古い区切りの提案は一覧に出さない
    db.add(Setting(key="deli_time_bands", value=[10, 12, 16]))
    db.flush()
    assert list_deli(client)["job"] is not None
    rows = list_deli(client)["proposals"]
    assert [p["time_band"] for p in rows] == [10, 12, 16]


@pytest.mark.db
def test_band_model_mismatch_notice_is_returned(client, login, user_factory, deli_setup, app, job_session_factory,
                                                tmp_path, db):
    from smdx_api.api.deps import get_compute_services, get_session_factory
    from smdx_api.proposals.compute_fresh import ComputeServices
    from tests.fake_models import band_registry
    from tests.fakes import FakeWeatherClient

    db.add(Setting(key="deli_time_bands", value=[10, 12, 16]))
    db.flush()
    app.dependency_overrides[get_compute_services] = lambda: ComputeServices(band_registry(tmp_path, [10, 11, 14, 17]),
                                                                             FakeWeatherClient())
    app.dependency_overrides[get_session_factory] = lambda: job_session_factory
    login(client, user_factory(departments=("DELI",)))
    list_deli(client)
    body = list_deli(client)
    assert body["notice"] == TIME_BANDS_CHANGED and body["job"] is None


@pytest.mark.db
def test_fresh_list_still_lists_by_product(client, login, user_factory, veg_setup, deli_setup, test_services, db):
    """惣菜の商品があっても、生鮮の一覧・ジョブは変わらない。"""
    login(client, user_factory(departments=("VEG", "DELI")))
    client.get("/api/proposals", params={"department_code": "VEG"})
    rows = client.get("/api/proposals", params={"department_code": "VEG"}).json()["proposals"]
    assert [(p["product_code"], p["time_band"]) for p in rows] == [("VEG-001", None)]
    assert len(list(db.scalars(select(ProposalJob)))) == 1
