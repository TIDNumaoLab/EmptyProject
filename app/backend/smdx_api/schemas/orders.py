"""承認済み発注リスト API の出力。"""
import datetime as dt

from pydantic import BaseModel

from smdx_api.schemas.common import JstDatetime


class ApprovedOrderOut(BaseModel):
    product_code: str
    product_name: str
    target_date: dt.date
    proposed_qty: int
    order_unit: int
    status: str
    approved_by_name: str | None
    approved_at: JstDatetime | None
