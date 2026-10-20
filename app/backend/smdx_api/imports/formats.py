"""標準取込形式の列定義(詳細設計書「標準取込形式」)。

文字コード UTF-8(BOM可)、カンマ区切り、1行目は見出し行。日付は YYYY-MM-DD、日時は YYYY-MM-DD HH:MM(Asia/Tokyo)。
"""
from dataclasses import dataclass
from typing import Literal

Kind = Literal["products", "pos", "inventory", "waste"]
KINDS: tuple[Kind, ...] = ("products", "pos", "inventory", "waste")
ColumnType = Literal["str", "int", "decimal", "date", "datetime", "time", "bool01"]


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    type: ColumnType
    required: bool
    # 文字列の最大長(DB の列の長さ。超えると「値が範囲外です」)
    max_length: int | None = None


COLUMNS: dict[Kind, list[ColumnSpec]] = {
    "products": [
        ColumnSpec("product_code", "str", True, 32),
        ColumnSpec("product_name", "str", True, 64),
        ColumnSpec("department_code", "str", True, 16),
        ColumnSpec("order_unit", "int", True),
        ColumnSpec("lead_time_days", "int", True),
        ColumnSpec("can_carry_over", "bool01", True),
        ColumnSpec("cost_price", "decimal", False),
        ColumnSpec("selling_price", "decimal", False),
    ],
    "pos": [
        ColumnSpec("sales_date", "date", True),
        ColumnSpec("sales_time", "time", False),  # 空は日計
        ColumnSpec("product_code", "str", True),
        ColumnSpec("quantity", "int", True),
    ],
    "inventory": [
        ColumnSpec("based_at", "datetime", True),
        ColumnSpec("product_code", "str", True),
        ColumnSpec("quantity", "int", True),
    ],
    "waste": [
        ColumnSpec("waste_date", "date", True),
        ColumnSpec("product_code", "str", True),
        ColumnSpec("quantity", "int", True),
    ],
}
