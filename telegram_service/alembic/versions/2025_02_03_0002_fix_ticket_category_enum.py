"""fix ticket_category enum values

Revision ID: 2025_02_03_0002
Revises: 2025_02_01_0001
Create Date: 2025-02-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2025_02_03_0002"
down_revision = "2025_02_01_0001"
branch_labels = None
depends_on = None


NEW_VALUES = ("PC", "TV", "PHONE", "PRINTER", "OTHER")
LEGACY_VALUE_MAP = {
    "ПК": "PC",
    "ТВ": "TV",
    "Телефон": "PHONE",
    "Принтер": "PRINTER",
    "Другое": "OTHER",
}


def _enum_exists(bind: sa.engine.Connection, enum_name: str) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
            {"name": enum_name},
        ).first()
    )


def _enum_label_exists(bind: sa.engine.Connection, enum_name: str, label: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = :name AND e.enumlabel = :label
                """
            ),
            {"name": enum_name, "label": label},
        ).first()
    )


def upgrade() -> None:
    bind = op.get_bind()

    if not _enum_exists(bind, "ticket_category"):
        values_sql = ", ".join(f"'{value}'" for value in NEW_VALUES)
        op.execute(sa.text(f"CREATE TYPE ticket_category AS ENUM ({values_sql})"))
        return

    for value in NEW_VALUES:
        op.execute(sa.text(f"ALTER TYPE ticket_category ADD VALUE IF NOT EXISTS '{value}'"))

    for legacy_value, new_value in LEGACY_VALUE_MAP.items():
        if not _enum_label_exists(bind, "ticket_category", legacy_value):
            continue
        op.execute(
            sa.text(
                """
                UPDATE tickets
                SET category = :new_value
                WHERE category = :legacy_value
                """
            ),
            {"new_value": new_value, "legacy_value": legacy_value},
        )


def downgrade() -> None:
    pass
