"""特売・チラシ API の入出力。"""
from datetime import date

from pydantic import BaseModel, Field


class PromotionIn(BaseModel):
    product_code: str = Field(min_length=1)
    start_date: date
    end_date: date
    description: str = Field(min_length=1, max_length=128)


class PromotionPatch(BaseModel):
    product_code: str | None = Field(default=None, min_length=1)
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=128)


class PromotionOut(BaseModel):
    id: int
    product_code: str
    product_name: str
    department_code: str
    department_name: str
    start_date: date
    end_date: date
    description: str
    created_by_name: str | None
