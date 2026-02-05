"""add ticket money operations table

Revision ID: 2026_02_08_0010
Revises: 2026_02_07_0009
Create Date: 2026-02-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2026_02_08_0010"
down_revision = "2026_02_07_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_money_operations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "op_type",
            sa.Enum("INCOME", "EXPENSE", name="project_transaction_type", create_type=False),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("category_snapshot", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_money_operations_created_at", "ticket_money_operations", ["created_at"], unique=False)
    op.create_index("ix_ticket_money_operations_ticket_id", "ticket_money_operations", ["ticket_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ticket_money_operations_ticket_id", table_name="ticket_money_operations")
    op.drop_index("ix_ticket_money_operations_created_at", table_name="ticket_money_operations")
    op.drop_table("ticket_money_operations")
