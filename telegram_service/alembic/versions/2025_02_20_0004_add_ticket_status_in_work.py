"""add IN_WORK status for tickets

Revision ID: 2025_02_20_0004
Revises: 2025_02_10_0003
Create Date: 2025-02-20 00:00:00.000000

"""
from alembic import op


revision = "2025_02_20_0004"
down_revision = "2025_02_10_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE ticket_status ADD VALUE IF NOT EXISTS 'IN_WORK'")


def downgrade() -> None:
    pass
