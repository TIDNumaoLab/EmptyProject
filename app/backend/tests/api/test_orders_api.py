"""承認済み発注リストの API(詳細設計書「承認済み発注リスト(/orders/approved)」)。"""
from datetime import date

import pytest

from tests.conftest import jst


@pytest.mark.db
def test_approved_list(client, login, user_factory, proposal_factory, fixed_now):
    approver = user_factory(name="青果 一郎", departments=("VEG",))
    login(client, approver)
    proposal_factory(status="approved", product_code="VEG-002", approved_by=approver.id)
    proposal_factory(status="confirmed", product_code="VEG-001")
    proposal_factory(status="pending", product_code="VEG-003")
    proposal_factory(status="expired", product_code="VEG-004")
    rows = client.get("/api/orders/approved", params={"department_code": "VEG"}).json()
    assert [r["product_code"] for r in rows] == ["VEG-001", "VEG-002"]
    assert set(rows[1]) == {"product_code", "product_name", "target_date", "proposed_qty", "order_unit", "status",
                            "approved_by_name", "approved_at"}
    assert (rows[1]["approved_by_name"], rows[1]["status"], rows[1]["target_date"]) == ("青果 一郎", "approved", "2026-10-17")


@pytest.mark.db
def test_approved_list_target_date_and_default(client, login, user_factory, proposal_factory, fixed_now):
    login(client, user_factory(departments=("VEG",)))
    proposal_factory(status="confirmed", product_code="VEG-001", target=date(2026, 10, 15), deadline=jst(2026, 10, 14, 20))
    proposal_factory(status="approved", product_code="VEG-002", target=date(2026, 10, 18), deadline=jst(2026, 10, 17, 20))
    proposal_factory(status="approved", product_code="VEG-003", target=date(2026, 10, 17))
    # 対象日未指定は当日以降すべて(過去の対象日は出さない)
    rows = client.get("/api/orders/approved", params={"department_code": "VEG"}).json()
    assert [r["product_code"] for r in rows] == ["VEG-002", "VEG-003"]
    rows = client.get("/api/orders/approved", params={"department_code": "VEG", "target_date": "2026-10-18"}).json()
    assert [r["product_code"] for r in rows] == ["VEG-002"]


@pytest.mark.db
def test_approved_list_applies_deadlines(client, login, user_factory, proposal_factory, fixed_now):
    login(client, user_factory(departments=("VEG",)))
    proposal_factory(status="approved", product_code="VEG-001", deadline=jst(2026, 10, 16, 9))
    rows = client.get("/api/orders/approved", params={"department_code": "VEG"}).json()
    assert [r["status"] for r in rows] == ["confirmed"]


@pytest.mark.db
def test_approved_list_errors(client, login, user_factory, fixed_now):
    login(client, user_factory(departments=("VEG",)))
    assert client.get("/api/orders/approved", params={"department_code": "FISH"}).status_code == 403
    login(client, user_factory(role="manager", departments=()))
    res = client.get("/api/orders/approved", params={"department_code": "DELI"})
    assert res.status_code == 400 and res.json()["detail"] == "部門と業務の組合せが正しくありません"
