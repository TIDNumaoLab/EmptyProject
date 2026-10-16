"""テーブル定義の確認(DB不要)。"""
import pytest
from sqlalchemy import UniqueConstraint

from smdx_api.db.base import Base
import smdx_api.db.models  # noqa: F401  モデルを Base.metadata に登録する

EXPECTED = {
    "departments", "users", "user_departments", "products", "pos_sales", "inventory_snapshots",
    "waste_records", "display_stock_entries", "weather_forecasts", "weather_actuals", "calendar_days",
    "promotions", "forecasts", "proposals", "proposal_histories", "proposal_jobs", "import_logs", "settings",
}


def test_all_18_tables_defined():
    assert set(Base.metadata.tables) == EXPECTED


@pytest.mark.parametrize("table,cols", [
    ("pos_sales", ["sales_date", "sales_hour", "product_id"]),
    ("proposals", ["department_id", "product_id", "target_date", "time_band"]),
])
def test_nulls_not_distinct_unique(table, cols):
    uc = [c for c in Base.metadata.tables[table].constraints if isinstance(c, UniqueConstraint)]
    match = [c for c in uc if [col.name for col in c.columns] == cols]
    assert match and match[0].dialect_options["postgresql"]["nulls_not_distinct"] is True


def test_every_table_has_timestamps():
    for t in Base.metadata.tables.values():
        assert {"id", "created_at", "updated_at"} <= set(t.c.keys())
        assert t.c.created_at.type.timezone is True
