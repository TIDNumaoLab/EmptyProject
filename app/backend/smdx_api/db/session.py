"""DB 接続とセッションの生成。"""
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

# 日時はすべて Asia/Tokyo で扱う。DB 側の日付変換(::date など)と返す日時もこれに揃える
DB_TIMEZONE = "Asia/Tokyo"


def make_engine(url: str) -> Engine:
    connect_args = {"options": f"-c timezone={DB_TIMEZONE}"} if url.startswith("postgresql") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
