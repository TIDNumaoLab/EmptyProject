"""役割と所属部門による権限の判定(要件定義書「利用者と権限」)。"""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Principal:
    """ログイン中の利用者。"""

    user_id: int
    name: str
    role: Literal["staff", "manager"]
    department_codes: frozenset[str]

    @property
    def is_manager(self) -> bool:
        return self.role == "manager"


def can_access_department(p: Principal, department_code: str) -> bool:
    """店長は全部門、担当者は所属部門のみ(部門コードは完全一致で比べる)。"""
    return p.is_manager or department_code in p.department_codes
