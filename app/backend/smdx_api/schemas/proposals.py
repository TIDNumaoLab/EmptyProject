"""提案 API の入出力(詳細設計書「API仕様」の提案(proposal)の項目)。"""
import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from smdx_api.proposals.codes import ADJUST_REASONS
from smdx_api.schemas.common import JstDatetime

StatusFilter = Literal["pending", "approved", "confirmed", "expired"]
AdjustReason = Literal[ADJUST_REASONS]  # type: ignore[valid-type]


class ProposalOut(BaseModel):
    id: int
    department_code: str
    product_code: str
    product_name: str
    target_date: dt.date
    time_band: int | None
    proposed_qty: int
    original_qty: int
    recalculated_qty: int | None
    is_adjusted: bool
    adjust_reason: str | None
    adjust_note: str | None
    status: str
    deadline: JstDatetime
    approved_by: int | None
    approved_by_name: str | None
    approved_at: JstDatetime | None
    warnings: list[str]
    order_unit: int
    calculated_at: JstDatetime
    created_at: JstDatetime
    updated_at: JstDatetime
    # 根拠(basis)を平坦に並べたもの。日時は ISO 8601 文字列のまま
    predicted_qty: float | None = None
    model_version: str | None = None
    is_baseline: bool | None = None
    weather_code: int | None = None
    weather_label: str | None = None
    temperature: float | None = None
    precipitation: float | None = None
    precipitation_probability: float | None = None
    is_holiday: bool | None = None
    is_event_day: bool | None = None
    holiday_name: str | None = None
    is_promotion: bool | None = None
    sales_lag_7d: float | None = None
    inventory_qty: int | None = None
    inventory_based_at: str | None = None
    backlog_qty: int | None = None
    carry_over_qty: float | None = None
    expected_sales_qty: float | None = None
    display_stock_qty: int | None = None
    weather_fetched_at: str | None = None


class JobOut(BaseModel):
    id: int
    status: str
    processed: int
    total: int
    error: str | None


class FreshnessOut(BaseModel):
    calculated_at: JstDatetime | None
    weather_fetched_at: JstDatetime | None
    inventory_based_at: JstDatetime | None


class ProposalListOut(BaseModel):
    proposals: list[ProposalOut]
    freshness: FreshnessOut
    job: JobOut | None
    notice: str | None


class RecalculateIn(BaseModel):
    department_code: str
    target_date: dt.date | None = None


class JobResponse(BaseModel):
    job: JobOut


class AdjustIn(BaseModel):
    # DB の integer に収まる範囲
    quantity: int = Field(ge=0, le=2_147_483_647)
    reason: AdjustReason
    reason_note: str | None = Field(default=None, max_length=128)


class ApproveIn(BaseModel):
    # 画面に表示していた提案数(裏の再計算で変わっていれば 409)
    expected_qty: int
    confirm_warnings: bool = False


class BulkApproveItem(BaseModel):
    id: int
    expected_qty: int


class BulkApproveIn(BaseModel):
    items: list[BulkApproveItem] = Field(min_length=1, max_length=1000)


class SkippedOut(BaseModel):
    id: int
    reason: str


class BulkApproveOut(BaseModel):
    approved_ids: list[int]
    skipped: list[SkippedOut]
