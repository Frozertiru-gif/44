"""project settings table

Revision ID: 2024_04_10_0005
Revises: 2024_03_15_0004
Create Date: 2024-04-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2024_04_10_0005"
down_revision = "2024_03_15_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("requests_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="RUB"),
        sa.Column("rounding_mode", sa.String(length=32), nullable=False, server_default="HALF_UP"),
        sa.Column("thresholds", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("project_settings")
