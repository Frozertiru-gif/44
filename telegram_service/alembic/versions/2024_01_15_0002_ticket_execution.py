"""ticket execution fields

Revision ID: 2024_01_15_0002
Revises: 2024_01_01_0001
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2024_01_15_0002"
down_revision = "2024_01_01_0001"
branch_labels = None
depends_on = None


transfer_status = postgresql.ENUM(
    "NOT_SENT",
    "SENT",
    "CONFIRMED",
    "REJECTED",
    name="transfer_status",
    create_type=False,
)


TICKET_STATUS_VALUES = ["TAKEN", "IN_PROGRESS", "WAITING", "CLOSED"]


def upgrade() -> None:
    for value in TICKET_STATUS_VALUES:
        op.execute(f"ALTER TYPE ticket_status ADD VALUE IF NOT EXISTS '{value}'")

    bind = op.get_bind()
    transfer_status.create(bind, checkfirst=True)

    op.add_column("tickets", sa.Column("assigned_executor_id", sa.BigInteger(), nullable=True))
    op.add_column("tickets", sa.Column("taken_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("closed_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("revenue", sa.Numeric(12, 2), nullable=True))
    op.add_column("tickets", sa.Column("expense", sa.Numeric(12, 2), nullable=True))
    op.add_column("tickets", sa.Column("net_profit", sa.Numeric(12, 2), nullable=True))
    op.add_column("tickets", sa.Column("transfer_status", transfer_status, nullable=True))
    op.add_column("tickets", sa.Column("transfer_sent_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("transfer_confirmed_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("transfer_confirmed_by", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_tickets_assigned_executor", "tickets", "users", ["assigned_executor_id"], ["id"])
    op.create_foreign_key("fk_tickets_transfer_confirmed_by", "tickets", "users", ["transfer_confirmed_by"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_tickets_transfer_confirmed_by", "tickets", type_="foreignkey")
    op.drop_constraint("fk_tickets_assigned_executor", "tickets", type_="foreignkey")
    op.drop_column("tickets", "transfer_confirmed_by")
    op.drop_column("tickets", "transfer_confirmed_at")
    op.drop_column("tickets", "transfer_sent_at")
    op.drop_column("tickets", "transfer_status")
    op.drop_column("tickets", "net_profit")
    op.drop_column("tickets", "expense")
    op.drop_column("tickets", "revenue")
    op.drop_column("tickets", "closed_at")
    op.drop_column("tickets", "taken_at")
    op.drop_column("tickets", "assigned_executor_id")

    bind = op.get_bind()
    transfer_status.drop(bind, checkfirst=True)
