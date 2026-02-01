"""initial tables

Revision ID: 2024_01_01_0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2024_01_01_0001"
down_revision = None
branch_labels = None
depends_on = None


user_role = postgresql.ENUM(
    "SYS_ADMIN",
    "SUPER_ADMIN",
    "ADMIN",
    "JUNIOR_ADMIN",
    "MASTER",
    "JUNIOR_MASTER",
    name="user_role",
    create_type=False,
)

ticket_status = postgresql.ENUM(
    "READY_FOR_WORK",
    "CANCELLED",
    name="ticket_status",
    create_type=False,
)

ticket_category = postgresql.ENUM(
    "ПК",
    "ТВ",
    "Телефон",
    "Принтер",
    "Другое",
    name="ticket_category",
    create_type=False,
)

ad_source = postgresql.ENUM(
    "Авито",
    "Листовка",
    "Визитка",
    "Другое",
    "Неизвестно",
    name="ad_source",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    ticket_status.create(bind, checkfirst=True)
    ticket_category.create(bind, checkfirst=True)
    ad_source.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("role", user_role, nullable=False, server_default="JUNIOR_ADMIN"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("client_age_estimate", sa.BigInteger(), nullable=True),
        sa.Column("client_phone", sa.String(length=64), nullable=False),
        sa.Column("problem_text", sa.Text(), nullable=False),
        sa.Column("special_note", sa.Text(), nullable=True),
        sa.Column("ad_source", ad_source, nullable=False),
        sa.Column("is_repeat", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("repeat_ticket_ids", sa.JSON(), nullable=True),
        sa.Column("created_by_admin_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tickets_client_phone", "tickets", ["client_phone"], unique=False)

    op.create_table(
        "ticket_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.BigInteger(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("audit_events")
    op.drop_table("ticket_events")
    op.drop_index("ix_tickets_client_phone", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("users")

    ad_source.drop(bind, checkfirst=True)
    ticket_category.drop(bind, checkfirst=True)
    ticket_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
