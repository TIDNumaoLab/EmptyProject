"""サンプルデータ一式の投入(PostgreSQL と smdx_sample が必要)。"""
from datetime import date

import pytest
from sqlalchemy import func, select

from smdx_api.commands.import_sample import import_sample
from smdx_api.db.models import (
    CalendarDay,
    ImportLog,
    InventorySnapshot,
    PosSale,
    Product,
    Promotion,
    WasteRecord,
    WeatherActual,
)
from smdx_api.settings.service import EVENTS_CHANGED_KEY, read_internal_datetime


def _count(db, model, *where):
    return db.scalar(select(func.count()).select_from(model).where(*where))


@pytest.fixture(scope="module")
def sample_dir(tmp_path_factory):
    gen = pytest.importorskip("smdx_sample.export")
    out = tmp_path_factory.mktemp("sample")
    gen.generate(date(2026, 10, 15), out, days=30)
    return out


@pytest.mark.db
def test_import_sample_end_to_end(db, sample_dir, fixed_now):
    counts = import_sample(db, sample_dir, fixed_now.value)
    csv_lines = {f: len((sample_dir / f).read_text(encoding="utf-8").splitlines()) - 1
                 for f in ["pos_sales.csv", "inventory.csv", "waste.csv", "weather.csv", "promotions.csv"]}
    assert counts["products"] == 15 and _count(db, Product) == 15
    assert counts["pos"] == csv_lines["pos_sales.csv"]
    assert counts["inventory"] == csv_lines["inventory.csv"] == _count(db, InventorySnapshot)
    assert counts["waste"] == csv_lines["waste.csv"] == _count(db, WasteRecord)
    assert counts["weather"] == 30 * 24 == _count(db, WeatherActual)
    assert counts["promotions"] == csv_lines["promotions.csv"] == _count(db, Promotion)
    # 祝日は import_holidays で入れるため、calendar.csv からは行事日だけを入れる
    assert _count(db, CalendarDay, CalendarDay.kind == "holiday") == 0
    assert counts["calendar"] == _count(db, CalendarDay, CalendarDay.kind == "event")
    # products 1 + pos 3部門 + inventory 2部門(生鮮のみ)+ waste 2部門(持越不可の FISH・DELI。VEG は廃棄行が無い)
    assert _count(db, ImportLog) == 8
    assert all(log.skipped_count == 0 and log.imported_by is None for log in db.scalars(select(ImportLog)))
    assert _count(db, PosSale, PosSale.sales_hour.is_not(None)) > 0
    assert read_internal_datetime(db, EVENTS_CHANGED_KEY) == fixed_now.value


@pytest.mark.db
def test_import_sample_twice_does_not_duplicate(db, sample_dir, fixed_now):
    first = import_sample(db, sample_dir, fixed_now.value)
    totals = {m: _count(db, m) for m in (Product, PosSale, InventorySnapshot, WasteRecord, WeatherActual, CalendarDay, Promotion)}
    second = import_sample(db, sample_dir, fixed_now.value)
    assert {m: _count(db, m) for m in totals} == totals
    assert second["promotions"] == 0 and first["promotions"] > 0


def test_import_sample_missing_folder(tmp_path):
    from smdx_api.commands import CommandError

    with pytest.raises(CommandError, match="products.csv がありません"):
        import_sample(None, tmp_path, None)
