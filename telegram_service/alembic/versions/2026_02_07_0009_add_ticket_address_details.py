"""add ticket address details

Revision ID: 2026_02_07_0009
Revises: 2026_02_06_0008
Create Date: 2026-02-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2026_02_07_0009"
down_revision = "2026_02_06_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("address_details", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tickets", "address_details")
