"""標準取込形式の検証(DB不要)。"""
from datetime import date, datetime
from decimal import Decimal

import pytest

from smdx_api.clock import JST
from smdx_api.imports.parse import (
    FileFormatError,
    InventoryRow,
    ParseContext,
    PosRow,
    ProductRow,
    RowError,
    WasteRow,
    parse_csv,
)

CTX = ParseContext(
    products={"VEG-001": (1, "VEG"), "FISH-001": (2, "FISH")},
    department_code="VEG",
    known_departments={"VEG", "FISH", "DELI"},
)
POS_HEADER = "sales_date,sales_time,product_code,quantity\n"


def test_pos_with_bom_and_hour_bucketing():
    data = ("﻿" + POS_HEADER + "2026-10-15,10:23,VEG-001,3\n2026-10-15,,VEG-001,5\n").encode("utf-8")
    r = parse_csv("pos", data, CTX)
    assert r.errors == []
    assert r.rows == [PosRow(date(2026, 10, 15), 10, 1, 3), PosRow(date(2026, 10, 15), None, 1, 5)]


@pytest.mark.parametrize("line,reason", [
    (",10:00,VEG-001,3", "必須項目がありません: sales_date"),
    ("2026-13-01,,VEG-001,3", "形式が不正です: sales_date"),
    ("2026/10/15,,VEG-001,3", "形式が不正です: sales_date"),
    ("2026-10-15,25:00,VEG-001,3", "形式が不正です: sales_time"),
    ("2026-10-15,,VEG-001,-1", "数量が負です"),
    ("2026-10-15,,VEG-001,1.5", "形式が不正です: quantity"),
    ("2026-10-15,,VEG-001,", "必須項目がありません: quantity"),
    ("2026-10-15,,XXX,1", "未登録の商品コードです: XXX"),
    ("2026-10-15,,FISH-001,1", "取込先の部門と異なる商品です: FISH-001"),
    ("2026-10-15", "必須項目がありません: product_code"),  # 列が足りない行
])
def test_pos_invalid_rows_are_skipped_with_reason(line, reason):
    data = (POS_HEADER + "2026-10-15,,VEG-001,1\n" + line + "\n").encode()
    r = parse_csv("pos", data, CTX)
    assert len(r.rows) == 1
    assert r.errors == [RowError(3, reason)]


def test_blank_lines_are_ignored_but_numbering_follows_file():
    data = (POS_HEADER + "\n2026-10-15,,XXX,1\n").encode()
    assert parse_csv("pos", data, CTX).errors == [RowError(3, "未登録の商品コードです: XXX")]


def test_columns_can_be_reordered_and_extra_columns_ignored():
    data = b"quantity,memo,product_code,sales_date\n4,x,VEG-001,2026-10-15\n"
    assert parse_csv("pos", data, CTX).rows == [PosRow(date(2026, 10, 15), None, 1, 4)]


def test_missing_required_column_rejects_file():
    with pytest.raises(FileFormatError, match="必須列がありません: quantity"):
        parse_csv("waste", b"waste_date,product_code\n2026-10-15,VEG-001\n", CTX)


def test_empty_file_rejects():
    with pytest.raises(FileFormatError, match="見出し行がありません"):
        parse_csv("waste", b"", CTX)


def test_non_utf8_rejects_file():
    with pytest.raises(FileFormatError, match="文字コードはUTF-8にしてください"):
        parse_csv("waste", "waste_date,product_code,quantity\n2026-10-15,キャベツ,1\n".encode("cp932"), CTX)


def test_products_validation():
    ctx = ParseContext(products={}, department_code=None, known_departments={"VEG"})
    data = (
        "product_code,product_name,department_code,order_unit,lead_time_days,can_carry_over,cost_price,selling_price\n"
        "VEG-009,にんじん,VEG,6,1,1,98,158.5\n"
        "VEG-010,ごぼう,XXX,1,1,1,,\n"
        "VEG-011,れんこん,VEG,0,1,1,,\n"
        "VEG-012,かぶ,VEG,1,1,2,,\n"
        "VEG-013,ねぎ,VEG,1,-1,1,,\n"
        "VEG-014,しそ,VEG,1,1,0,-5,\n"
    ).encode()
    r = parse_csv("products", data, ctx)
    assert r.rows == [ProductRow("VEG-009", "にんじん", "VEG", 6, 1, True, Decimal("98"), Decimal("158.5"))]
    assert r.errors == [
        RowError(3, "未登録の部門コードです: XXX"),
        RowError(4, "値が範囲外です: order_unit"),
        RowError(5, "形式が不正です: can_carry_over"),
        RowError(6, "値が範囲外です: lead_time_days"),
        RowError(7, "値が範囲外です: cost_price"),
    ]


def test_inventory_datetime_is_tokyo():
    r = parse_csv("inventory", b"based_at,product_code,quantity\n2026-10-15 19:30,VEG-001,12\n", CTX)
    assert r.rows == [InventoryRow(datetime(2026, 10, 15, 19, 30, tzinfo=JST), 1, 12)]


def test_inventory_datetime_format_strict():
    r = parse_csv("inventory", b"based_at,product_code,quantity\n2026-10-15T19:30,VEG-001,12\n", CTX)
    assert r.errors == [RowError(2, "形式が不正です: based_at")]


def test_waste_row():
    r = parse_csv("waste", b"waste_date,product_code,quantity\n2026-10-15,VEG-001,4\n", CTX)
    assert r.rows == [WasteRow(date(2026, 10, 15), 1, 4)]


@pytest.mark.parametrize("line,reason", [
    ("VEG-001," + "あ" * 65 + ",VEG,1,1,1,,", "値が範囲外です: product_name"),
    ("V" * 33 + ",にんじん,VEG,1,1,1,,", "値が範囲外です: product_code"),
    ("VEG-001,にんじん,VEG,1,1,1,1e20,", "値が範囲外です: cost_price"),
    ("VEG-001,にんじん,VEG,2147483648,1,1,,", "値が範囲外です: order_unit"),
])
def test_products_values_must_fit_db_columns(line, reason):
    ctx = ParseContext(products={}, department_code=None, known_departments={"VEG"})
    header = "product_code,product_name,department_code,order_unit,lead_time_days,can_carry_over,cost_price,selling_price\n"
    r = parse_csv("products", (header + line + "\n").encode(), ctx)
    assert r.rows == [] and r.errors == [RowError(2, reason)]


def test_quantity_must_fit_integer_column():
    r = parse_csv("pos", (POS_HEADER + "2026-10-15,,VEG-001,4900000000\n").encode(), CTX)
    assert r.errors == [RowError(2, "値が範囲外です: quantity")]
