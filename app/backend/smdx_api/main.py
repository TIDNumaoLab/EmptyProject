"""アプリの生成とルータ登録。"""
from fastapi import FastAPI

from smdx_api.config import AppConfig, get_config


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or get_config()
    app = FastAPI(title="スーパーマーケットDX API")
    app.state.config = config

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
