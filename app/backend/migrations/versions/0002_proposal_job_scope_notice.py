"""proposal_jobs に scope(既定表示/対象日の指定)と notice(予測の注記)を加える

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 既存のジョブは既定表示か対象日の指定かを区別できないため、既定表示とみなす(実行中のものは10分で失敗扱いになる)
    op.add_column("proposal_jobs", sa.Column("scope", sa.String(length=16), server_default="default", nullable=False))
    op.add_column("proposal_jobs", sa.Column("notice", sa.Text(), nullable=True))
    op.create_check_constraint(op.f("ck_proposal_jobs_scope"), "proposal_jobs", "scope IN ('default', 'date')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_proposal_jobs_scope"), "proposal_jobs", type_="check")
    op.drop_column("proposal_jobs", "notice")
    op.drop_column("proposal_jobs", "scope")
