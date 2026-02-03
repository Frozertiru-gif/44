"""add USER role and username field

Revision ID: 2025_02_25_0005
Revises: 2025_02_20_0004
Create Date: 2025-02-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2025_02_25_0005"
down_revision = "2025_02_20_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'USER'")
    op.add_column("users", sa.Column("username", sa.String(length=255), nullable=True))


def downgrade() -> None:
    pass
