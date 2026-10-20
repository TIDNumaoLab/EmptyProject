"""在庫入力 API の入出力。"""
from pydantic import AwareDatetime, BaseModel, Field

from smdx_api.schemas.common import JstDatetime


class InventoryItem(BaseModel):
    product_code: str = Field(min_length=1)
    quantity: int = Field(ge=0)


class InventoryInput(BaseModel):
    department_code: str
    # タイムゾーンの無い日時は受け付けない(画面は +09:00 を付けて送る)
    based_at: AwareDatetime
    items: list[InventoryItem]


class SavedOut(BaseModel):
    saved: int


class LatestInventoryOut(BaseModel):
    product_code: str
    product_name: str
    quantity: int | None
    based_at: JstDatetime | None
