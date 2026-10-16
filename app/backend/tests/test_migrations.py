"""マイグレーションの確認(PostgreSQL が必要)。"""
from datetime import date

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from smdx_api.db.base import Base
from smdx_api.db.models import Department, PosSale


@pytest.mark.db
def test_migration_matches_models(db_engine):
    with db_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


@pytest.mark.db
def test_departments_seeded(db):
    rows = {(d.code, d.business_type) for d in db.scalars(select(Department))}
    assert rows == {("VEG", "order"), ("FISH", "order"), ("DELI", "production")}


@pytest.mark.db
def test_pos_daily_row_cannot_duplicate(db, product_factory):
    p = product_factory()
    db.add(PosSale(sales_date=date(2026, 10, 15), sales_hour=None, product_id=p.id, quantity=1))
    db.flush()
    db.add(PosSale(sales_date=date(2026, 10, 15), sales_hour=None, product_id=p.id, quantity=2))
    with pytest.raises(IntegrityError):
        db.flush()
