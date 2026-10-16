"""管理コマンド(画面を持たない初期設定・データ投入)。

実行: python -m smdx_api.commands <サブコマンド> ...
"""
from sqlalchemy.orm import Session

from smdx_api.db.session import make_engine, make_session_factory
from smdx_api.db.url import database_url_from_env


class CommandError(Exception):
    """利用者に見せる文言を持つコマンドの失敗。"""


def open_session() -> Session:
    """本体と同じ接続先(DATABASE_URL → .env → 既定値)の DB に接続する。"""
    return make_session_factory(make_engine(database_url_from_env()))()
