"""標準取込形式CSVの検証。DB に依存しない。

不正な行(必須欠落、型不正、未登録の商品コード、負の数量、取込先の部門と異なる商品)はスキップし、
行番号(見出し行を1行目とした番号)と理由を返す。取込全体は止めない。
ファイル全体が読めない場合(UTF-8 でない、見出し行・必須列が無い)は FileFormatError。
"""
import csv
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from smdx_api.clock import JST
from smdx_api.imports.formats import COLUMNS, ColumnSpec, Kind

_INT_RE = re.compile(r"^-?\d+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) ([01]\d|2[0-3]):([0-5]\d)$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
# DB の列に収まる範囲(integer、numeric(12,2))。超える値は行ごとスキップする
INT_MAX = 2_147_483_647
DECIMAL_MAX = Decimal("9999999999.99")


class FileFormatError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class RowError:
    row: int
    reason: str


@dataclass(frozen=True)
class ProductRow:
    product_code: str
    name: str
    department_code: str
    order_unit: int
    lead_time_days: int
    can_carry_over: bool
    cost_price: Decimal | None
    selling_price: Decimal | None


@dataclass(frozen=True)
class PosRow:
    sales_date: date
    sales_hour: int | None  # 空は日計
    product_id: int
    quantity: int


@dataclass(frozen=True)
class InventoryRow:
    based_at: datetime
    product_id: int
    quantity: int


@dataclass(frozen=True)
class WasteRow:
    waste_date: date
    product_id: int
    quantity: int


Row = ProductRow | PosRow | InventoryRow | WasteRow


@dataclass(frozen=True)
class ParseContext:
    # 商品コード → (product_id, 部門コード)
    products: Mapping[str, tuple[int | None, str]]
    # 取込先の部門(商品マスタの取込では None)
    department_code: str | None
    known_departments: set[str]


@dataclass
class ParseResult:
    rows: list[Row] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)


class _RowInvalid(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


def _convert(spec: ColumnSpec, raw: str) -> Any:
    bad = _RowInvalid(f"形式が不正です: {spec.name}")
    out_of_range = _RowInvalid(f"値が範囲外です: {spec.name}")
    if spec.type == "str":
        if spec.max_length is not None and len(raw) > spec.max_length:
            raise out_of_range
        return raw
    if spec.type == "int":
        if not _INT_RE.match(raw):
            raise bad
        value = int(raw)
        if abs(value) > INT_MAX:
            raise out_of_range
        return value
    if spec.type == "decimal":
        try:
            value = Decimal(raw)
        except InvalidOperation:
            raise bad from None
        if not value.is_finite():
            raise bad
        if abs(value) > DECIMAL_MAX:
            raise out_of_range
        return value
    if spec.type == "date":
        if not _DATE_RE.match(raw):
            raise bad
        try:
            return date.fromisoformat(raw)
        except ValueError:
            raise bad from None
    if spec.type == "datetime":
        m = _DATETIME_RE.match(raw)
        if not m:
            raise bad
        try:
            d = date.fromisoformat(m.group(1))
        except ValueError:
            raise bad from None
        return datetime(d.year, d.month, d.day, int(m.group(2)), int(m.group(3)), tzinfo=JST)
    if spec.type == "time":
        m = _TIME_RE.match(raw)
        if not m:
            raise bad
        return time(int(m.group(1)), int(m.group(2)))
    if spec.type == "bool01":
        if raw not in ("0", "1"):
            raise bad
        return raw == "1"
    raise AssertionError(spec.type)


def _product(ctx: ParseContext, code: str) -> int:
    found = ctx.products.get(code)
    if found is None:
        raise _RowInvalid(f"未登録の商品コードです: {code}")
    product_id, dept = found
    if ctx.department_code is not None and dept != ctx.department_code:
        raise _RowInvalid(f"取込先の部門と異なる商品です: {code}")
    return product_id


def _non_negative(v: dict, *names: str) -> None:
    for name in names:
        if v[name] is not None and v[name] < 0:
            raise _RowInvalid(f"値が範囲外です: {name}")


def _build(kind: Kind, v: dict, ctx: ParseContext) -> Row:
    if kind == "products":
        if v["order_unit"] < 1:
            raise _RowInvalid("値が範囲外です: order_unit")
        _non_negative(v, "lead_time_days", "cost_price", "selling_price")
        if v["department_code"] not in ctx.known_departments:
            raise _RowInvalid(f"未登録の部門コードです: {v['department_code']}")
        return ProductRow(v["product_code"], v["product_name"], v["department_code"], v["order_unit"],
                          v["lead_time_days"], v["can_carry_over"], v["cost_price"], v["selling_price"])
    if v["quantity"] < 0:
        raise _RowInvalid("数量が負です")
    product_id = _product(ctx, v["product_code"])
    if kind == "pos":
        hour = v["sales_time"].hour if v["sales_time"] is not None else None
        return PosRow(v["sales_date"], hour, product_id, v["quantity"])
    if kind == "inventory":
        return InventoryRow(v["based_at"], product_id, v["quantity"])
    return WasteRow(v["waste_date"], product_id, v["quantity"])


def parse_csv(kind: Kind, data: bytes, ctx: ParseContext) -> ParseResult:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FileFormatError("文字コードはUTF-8にしてください") from None
    lines = text.splitlines()
    reader = csv.reader(lines)
    header = next(reader, None)
    if not header or all(not h.strip() for h in header):
        raise FileFormatError("見出し行がありません")
    index = {h.strip(): i for i, h in enumerate(header)}
    specs = COLUMNS[kind]
    missing = [s.name for s in specs if s.required and s.name not in index]
    if missing:
        raise FileFormatError(f"必須列がありません: {', '.join(missing)}")

    result = ParseResult()
    for row_no, cells in enumerate(reader, start=2):
        if all(not c.strip() for c in cells):
            continue  # 空行は無視する(行番号はファイルの行に合わせる)
        try:
            values = {}
            for spec in specs:
                i = index.get(spec.name)
                raw = cells[i].strip() if i is not None and i < len(cells) else ""
                if raw == "":
                    if spec.required:
                        raise _RowInvalid(f"必須項目がありません: {spec.name}")
                    values[spec.name] = None
                else:
                    values[spec.name] = _convert(spec, raw)
            result.rows.append(_build(kind, values, ctx))
        except _RowInvalid as e:
            result.errors.append(RowError(row_no, e.reason))
    return result
