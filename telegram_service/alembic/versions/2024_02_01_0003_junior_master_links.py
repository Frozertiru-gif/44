"""junior master links and ticket fields

Revision ID: 2024_02_01_0003
Revises: 2024_01_15_0002
Create Date: 2024-02-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2024_02_01_0003"
down_revision = "2024_01_15_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "master_junior_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("master_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("junior_master_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ux_master_junior_links_active_junior",
        "master_junior_links",
        ["junior_master_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    op.add_column("tickets", sa.Column("junior_master_id", sa.BigInteger(), nullable=True))
    op.add_column("tickets", sa.Column("junior_master_percent_at_close", sa.Numeric(5, 2), nullable=True))
    op.add_column("tickets", sa.Column("junior_master_earned_amount", sa.Numeric(12, 2), nullable=True))
    op.create_foreign_key("fk_tickets_junior_master", "tickets", "users", ["junior_master_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_tickets_junior_master", "tickets", type_="foreignkey")
    op.drop_column("tickets", "junior_master_earned_amount")
    op.drop_column("tickets", "junior_master_percent_at_close")
    op.drop_column("tickets", "junior_master_id")

    op.drop_index("ux_master_junior_links_active_junior", table_name="master_junior_links")
    op.drop_table("master_junior_links")
