"""管理コマンド(画面を持たない初期設定・データ投入)。

実行: python -m smdx_api.commands <サブコマンド> ...
"""
import os

from sqlalchemy.orm import Session

from smdx_api.config import AppConfig
from smdx_api.db.session import make_engine, make_session_factory


class CommandError(Exception):
    """利用者に見せる文言を持つコマンドの失敗。"""


def open_session() -> Session:
    """環境変数 DATABASE_URL の DB に接続する。

    コマンドは SESSION_SECRET を必要としないため、AppConfig 全体は読まずに既定値だけを借りる。
    """
    url = os.environ.get("DATABASE_URL") or AppConfig.model_fields["database_url"].default
    return make_session_factory(make_engine(url))()
