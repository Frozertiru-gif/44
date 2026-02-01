"""leads table

Revision ID: 2024_05_20_0006
Revises: 2024_04_10_0005
Create Date: 2024-05-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2024_05_20_0006"
down_revision = "2024_04_10_0005"
branch_labels = None
depends_on = None


lead_ad_source = postgresql.ENUM(
    "AVITO",
    "FLYER",
    "BUSINESS_CARD",
    "OTHER",
    "UNKNOWN",
    name="lead_ad_source",
    create_type=False,
)

lead_status = postgresql.ENUM(
    "NEW_RAW",
    "NEED_INFO",
    "CONVERTED",
    "SPAM",
    name="lead_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    lead_ad_source.create(bind, checkfirst=True)
    lead_status.create(bind, checkfirst=True)

    op.alter_column(
        "audit_events",
        "entity_id",
        existing_type=sa.BigInteger(),
        type_=sa.String(length=64),
        existing_nullable=True,
        postgresql_using="entity_id::text",
    )

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("client_phone", sa.String(length=64), nullable=True),
        sa.Column("preferred_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_age_estimate", sa.BigInteger(), nullable=True),
        sa.Column("problem_text", sa.Text(), nullable=False),
        sa.Column(
            "special_note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "ad_source",
            lead_ad_source,
            nullable=True,
        ),
        sa.Column(
            "status",
            lead_status,
            nullable=False,
        ),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("converted_ticket_id", sa.BigInteger(), sa.ForeignKey("tickets.id"), nullable=True),
    )
    op.create_index(
        "ix_leads_status_created_at",
        "leads",
        [sa.text("status"), sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_leads_client_phone_created_at",
        "leads",
        [sa.text("client_phone"), sa.text("created_at DESC")],
        postgresql_where=sa.text("client_phone IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_leads_client_phone_created_at", table_name="leads")
    op.drop_index("ix_leads_status_created_at", table_name="leads")
    op.drop_table("leads")

    op.alter_column(
        "audit_events",
        "entity_id",
        existing_type=sa.String(length=64),
        type_=sa.BigInteger(),
        existing_nullable=True,
        postgresql_using="entity_id::bigint",
    )

    bind = op.get_bind()
    lead_status.drop(bind, checkfirst=True)
    lead_ad_source.drop(bind, checkfirst=True)
