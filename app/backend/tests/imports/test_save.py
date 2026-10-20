"""取込データの保存と上書き単位(PostgreSQL が必要)。"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from smdx_api.clock import JST
from smdx_api.db.models import InventorySnapshot, PosSale, Product, WasteRecord
from smdx_api.imports.parse import InventoryRow, PosRow, ProductRow, WasteRow
from smdx_api.imports.save import save_rows

D = date(2026, 10, 15)


def _pos(db, product_id):
    return db.execute(
        select(PosSale.sales_date, PosSale.sales_hour, PosSale.quantity)
        .where(PosSale.product_id == product_id)
        .order_by(PosSale.sales_date, PosSale.sales_hour.nulls_first())
    ).all()


@pytest.mark.db
def test_db_session_timezone_is_tokyo(db):
    assert db.execute(text("SELECT current_setting('TimeZone')")).scalar() == "Asia/Tokyo"


@pytest.mark.db
def test_pos_reimport_replaces_all_hours_of_date_product(db, product_factory):
    p = product_factory(code="VEG-001")
    other_day = date(2026, 10, 14)
    save_rows(db, "pos", [PosRow(D, 10, p.id, 3), PosRow(D, 11, p.id, 4), PosRow(other_day, None, p.id, 7)])
    save_rows(db, "pos", [PosRow(D, 12, p.id, 9)])
    assert _pos(db, p.id) == [(other_day, None, 7), (D, 12, 9)]


@pytest.mark.db
def test_pos_duplicate_rows_in_file_are_summed(db, product_factory):
    p = product_factory(code="VEG-001")
    n = save_rows(db, "pos", [PosRow(D, 10, p.id, 3), PosRow(D, 10, p.id, 2), PosRow(D, None, p.id, 1), PosRow(D, None, p.id, 1)])
    assert _pos(db, p.id) == [(D, None, 2), (D, 10, 5)]
    assert n == 2


@pytest.mark.db
def test_inventory_upsert_by_based_at_product_last_wins(db, product_factory):
    p = product_factory(code="VEG-001")
    t = datetime(2026, 10, 15, 19, 30, tzinfo=JST)
    save_rows(db, "inventory", [InventoryRow(t, p.id, 12), InventoryRow(t, p.id, 10)])
    save_rows(db, "inventory", [InventoryRow(t, p.id, 8)])
    rows = db.execute(select(InventorySnapshot.based_at, InventorySnapshot.quantity, InventorySnapshot.source)
                      .where(InventorySnapshot.product_id == p.id)).all()
    assert rows == [(t, 8, "csv")]


@pytest.mark.db
def test_waste_upsert_by_date_product(db, product_factory):
    p = product_factory(code="VEG-001")
    save_rows(db, "waste", [WasteRow(D, p.id, 3), WasteRow(D, p.id, 1)])
    save_rows(db, "waste", [WasteRow(D, p.id, 6)])
    assert db.execute(select(WasteRecord.waste_date, WasteRecord.quantity).where(WasteRecord.product_id == p.id)).all() == [(D, 6)]


@pytest.mark.db
def test_products_upsert(db, product_factory):
    product_factory(code="VEG-050", name="旧名", is_active=False)
    save_rows(db, "products", [
        ProductRow("VEG-050", "新名", "VEG", 6, 2, False, Decimal("98"), None),
        ProductRow("DELI-050", "焼き鳥", "DELI", 1, 0, False, None, Decimal("298")),
    ])
    p = db.scalar(select(Product).where(Product.product_code == "VEG-050"))
    assert (p.name, p.order_unit, p.lead_time_days, p.can_carry_over, p.cost_price, p.is_active) == ("新名", 6, 2, False, Decimal("98"), True)
    d = db.scalar(select(Product).where(Product.product_code == "DELI-050"))
    assert d.department.code == "DELI" and d.selling_price == Decimal("298")
