"""アプリの生成、ミドルウェア、ルータ登録。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from smdx_api.api import routes_auth, routes_imports, routes_settings
from smdx_api.config import AppConfig, get_config
from smdx_api.db.session import make_engine, make_session_factory
from smdx_api.security import CSRF_HEADER, CsrfMiddleware

SESSION_COOKIE_NAME = "smdx_session"


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or get_config()
    app = FastAPI(title="スーパーマーケットDX API")
    app.state.config = config
    # 接続は最初の利用時に張られる(DB が無くても /health は応答する)
    app.state.session_factory = make_session_factory(make_engine(config.database_url))

    # add_middleware は後に追加したものほど外側になる。外側から CORS → CSRF → セッション の順にする
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.session_secret,
        session_cookie=SESSION_COOKIE_NAME,
        max_age=int(config.session_max_age_hours * 3600),
        same_site="lax",
        https_only=config.session_cookie_secure,
    )
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", CSRF_HEADER],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(routes_auth.router)
    app.include_router(routes_settings.router)
    app.include_router(routes_imports.router)
    return app
