"""baseline schema

Revision ID: 2025_02_01_0001
Revises:
Create Date: 2025-02-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2025_02_01_0001"
down_revision = None
branch_labels = None
depends_on = None


user_role_enum = postgresql.ENUM(
    "SYS_ADMIN",
    "SUPER_ADMIN",
    "ADMIN",
    "JUNIOR_ADMIN",
    "MASTER",
    "JUNIOR_MASTER",
    name="user_role",
    create_type=False,
)

ticket_status_enum = postgresql.ENUM(
    "READY_FOR_WORK",
    "TAKEN",
    "IN_PROGRESS",
    "WAITING",
    "CLOSED",
    "CANCELLED",
    name="ticket_status",
    create_type=False,
)

ticket_category_enum = postgresql.ENUM(
    "ПК",
    "ТВ",
    "Телефон",
    "Принтер",
    "Другое",
    name="ticket_category",
    create_type=False,
)

ad_source_enum = postgresql.ENUM(
    "Авито",
    "Листовка",
    "Визитка",
    "Другое",
    "Неизвестно",
    name="ad_source",
    create_type=False,
)

lead_ad_source_enum = postgresql.ENUM(
    "AVITO",
    "FLYER",
    "BUSINESS_CARD",
    "OTHER",
    "UNKNOWN",
    name="lead_ad_source",
    create_type=False,
)

lead_status_enum = postgresql.ENUM(
    "NEW_RAW",
    "NEED_INFO",
    "CONVERTED",
    "SPAM",
    name="lead_status",
    create_type=False,
)

transfer_status_enum = postgresql.ENUM(
    "NOT_SENT",
    "SENT",
    "CONFIRMED",
    "REJECTED",
    name="transfer_status",
    create_type=False,
)

project_transaction_type_enum = postgresql.ENUM(
    "INCOME",
    "EXPENSE",
    name="project_transaction_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        user_role_enum,
        ticket_status_enum,
        ticket_category_enum,
        ad_source_enum,
        lead_ad_source_enum,
        lead_status_enum,
        transfer_status_enum,
        project_transaction_type_enum,
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("master_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("admin_percent", sa.Numeric(5, 2), nullable=True),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("status", ticket_status_enum, nullable=False),
        sa.Column("category", ticket_category_enum, nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("client_age_estimate", sa.BigInteger(), nullable=True),
        sa.Column("client_phone", sa.String(length=64), nullable=False),
        sa.Column("problem_text", sa.Text(), nullable=False),
        sa.Column("special_note", sa.Text(), nullable=True),
        sa.Column("ad_source", ad_source_enum, nullable=False),
        sa.Column("is_repeat", sa.Boolean(), nullable=False),
        sa.Column("repeat_ticket_ids", sa.JSON(), nullable=True),
        sa.Column("created_by_admin_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_executor_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("taken_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("revenue", sa.Numeric(12, 2), nullable=True),
        sa.Column("expense", sa.Numeric(12, 2), nullable=True),
        sa.Column("net_profit", sa.Numeric(12, 2), nullable=True),
        sa.Column("transfer_status", transfer_status_enum, nullable=True),
        sa.Column("transfer_sent_at", sa.DateTime(), nullable=True),
        sa.Column("transfer_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("transfer_confirmed_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("junior_master_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("junior_master_percent_at_close", sa.Numeric(5, 2), nullable=True),
        sa.Column("junior_master_earned_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("executor_percent_at_close", sa.Numeric(5, 2), nullable=True),
        sa.Column("admin_percent_at_close", sa.Numeric(5, 2), nullable=True),
        sa.Column("executor_earned_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("admin_earned_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("project_take_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tickets_client_phone", "tickets", ["client_phone"], unique=False)

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("client_phone", sa.String(length=64), nullable=True),
        sa.Column("preferred_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_age_estimate", sa.BigInteger(), nullable=True),
        sa.Column("problem_text", sa.Text(), nullable=False),
        sa.Column("special_note", sa.Text(), nullable=True),
        sa.Column("ad_source", lead_ad_source_enum, nullable=True),
        sa.Column("status", lead_status_enum, nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("converted_ticket_id", sa.BigInteger(), sa.ForeignKey("tickets.id"), nullable=True),
    )
    op.create_index(
        "ix_leads_status_created_at",
        "leads",
        ["status", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_leads_client_phone_created_at",
        "leads",
        ["client_phone", sa.text("created_at DESC")],
        unique=False,
        postgresql_where=sa.text("client_phone IS NOT NULL"),
    )

    op.create_table(
        "master_junior_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("master_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("junior_master_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

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
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "project_transactions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("type", project_transaction_type_enum, nullable=False),
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
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("set_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("set_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "project_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("requests_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("rounding_mode", sa.String(length=32), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("project_settings")
    op.drop_table("project_shares")
    op.drop_table("project_transactions")
    op.drop_table("audit_events")
    op.drop_table("ticket_events")
    op.drop_table("master_junior_links")
    op.drop_index("ix_leads_client_phone_created_at", table_name="leads")
    op.drop_index("ix_leads_status_created_at", table_name="leads")
    op.drop_table("leads")
    op.drop_index("ix_tickets_client_phone", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("users")

    bind = op.get_bind()
    for enum_type in (
        project_transaction_type_enum,
        transfer_status_enum,
        lead_status_enum,
        lead_ad_source_enum,
        ad_source_enum,
        ticket_category_enum,
        ticket_status_enum,
        user_role_enum,
    ):
        enum_type.drop(bind, checkfirst=True)
