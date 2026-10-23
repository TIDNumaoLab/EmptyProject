"""DB の接続先。本体・マイグレーション・管理コマンドで同じ規則にする。

優先順は 環境変数 DATABASE_URL → カレントの .env → 既定値。
マイグレーションと管理コマンドは SESSION_SECRET を必要としないため、AppConfig 全体ではなく接続先だけを読む。
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/supermarket_dx"


class _DatabaseOnly(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = DEFAULT_DATABASE_URL


def database_url_from_env() -> str:
    return _DatabaseOnly().database_url
