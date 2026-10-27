"""提案の状態・警告コード・修正理由(詳細設計書「欠損時の扱い」「データ項目定義(proposals)」)。"""
from typing import Literal

from smdx_api.db.models import ADJUST_REASONS as _ADJUST_REASONS
from smdx_api.weather_client.service import MAX_DAYS_AHEAD as _MAX_DAYS_AHEAD

Status = Literal["pending", "approved", "confirmed", "expired"]

WARNING_CODES = ("NO_INVENTORY", "NO_HISTORY", "NO_WEATHER", "STALE_POS")
# 警告の付いた提案はすべて一括承認の対象外
BULK_EXCLUDED = set(WARNING_CODES)
ADJUST_REASONS = _ADJUST_REASONS
# 対象日は当日〜15日先(気象予報の提供範囲)
MAX_DAYS_AHEAD = _MAX_DAYS_AHEAD
