"""add stable ad_source codes and ensure ticket_category values

Revision ID: 2025_02_10_0003
Revises: 2025_02_03_0002
Create Date: 2025-02-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2025_02_10_0003"
down_revision = "2025_02_03_0002"
branch_labels = None
depends_on = None


TICKET_CATEGORY_VALUES = ("PC", "TV", "PHONE", "PRINTER", "OTHER")
AD_SOURCE_VALUES = ("AVITO", "LEAFLET", "BUSINESS_CARD", "OTHER", "UNKNOWN")
LEGACY_AD_SOURCE_MAP = {
    "Авито": "AVITO",
    "Листовка": "LEAFLET",
    "Визитка": "BUSINESS_CARD",
    "Другое": "OTHER",
    "Неизвестно": "UNKNOWN",
}


def upgrade() -> None:
    ctx = op.get_context()
    with ctx.autocommit_block():
        for value in TICKET_CATEGORY_VALUES:
            op.execute(sa.text(f"ALTER TYPE ticket_category ADD VALUE IF NOT EXISTS '{value}'"))
        for value in AD_SOURCE_VALUES:
            op.execute(sa.text(f"ALTER TYPE ad_source ADD VALUE IF NOT EXISTS '{value}'"))

    bind = op.get_bind()
    for legacy_value, new_value in LEGACY_AD_SOURCE_MAP.items():
        bind.execute(
            sa.text(
                """
                UPDATE tickets
                SET ad_source = :new_value
                WHERE ad_source = :legacy_value
                """
            ),
            {"new_value": new_value, "legacy_value": legacy_value},
        )


def downgrade() -> None:
    pass
