"""惣菜の陳列残数の入力。"""
from datetime import date

from pydantic import BaseModel

from smdx_api.schemas.common import JstDatetime
from smdx_api.schemas.inventory import InventoryItem
from smdx_api.schemas.proposals import JobOut


class DisplayStockInput(BaseModel):
    department_code: str
    target_date: date
    # 入力時刻は受け取らない(保存時のサーバーの時刻を使い、端末の時計のずれで割り当て先の時間帯が変わらないようにする)
    items: list[InventoryItem]


class DisplayStockOut(BaseModel):
    saved: int
    entered_at: JstDatetime
    job: JobOut
