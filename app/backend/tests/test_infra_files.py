"""開発用 Docker Compose・Dockerfile の内容の確認(Docker が無い端末でも確かめられる範囲)。"""
from pathlib import Path

INFRA = Path(__file__).resolve().parents[2] / "infra"


def _read(name: str) -> str:
    return (INFRA / name).read_text(encoding="utf-8")


def test_compose_services_and_ports():
    text = _read("docker-compose.yml")
    for s in ["db:", "backend:", "frontend:", "postgres:16", "5432:5432", "8000:8000", "5173:5173", "alembic upgrade head"]:
        assert s in text, s


def test_backend_starts_with_app_factory():
    # 起動時に create_app() を呼ぶ(import しただけでは SESSION_SECRET を要求しない)
    assert "--factory smdx_api.main:create_app" in _read("docker-compose.yml")
    assert "--factory smdx_api.main:create_app" in _read("backend.Dockerfile")


def test_backend_image_is_python_311():
    text = _read("backend.Dockerfile")
    assert "python:3.11" in text
    assert "-c constraints.txt" in text


def test_frontend_image_is_node_20():
    text = _read("frontend.Dockerfile")
    assert "node:20" in text and "npm ci" in text
