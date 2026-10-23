"""初回: 18テーブルの作成と部門の初期データ

Revision ID: 0001
Revises:
Create Date: 2026-10-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# 部門は取込・画面で登録しないため、ここで投入する(実装計画 段階1 の判断 1-3)
DEPARTMENTS = [
    {"code": "VEG", "name": "青果", "business_type": "order"},
    {"code": "FISH", "name": "鮮魚", "business_type": "order"},
    {"code": "DELI", "name": "惣菜", "business_type": "production"},
]


def upgrade() -> None:
    op.create_table('calendar_days',
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('holiday', 'event')", name=op.f('ck_calendar_days_kind')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calendar_days')),
    sa.UniqueConstraint('date', 'kind', name=op.f('uq_calendar_days_date_kind'))
    )
    op.create_table('departments',
    sa.Column('code', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('business_type', sa.String(length=16), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("business_type IN ('order', 'production')", name=op.f('ck_departments_business_type')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_departments')),
    sa.UniqueConstraint('code', name=op.f('uq_departments_code'))
    )
    op.create_table('users',
    sa.Column('login_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('staff', 'manager')", name=op.f('ck_users_role')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('login_id', name=op.f('uq_users_login_id'))
    )
    op.create_table('weather_actuals',
    sa.Column('observed_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('weather_code', sa.Integer(), nullable=False),
    sa.Column('temperature', sa.Float(), nullable=False),
    sa.Column('precipitation_probability', sa.Float(), nullable=True),
    sa.Column('precipitation', sa.Float(), nullable=True),
    sa.Column('source', sa.String(length=32), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('archive', 'historical_forecast')", name=op.f('ck_weather_actuals_source')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_weather_actuals')),
    sa.UniqueConstraint('observed_time', name=op.f('uq_weather_actuals_observed_time'))
    )
    op.create_table('weather_forecasts',
    sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('forecast_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('weather_code', sa.Integer(), nullable=False),
    sa.Column('temperature', sa.Float(), nullable=False),
    sa.Column('precipitation_probability', sa.Float(), nullable=True),
    sa.Column('precipitation', sa.Float(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_weather_forecasts')),
    sa.UniqueConstraint('fetched_at', 'forecast_time', name=op.f('uq_weather_forecasts_fetched_at_forecast_time'))
    )
    op.create_table('import_logs',
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('department_id', sa.Integer(), nullable=True),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('imported_count', sa.Integer(), nullable=False),
    sa.Column('skipped_count', sa.Integer(), nullable=False),
    sa.Column('errors', sa.JSON(), nullable=False),
    sa.Column('imported_by', sa.Integer(), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('products', 'pos', 'inventory', 'waste')", name=op.f('ck_import_logs_kind')),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_import_logs_department_id_departments')),
    sa.ForeignKeyConstraint(['imported_by'], ['users.id'], name=op.f('fk_import_logs_imported_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_import_logs'))
    )
    op.create_table('products',
    sa.Column('product_code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('department_id', sa.Integer(), nullable=False),
    sa.Column('order_unit', sa.Integer(), nullable=False),
    sa.Column('lead_time_days', sa.Integer(), nullable=False),
    sa.Column('can_carry_over', sa.Boolean(), nullable=False),
    sa.Column('cost_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('selling_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('lead_time_days >= 0', name=op.f('ck_products_lead_time_days')),
    sa.CheckConstraint('order_unit >= 1', name=op.f('ck_products_order_unit')),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_products_department_id_departments')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_products')),
    sa.UniqueConstraint('product_code', name=op.f('uq_products_product_code'))
    )
    op.create_table('proposal_jobs',
    sa.Column('department_id', sa.Integer(), nullable=False),
    sa.Column('target_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('processed', sa.Integer(), server_default='0', nullable=False),
    sa.Column('total', sa.Integer(), server_default='0', nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('running', 'succeeded', 'failed')", name=op.f('ck_proposal_jobs_status')),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_proposal_jobs_department_id_departments')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_proposal_jobs'))
    )
    op.create_table('settings',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name=op.f('fk_settings_updated_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_settings')),
    sa.UniqueConstraint('key', name=op.f('uq_settings_key'))
    )
    op.create_table('user_departments',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('department_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_user_departments_department_id_departments')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_departments_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_departments')),
    sa.UniqueConstraint('user_id', 'department_id', name=op.f('uq_user_departments_user_id_department_id'))
    )
    op.create_table('display_stock_entries',
    sa.Column('target_date', sa.Date(), nullable=False),
    sa.Column('entered_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('entered_by', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['entered_by'], ['users.id'], name=op.f('fk_display_stock_entries_entered_by_users')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_display_stock_entries_product_id_products')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_display_stock_entries')),
    sa.UniqueConstraint('target_date', 'entered_at', 'product_id', name=op.f('uq_display_stock_entries_target_date_entered_at_product_id'))
    )
    op.create_table('forecasts',
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('target_date', sa.Date(), nullable=False),
    sa.Column('time_band', sa.Integer(), nullable=True),
    sa.Column('predicted_qty', sa.Float(), nullable=False),
    sa.Column('model_version', sa.String(length=64), nullable=False),
    sa.Column('features', sa.JSON(), nullable=False),
    sa.Column('weather_fetched_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_forecasts_product_id_products')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_forecasts'))
    )
    op.create_table('inventory_snapshots',
    sa.Column('based_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('entered_by', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('csv', 'manual')", name=op.f('ck_inventory_snapshots_source')),
    sa.ForeignKeyConstraint(['entered_by'], ['users.id'], name=op.f('fk_inventory_snapshots_entered_by_users')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_inventory_snapshots_product_id_products')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_inventory_snapshots')),
    sa.UniqueConstraint('based_at', 'product_id', name=op.f('uq_inventory_snapshots_based_at_product_id'))
    )
    op.create_table('pos_sales',
    sa.Column('sales_date', sa.Date(), nullable=False),
    sa.Column('sales_hour', sa.Integer(), nullable=True),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('sales_hour BETWEEN 0 AND 23', name=op.f('ck_pos_sales_sales_hour')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_pos_sales_product_id_products')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pos_sales')),
    sa.UniqueConstraint('sales_date', 'sales_hour', 'product_id', name=op.f('uq_pos_sales_sales_date_sales_hour_product_id'), postgresql_nulls_not_distinct=True)
    )
    op.create_table('promotions',
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('description', sa.String(length=128), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_promotions_created_by_users')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_promotions_product_id_products')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_promotions'))
    )
    op.create_table('waste_records',
    sa.Column('waste_date', sa.Date(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_waste_records_product_id_products')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_waste_records')),
    sa.UniqueConstraint('waste_date', 'product_id', name=op.f('uq_waste_records_waste_date_product_id'))
    )
    op.create_table('proposals',
    sa.Column('department_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('target_date', sa.Date(), nullable=False),
    sa.Column('time_band', sa.Integer(), nullable=True),
    sa.Column('forecast_id', sa.Integer(), nullable=False),
    sa.Column('proposed_qty', sa.Integer(), nullable=False),
    sa.Column('original_qty', sa.Integer(), nullable=False),
    sa.Column('recalculated_qty', sa.Integer(), nullable=True),
    sa.Column('is_adjusted', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('adjust_reason', sa.String(length=16), nullable=True),
    sa.Column('adjust_note', sa.String(length=128), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('deadline', sa.DateTime(timezone=True), nullable=False),
    sa.Column('approved_by', sa.Integer(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('warnings', sa.JSON(), nullable=False),
    sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('basis', sa.JSON(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("adjust_reason IN ('weather', 'promotion', 'inventory', 'other')", name=op.f('ck_proposals_adjust_reason')),
    sa.CheckConstraint("status IN ('pending', 'approved', 'confirmed', 'expired')", name=op.f('ck_proposals_status')),
    sa.ForeignKeyConstraint(['approved_by'], ['users.id'], name=op.f('fk_proposals_approved_by_users')),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_proposals_department_id_departments')),
    sa.ForeignKeyConstraint(['forecast_id'], ['forecasts.id'], name=op.f('fk_proposals_forecast_id_forecasts')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_proposals_product_id_products')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_proposals')),
    sa.UniqueConstraint('department_id', 'product_id', 'target_date', 'time_band', name=op.f('uq_proposals_department_id_product_id_target_date_time_band'), postgresql_nulls_not_distinct=True)
    )
    op.create_table('proposal_histories',
    sa.Column('proposal_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=16), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('qty_before', sa.Integer(), nullable=True),
    sa.Column('qty_after', sa.Integer(), nullable=True),
    sa.Column('reason', sa.String(length=16), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("action IN ('create', 'recalculate', 'adjust', 'approve', 'cancel', 'adopt', 'confirm', 'expire')", name=op.f('ck_proposal_histories_action')),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_proposal_histories_actor_id_users')),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], name=op.f('fk_proposal_histories_proposal_id_proposals'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_proposal_histories'))
    )

    departments = sa.table(
        "departments",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("business_type", sa.String),
    )
    op.bulk_insert(departments, DEPARTMENTS)


def downgrade() -> None:
    op.drop_table("proposal_histories")
    op.drop_table("proposals")
    op.drop_table("waste_records")
    op.drop_table("promotions")
    op.drop_table("pos_sales")
    op.drop_table("inventory_snapshots")
    op.drop_table("forecasts")
    op.drop_table("display_stock_entries")
    op.drop_table("user_departments")
    op.drop_table("settings")
    op.drop_table("proposal_jobs")
    op.drop_table("products")
    op.drop_table("import_logs")
    op.drop_table("weather_forecasts")
    op.drop_table("weather_actuals")
    op.drop_table("users")
    op.drop_table("departments")
    op.drop_table("calendar_days")
