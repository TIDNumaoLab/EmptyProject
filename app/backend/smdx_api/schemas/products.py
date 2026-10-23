"""商品一覧 API の出力。"""
from pydantic import BaseModel


class ProductOut(BaseModel):
    product_code: str
    name: str
    department_code: str
    order_unit: int
    lead_time_days: int
    can_carry_over: bool
    cost_price: float | None
    selling_price: float | None
    is_active: bool
