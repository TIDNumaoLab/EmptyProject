"""Alembic の実行環境。

接続先の優先順: alembic の設定 sqlalchemy.url(試験で指定)→ 環境変数 DATABASE_URL → 既定値。
SESSION_SECRET を要求しないよう、AppConfig は使わずに環境変数を直接読む。
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from smdx_api.db.base import Base
import smdx_api.db.models  # noqa: F401  モデルを Base.metadata に登録する

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/supermarket_dx"

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
