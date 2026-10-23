"""API の入出力で共通に使う型。"""
from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer

from smdx_api.clock import JST


def _to_jst_iso(v: datetime) -> str:
    return v.astimezone(JST).isoformat()


# 日時は Asia/Tokyo の ISO 8601 で返す(DB の接続設定によらず +09:00 で出す)
JstDatetime = Annotated[datetime, PlainSerializer(_to_jst_iso, return_type=str)]
