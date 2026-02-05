"""add ticket close photos table

Revision ID: 2026_02_06_0008
Revises: 2026_02_05_0007
Create Date: 2026-02-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2026_02_06_0008"
down_revision = "2026_02_05_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_close_photos",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("file_id", sa.Text(), nullable=False),
        sa.Column("file_unique_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_close_photos_ticket_id", "ticket_close_photos", ["ticket_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ticket_close_photos_ticket_id", table_name="ticket_close_photos")
    op.drop_table("ticket_close_photos")
