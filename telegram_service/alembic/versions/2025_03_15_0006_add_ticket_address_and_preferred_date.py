"""add ticket address and preferred date

Revision ID: 2025_03_15_0006
Revises: 2025_02_25_0005
Create Date: 2025-03-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2025_03_15_0006"
down_revision = "2025_02_25_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("client_address", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("preferred_date_dm", sa.String(length=5), nullable=True))


def downgrade() -> None:
    op.drop_column("tickets", "preferred_date_dm")
    op.drop_column("tickets", "client_address")
