"""認証 API の入出力。"""
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login_id: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1)


class DepartmentRef(BaseModel):
    code: str
    name: str
    business_type: Literal["order", "production"]


class MeResponse(BaseModel):
    user_id: int
    name: str
    role: Literal["staff", "manager"]
    # 所属部門
    departments: list[DepartmentRef]
    # 操作できる部門(店長は全部門、担当者は所属部門)
    accessible_departments: list[DepartmentRef]
