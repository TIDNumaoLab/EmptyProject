"""在庫の手入力(F-03)。"""
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from smdx_api.db.models import Department, Product
from smdx_api.imports.parse import InventoryRow
from smdx_api.imports.save import save_inventory


class ManualInputError(Exception):
    def __init__(self, product_code: str, reason: str) -> None:
        super().__init__(reason)
        self.product_code = product_code
        self.reason = reason


def _product_ids(db: Session, department: Department, codes: Sequence[str]) -> dict[str, int]:
    """商品コード → product_id。未登録・部門外の商品が1件でもあれば ManualInputError。"""
    found = {p.product_code: p for p in db.scalars(select(Product).where(Product.product_code.in_(codes)))}
    for code in codes:
        p = found.get(code)
        if p is None:
            raise ManualInputError(code, f"未登録の商品コードです: {code}")
        if p.department_id != department.id:
            raise ManualInputError(code, f"この部門の商品ではありません: {code}")
    return {code: found[code].id for code in codes}


def save_manual_inventory(
    db: Session, department: Department, based_at: datetime, items: Sequence[tuple[str, int]], user_id: int
) -> int:
    ids = _product_ids(db, department, [code for code, _ in items])
    rows = [InventoryRow(based_at, ids[code], qty) for code, qty in items]
    return save_inventory(db, rows, source="manual", entered_by=user_id)
