"""在庫の手入力と最新の在庫(PostgreSQL が必要)。"""
from datetime import datetime

import pytest
from sqlalchemy import select

from smdx_api.clock import JST
from smdx_api.db.models import InventorySnapshot


def _body(based_at, items, department_code="VEG"):
    return {"department_code": department_code, "based_at": based_at, "items": items}


@pytest.mark.db
def test_manual_inventory_saved_and_latest_listed(client, login, user_factory, product_factory, db):
    product_factory(code="VEG-001", name="キャベツ")
    product_factory(code="VEG-002", name="トマト")
    u = user_factory(departments=("VEG",))
    login(client, u)
    body = _body("2026-10-15T19:30:00+09:00", [{"product_code": "VEG-001", "quantity": 12}])
    assert client.put("/api/inventory", json=body).json() == {"saved": 1}
    body = _body("2026-10-15T20:00:00+09:00", [{"product_code": "VEG-001", "quantity": 8}])
    client.put("/api/inventory", json=body)
    latest = client.get("/api/inventory", params={"department_code": "VEG"}).json()
    assert latest == [
        {"product_code": "VEG-001", "product_name": "キャベツ", "quantity": 8, "based_at": "2026-10-15T20:00:00+09:00"},
        {"product_code": "VEG-002", "product_name": "トマト", "quantity": None, "based_at": None},
    ]
    snap = db.scalar(select(InventorySnapshot).where(InventorySnapshot.based_at == datetime(2026, 10, 15, 20, tzinfo=JST)))
    assert (snap.source, snap.entered_by) == ("manual", u.id)


@pytest.mark.db
def test_manual_inventory_overwrites_same_based_at(client, login, user_factory, product_factory):
    product_factory(code="VEG-001")
    login(client, user_factory(departments=("VEG",)))
    for q in (5, 7):
        client.put("/api/inventory", json=_body("2026-10-15T19:30:00+09:00", [{"product_code": "VEG-001", "quantity": q}]))
    assert client.get("/api/inventory", params={"department_code": "VEG"}).json()[0]["quantity"] == 7


@pytest.mark.db
@pytest.mark.parametrize("items,expect", [
    ([{"product_code": "FISH-001", "quantity": 1}], "この部門の商品ではありません: FISH-001"),
    ([{"product_code": "XXX", "quantity": 1}], "未登録の商品コードです: XXX"),
])
def test_manual_inventory_rejects_bad_products(client, login, user_factory, product_factory, db, items, expect):
    product_factory(code="VEG-001")
    product_factory(code="FISH-001", department="FISH")
    login(client, user_factory(departments=("VEG",)))
    res = client.put("/api/inventory", json=_body("2026-10-15T19:30:00+09:00", [{"product_code": "VEG-001", "quantity": 1}] + items))
    assert res.status_code == 422 and res.json()["detail"] == expect
    # 1件でも不正なら何も保存しない
    assert db.scalar(select(InventorySnapshot)) is None


@pytest.mark.db
@pytest.mark.parametrize("based_at,qty", [("2026-10-15T19:30:00+09:00", -1), ("2026-10-15T19:30:00", 1)])
def test_negative_quantity_or_naive_datetime_is_422(client, login, user_factory, product_factory, based_at, qty):
    product_factory(code="VEG-001")
    login(client, user_factory(departments=("VEG",)))
    res = client.put("/api/inventory", json=_body(based_at, [{"product_code": "VEG-001", "quantity": qty}]))
    assert res.status_code == 422


@pytest.mark.db
def test_manual_inventory_other_department_forbidden(client, login, user_factory):
    login(client, user_factory(departments=("VEG",)))
    res = client.put("/api/inventory", json=_body("2026-10-15T19:30:00+09:00", [], department_code="FISH"))
    assert res.status_code == 403
    assert client.get("/api/inventory", params={"department_code": "FISH"}).status_code == 403
