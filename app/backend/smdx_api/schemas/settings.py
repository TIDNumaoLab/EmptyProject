"""設定 API の入出力。値の形式は settings/values.py の説明に従う。"""
from typing import Any

from pydantic import BaseModel


class SettingsBody(BaseModel):
    settings: dict[str, Any]
