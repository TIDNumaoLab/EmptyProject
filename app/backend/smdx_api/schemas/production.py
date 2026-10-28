"""惣菜の陳列残数の入力。"""
from datetime import date

from pydantic import AwareDatetime, BaseModel

from smdx_api.schemas.inventory import InventoryItem
from smdx_api.schemas.proposals import JobOut


class DisplayStockInput(BaseModel):
    department_code: str
    target_date: date
    # タイムゾーンの無い日時は受け付けない(画面は保存時の時刻を +09:00 付きで送る)
    entered_at: AwareDatetime
    items: list[InventoryItem]


class DisplayStockOut(BaseModel):
    saved: int
    job: JobOut
