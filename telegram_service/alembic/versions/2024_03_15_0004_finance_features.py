"""finance fields and project tables

Revision ID: 2024_03_15_0004
Revises: 2024_02_01_0003
Create Date: 2024-03-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2024_03_15_0004"
down_revision = "2024_02_01_0003"
branch_labels = None
depends_on = None


project_transaction_type = sa.Enum("INCOME", "EXPENSE", name="project_transaction_type")


def upgrade() -> None:
    project_transaction_type.create(op.get_bind(), checkfirst=True)

    op.add_column("users", sa.Column("master_percent", sa.Numeric(5, 2), nullable=True))
    op.add_column("users", sa.Column("admin_percent", sa.Numeric(5, 2), nullable=True))

    op.add_column("tickets", sa.Column("executor_percent_at_close", sa.Numeric(5, 2), nullable=True))
    op.add_column("tickets", sa.Column("admin_percent_at_close", sa.Numeric(5, 2), nullable=True))
    op.add_column("tickets", sa.Column("executor_earned_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("tickets", sa.Column("admin_earned_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("tickets", sa.Column("project_take_amount", sa.Numeric(12, 2), nullable=True))

    op.create_table(
        "project_transactions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("type", project_transaction_type, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "project_shares",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("set_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("set_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ux_project_shares_user_active",
        "project_shares",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("ux_project_shares_user_active", table_name="project_shares")
    op.drop_table("project_shares")
    op.drop_table("project_transactions")

    op.drop_column("tickets", "project_take_amount")
    op.drop_column("tickets", "admin_earned_amount")
    op.drop_column("tickets", "executor_earned_amount")
    op.drop_column("tickets", "admin_percent_at_close")
    op.drop_column("tickets", "executor_percent_at_close")

    op.drop_column("users", "admin_percent")
    op.drop_column("users", "master_percent")

    project_transaction_type.drop(op.get_bind(), checkfirst=True)
