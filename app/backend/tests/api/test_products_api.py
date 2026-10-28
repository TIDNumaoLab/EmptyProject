"""商品一覧(PostgreSQL が必要)。"""
from decimal import Decimal

import pytest


def test_products_requires_login(client):
    assert client.get("/api/products").status_code == 401


@pytest.mark.db
def test_products_list_filters_department_and_inactive(client, login, user_factory, product_factory):
    product_factory(code="VEG-002", name="トマト", order_unit=4, cost_price=Decimal("120"), selling_price=Decimal("198.5"))
    product_factory(code="VEG-001", name="キャベツ")
    product_factory(code="VEG-003", is_active=False)
    product_factory(code="FISH-001", department="FISH")
    login(client, user_factory(departments=("FISH",)))  # 一覧は全員が全部門を見られる
    rows = client.get("/api/products", params={"department_code": "VEG"}).json()
    assert [p["product_code"] for p in rows] == ["VEG-001", "VEG-002"]
    assert rows[1] == {
        "product_code": "VEG-002", "name": "トマト", "department_code": "VEG", "department_name": "青果", "order_unit": 4, "lead_time_days": 1,
        "can_carry_over": True, "cost_price": 120.0, "selling_price": 198.5, "is_active": True,
    }
    assert len(client.get("/api/products").json()) == 3


@pytest.mark.db
def test_products_unknown_department_404(client, login, user_factory):
    login(client, user_factory())
    res = client.get("/api/products", params={"department_code": "NONE"})
    assert res.status_code == 404 and res.json()["detail"] == "対象が見つかりません"
