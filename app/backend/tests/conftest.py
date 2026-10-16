"""本体の試験で共通に使う fixture。"""
import pytest
from fastapi.testclient import TestClient

from smdx_api.config import AppConfig
from smdx_api.main import create_app

TEST_SESSION_SECRET = "test-secret-" + "x" * 32


@pytest.fixture
def config(monkeypatch) -> AppConfig:
    """試験用の設定。.env は読まず、SESSION_SECRET だけを与える。"""
    monkeypatch.setenv("SESSION_SECRET", TEST_SESSION_SECRET)
    return AppConfig(_env_file=None)


@pytest.fixture
def app(config):
    return create_app(config)


@pytest.fixture
def client(app):
    """状態を変える API を通すため、既定で CSRF 用ヘッダを付けたクライアント。"""
    return TestClient(app, headers={"X-Requested-With": "smdx"})
