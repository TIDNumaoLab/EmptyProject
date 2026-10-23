"""本体の試験で共通に使う fixture。

DB を使う試験は `@pytest.mark.db` を付け、環境変数 TEST_DATABASE_URL があるときだけ実行する。
試験用DBは public スキーマを作り直してから `alembic upgrade head` で作る(create_all は使わない)。
"""
import itertools
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from smdx_api.api.deps import get_db
from smdx_api.config import AppConfig
from smdx_api.auth.passwords import hash_password
from smdx_api.clock import JST, get_now
from smdx_api.db.models import Department, Product, User, UserDepartment
from smdx_api.db.session import make_engine
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
    # 本体と同じ接続設定(タイムゾーン Asia/Tokyo)にする
    engine = make_engine(url)
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


class FixedClock:
    """試験用の時計。API の現在時刻(get_now)をこの値に固定する。"""

    def __init__(self, value: datetime) -> None:
        self.value = value

    def set(self, value: datetime) -> None:
        self.value = value

    def advance(self, **delta) -> None:
        self.value = self.value + timedelta(**delta)


@pytest.fixture
def fixed_now() -> FixedClock:
    return FixedClock(datetime(2026, 10, 16, 10, 0, tzinfo=JST))


def _apply_overrides(request, app) -> None:
    if "db" in request.fixturenames:
        session = request.getfixturevalue("db")
        app.dependency_overrides[get_db] = lambda: session
    if "fixed_now" in request.fixturenames:
        clock = request.getfixturevalue("fixed_now")
        app.dependency_overrides[get_now] = lambda: clock.value


@pytest.fixture
def app(request, config):
    app = create_app(config)
    _apply_overrides(request, app)
    return app


@pytest.fixture
def client(app):
    """状態を変える API を通すため、既定で CSRF 用ヘッダを付けたクライアント。"""
    return TestClient(app, headers={"X-Requested-With": "smdx"})


@pytest.fixture
def make_client(request, config):
    """設定の一部を上書きしたアプリのクライアントを作る(db を使う試験では同じセッションを共有する)。"""

    def make(**overrides) -> TestClient:
        app = create_app(config.model_copy(update=overrides))
        _apply_overrides(request, app)
        return TestClient(app, headers={"X-Requested-With": "smdx"})

    return make


_login_ids = itertools.count(1)


@pytest.fixture
def user_factory(db):
    """利用者を1件作る。パスワードの既定は pass1234。"""

    def make(
        login_id: str | None = None,
        name: str = "試験 太郎",
        role: str = "staff",
        departments: tuple[str, ...] = ("VEG",),
        password: str = "pass1234",
        is_active: bool = True,
    ) -> User:
        u = User(
            login_id=login_id or f"user{next(_login_ids)}",
            name=name,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db.add(u)
        db.flush()
        for code in departments:
            dept = db.scalar(select(Department).where(Department.code == code))
            db.add(UserDepartment(user_id=u.id, department_id=dept.id))
        db.flush()
        db.expire(u, ["departments"])
        return u

    return make


@pytest.fixture
def login():
    """画面と同じ API でログインする。"""

    def do(client: TestClient, user: User, password: str = "pass1234"):
        res = client.post("/api/auth/login", json={"login_id": user.login_id, "password": password})
        assert res.status_code == 200, res.text
        return res

    return do


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
