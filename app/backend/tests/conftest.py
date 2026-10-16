"""本体の試験で共通に使う fixture。

DB を使う試験は `@pytest.mark.db` を付け、環境変数 TEST_DATABASE_URL があるときだけ実行する。
試験用DBは public スキーマを作り直してから `alembic upgrade head` で作る(create_all は使わない)。
"""
import itertools
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from smdx_api.api.deps import get_db
from smdx_api.config import AppConfig
from smdx_api.db.models import Department, Product
from smdx_api.main import create_app

TEST_SESSION_SECRET = "test-secret-" + "x" * 32
BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def config(monkeypatch) -> AppConfig:
    """試験用の設定。.env は読まず、SESSION_SECRET だけを与える。"""
    monkeypatch.setenv("SESSION_SECRET", TEST_SESSION_SECRET)
    return AppConfig(_env_file=None)


@pytest.fixture(scope="session")
def db_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL が未設定のため DB 試験をスキップ")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine):
    """試験ごとのセッション。試験後にロールバックし、DB を元に戻す。"""
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def app(request, config):
    app = create_app(config)
    if "db" in request.fixturenames:
        session = request.getfixturevalue("db")
        app.dependency_overrides[get_db] = lambda: session
    return app


@pytest.fixture
def client(app):
    """状態を変える API を通すため、既定で CSRF 用ヘッダを付けたクライアント。"""
    return TestClient(app, headers={"X-Requested-With": "smdx"})


_codes = itertools.count(1)


@pytest.fixture
def product_factory(db):
    """商品を1件作る。既定は部門 VEG・入数1・リードタイム1日・持越可。"""

    def make(code: str | None = None, department: str = "VEG", is_active: bool = True, **fields) -> Product:
        dept = db.scalar(select(Department).where(Department.code == department))
        values = dict(
            product_code=code or f"{department}-T{next(_codes):03d}",
            name=fields.pop("name", "試験用商品"),
            department_id=dept.id,
            order_unit=1,
            lead_time_days=0 if dept.business_type == "production" else 1,
            can_carry_over=dept.business_type == "order",
            is_active=is_active,
        )
        values.update(fields)
        p = Product(**values)
        db.add(p)
        db.flush()
        return p

    return make
