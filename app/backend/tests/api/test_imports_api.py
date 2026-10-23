"""CSV取込と取込履歴のAPI。"""
import pytest
from sqlalchemy import func, select

from smdx_api.db.models import ImportLog

WASTE_CSV = b"waste_date,product_code,quantity\n2026-10-15,VEG-001,4\n2026-10-15,XXX,1\n"


def _upload(client, kind, data, department_code=None, name="data.csv"):
    form = {"department_code": department_code} if department_code else {}
    return client.post(f"/api/imports/{kind}", files={"file": (name, data, "text/csv")}, data=form)


def test_import_requires_login(client):
    assert _upload(client, "waste", WASTE_CSV, "VEG").status_code == 401


@pytest.mark.db
def test_import_api_records_log(client, login, user_factory, product_factory):
    product_factory(code="VEG-001")
    login(client, user_factory(name="青果 太郎", departments=("VEG",)))
    res = _upload(client, "waste", WASTE_CSV, "VEG", name="waste.csv")
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["kind"], body["department_code"], body["file_name"]) == ("waste", "VEG", "waste.csv")
    assert (body["imported_count"], body["skipped_count"]) == (1, 1)
    assert body["errors"] == [{"row": 3, "reason": "未登録の商品コードです: XXX"}]
    assert body["imported_by_name"] == "青果 太郎"
    assert body["finished_at"].endswith("+09:00")
    history = client.get("/api/imports", params={"kind": "waste"}).json()
    assert history[0]["id"] == body["id"]


@pytest.mark.db
def test_staff_cannot_import_products_or_other_department(client, login, user_factory):
    login(client, user_factory(departments=("VEG",)))
    f = b"product_code\n"
    assert _upload(client, "products", f).status_code == 403
    assert _upload(client, "pos", f, "FISH").status_code == 403
    assert _upload(client, "pos", f, "NONE").status_code == 404


@pytest.mark.db
def test_department_code_required_except_products(client, login, user_factory):
    login(client, user_factory(departments=("VEG",)))
    res = _upload(client, "pos", b"sales_date\n")
    assert res.status_code == 422 and res.json()["detail"] == "部門を指定してください"


@pytest.mark.db
def test_unknown_kind_is_422(client, login, user_factory):
    login(client, user_factory(departments=("VEG",)))
    assert _upload(client, "orders", WASTE_CSV, "VEG").status_code == 422


@pytest.mark.db
def test_bad_header_is_422_without_log(client, login, user_factory, db):
    login(client, user_factory(departments=("VEG",)))
    res = _upload(client, "pos", b"a,b\n1,2\n", "VEG")
    assert res.status_code == 422 and "必須列がありません" in res.json()["detail"]
    assert db.scalar(select(func.count()).select_from(ImportLog)) == 0


@pytest.mark.db
def test_too_large_file_is_413_without_log(make_client, login, user_factory, product_factory, db):
    # 上限 IMPORT_MAX_MB を超えるファイルは読み切らずに拒否する(取込履歴は残さない)
    client = make_client(import_max_mb=0.001)  # 約1KB
    login(client, user_factory(departments=("VEG",)))
    product_factory("VEG-001", "VEG")
    big = b"waste_date,product_code,quantity\n" + b"2026-10-15,VEG-001,4\n" * 100
    res = _upload(client, "waste", big, "VEG")
    assert res.status_code == 413 and "上限" in res.json()["detail"]
    assert db.scalar(select(func.count()).select_from(ImportLog)) == 0
    # 上限以内なら取り込める
    assert _upload(client, "waste", WASTE_CSV, "VEG").status_code == 200


@pytest.mark.db
def test_manager_imports_products(client, login, user_factory, db):
    login(client, user_factory(role="manager", departments=()))
    csv = ("product_code,product_name,department_code,order_unit,lead_time_days,can_carry_over,cost_price,selling_price\n"
           "VEG-001,キャベツ,VEG,6,1,1,98,158\n").encode()
    body = _upload(client, "products", csv).json()
    assert (body["kind"], body["department_code"], body["imported_count"]) == ("products", None, 1)


@pytest.mark.db
def test_history_visibility_for_staff(client, login, user_factory, product_factory, make_client):
    product_factory(code="VEG-001")
    product_factory(code="FISH-001", department="FISH")
    manager = make_client()
    login(manager, user_factory(role="manager", departments=()))
    _upload(manager, "waste", b"waste_date,product_code,quantity\n2026-10-15,FISH-001,1\n", "FISH")
    _upload(manager, "waste", b"waste_date,product_code,quantity\n2026-10-15,VEG-001,1\n", "VEG")
    _upload(manager, "products", ("product_code,product_name,department_code,order_unit,lead_time_days,can_carry_over\n"
                                  "VEG-002,トマト,VEG,4,1,1\n").encode())
    login(client, user_factory(departments=("VEG",)))
    seen = {(h["kind"], h["department_code"]) for h in client.get("/api/imports").json()}
    assert seen == {("waste", "VEG"), ("products", None)}
    assert client.get("/api/imports", params={"department_code": "FISH"}).status_code == 403


def test_import_handler_runs_in_threadpool():
    # 同期の DB 処理を async の関数で行うと、取込の間 API 全体が止まる(サーバーは1プロセス)
    import inspect

    from smdx_api.api import routes_imports

    assert not inspect.iscoroutinefunction(routes_imports.import_csv)


@pytest.mark.db
def test_stored_errors_are_capped(client, login, user_factory, product_factory, db):
    product_factory(code="VEG-001")
    login(client, user_factory(departments=("VEG",)))
    rows = "".join(f"2026-10-15,X{i},1\n" for i in range(150))
    body = _upload(client, "waste", ("waste_date,product_code,quantity\n" + rows).encode(), "VEG").json()
    assert body["skipped_count"] == 150 and len(body["errors"]) == 100
    assert body["errors"][0] == {"row": 2, "reason": "未登録の商品コードです: X0"}


@pytest.mark.db
def test_long_file_name_is_truncated(client, login, user_factory, product_factory):
    product_factory(code="VEG-001")
    login(client, user_factory(departments=("VEG",)))
    res = _upload(client, "waste", WASTE_CSV, "VEG", name="あ" * 300 + ".csv")
    assert res.status_code == 200 and len(res.json()["file_name"]) == 255
