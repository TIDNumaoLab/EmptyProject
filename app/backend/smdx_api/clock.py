"""現在時刻の取得。日時はすべて Asia/Tokyo で扱う(店舗は日本国内のため、環境変数 TZ によらず固定)。

現在時刻は必ずここから取り、試験では get_now を差し替える。
"""
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def now() -> datetime:
    return datetime.now(JST)


def get_now() -> datetime:
    """FastAPI の依存関係として使う現在時刻。"""
    return now()


def get_clock() -> Callable[[], datetime]:
    """FastAPI の依存関係として使う時計(要求の後で時刻を取り直す処理用。裏で動くジョブの終了日時など)。"""
    return now
