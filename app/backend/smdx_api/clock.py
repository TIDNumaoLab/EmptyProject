"""現在時刻の取得。日時はすべて Asia/Tokyo で扱う。

現在時刻は必ずここから取り、試験では get_now を差し替える。
"""
from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def now() -> datetime:
    return datetime.now(JST)


def get_now() -> datetime:
    """FastAPI の依存関係として使う現在時刻。"""
    return now()
