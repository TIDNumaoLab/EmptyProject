"""特売・チラシ(PostgreSQL が必要)。"""
import pytest

from smdx_api.settings.service import EVENTS_CHANGED_KEY, read_internal_datetime


def _promo(product="VEG-001", start="2026-10-20", end="2026-10-22", description="チラシ"):
    return {"product_code": product, "start_date": start, "end_date": end, "description": description}


@pytest.fixture
def products(product_factory):
    product_factory(code="VEG-001", name="キャベツ")
    product_factory(code="VEG-002")
    product_factory(code="FISH-001", department="FISH")


@pytest.mark.db
def test_promotion_rules(client, login, user_factory, products):
    login(client, user_factory(name="青果 太郎", departments=("VEG",)))
    ok = client.post("/api/promotions", json=_promo())
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert (body["product_name"], body["department_code"], body["created_by_name"]) == ("キャベツ", "VEG", "青果 太郎")
    assert client.post("/api/promotions", json=_promo(product="FISH-001")).status_code == 403
    bad = client.post("/api/promotions", json=_promo(start="2026-10-22", end="2026-10-20"))
    assert bad.status_code == 422 and bad.json()["detail"] == "終了日は開始日以降にしてください"
    unknown = client.post("/api/promotions", json=_promo(product="XXX"))
    assert unknown.status_code == 422 and unknown.json()["detail"] == "未登録の商品コードです: XXX"
    assert client.post("/api/promotions", json=_promo(description="x" * 129)).status_code == 422
    listed = client.get("/api/promotions", params={"date_from": "2026-10-21", "date_to": "2026-10-21"}).json()
    assert [p["id"] for p in listed] == [body["id"]]
    assert client.get("/api/promotions", params={"date_from": "2026-10-23", "date_to": "2026-10-30"}).json() == []
    patched = client.patch(f"/api/promotions/{body['id']}", json={"end_date": "2026-10-23"})
    assert patched.json()["end_date"] == "2026-10-23" and patched.json()["start_date"] == "2026-10-20"
    assert client.patch(f"/api/promotions/{body['id']}", json={"end_date": "2026-10-19"}).status_code == 422
    assert client.delete("/api/promotions/999999").status_code == 404
    assert client.delete(f"/api/promotions/{body['id']}").status_code == 204
    assert client.get("/api/promotions").json() == []


@pytest.mark.db
def test_staff_cannot_change_other_departments_promotion(client, login, user_factory, products, make_client):
    fish = make_client()
    login(fish, user_factory(departments=("FISH",)))
    pid = fish.post("/api/promotions", json=_promo(product="FISH-001")).json()["id"]
    login(client, user_factory(departments=("VEG",)))
    assert client.patch(f"/api/promotions/{pid}", json={"description": "x"}).status_code == 403
    assert client.delete(f"/api/promotions/{pid}").status_code == 403
    # 自部門の商品へ付け替えるのも、元が他部門なら不可
    assert client.patch(f"/api/promotions/{pid}", json={"product_code": "VEG-001"}).status_code == 403
    # 一覧は全員が全部門を見られる
    assert [p["id"] for p in client.get("/api/promotions", params={"department_code": "FISH"}).json()] == [pid]


@pytest.mark.db
def test_promotions_department_filter_and_order(client, login, user_factory, products):
    login(client, user_factory(role="manager", departments=()))
    client.post("/api/promotions", json=_promo(product="VEG-002", start="2026-10-25", end="2026-10-25"))
    client.post("/api/promotions", json=_promo(product="FISH-001", start="2026-10-21", end="2026-10-21"))
    client.post("/api/promotions", json=_promo(product="VEG-001", start="2026-10-20", end="2026-10-26"))
    rows = client.get("/api/promotions", params={"department_code": "VEG"}).json()
    assert [(p["product_code"], p["start_date"]) for p in rows] == [("VEG-001", "2026-10-20"), ("VEG-002", "2026-10-25")]
    # 担当者が他部門の行を見ても部門コードのままにならないよう、部門名を返す(PR #2 指摘10)
    assert {p["department_name"] for p in rows} == {"青果"}


@pytest.mark.db
def test_changes_touch_events_marker(client, login, user_factory, products, db, fixed_now):
    login(client, user_factory(departments=("VEG",)))
    pid = client.post("/api/promotions", json=_promo()).json()["id"]
    assert read_internal_datetime(db, EVENTS_CHANGED_KEY) == fixed_now.value
    fixed_now.advance(minutes=5)
    client.patch(f"/api/promotions/{pid}", json={"description": "変更"})
    assert read_internal_datetime(db, EVENTS_CHANGED_KEY) == fixed_now.value
    fixed_now.advance(minutes=5)
    client.delete(f"/api/promotions/{pid}")
    assert read_internal_datetime(db, EVENTS_CHANGED_KEY) == fixed_now.value
    # 内部用のキーは設定 API に出さない
    assert not any(k.startswith("internal.") for k in client.get("/api/settings").json()["settings"])
