"""add ticket public id and close metadata

Revision ID: 2026_02_05_0007
Revises: 2025_03_15_0006
Create Date: 2026-02-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2026_02_05_0007"
down_revision = "2025_03_15_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_counters",
        sa.Column("counter_date", sa.Date(), nullable=False),
        sa.Column("counter", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("counter_date"),
    )

    op.add_column("tickets", sa.Column("public_id", sa.String(length=8), nullable=True))
    op.add_column("tickets", sa.Column("closed_by_user_id", sa.BigInteger(), nullable=True))
    op.add_column("tickets", sa.Column("closed_comment", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("closed_photo_file_id", sa.Text(), nullable=True))
    op.create_foreign_key("fk_tickets_closed_by_user_id_users", "tickets", "users", ["closed_by_user_id"], ["id"])

    op.execute(
        """
        WITH ordered AS (
            SELECT
                id,
                created_at::date AS d,
                ROW_NUMBER() OVER (
                    PARTITION BY created_at::date
                    ORDER BY created_at ASC, id ASC
                ) AS seq
            FROM tickets
        )
        UPDATE tickets t
        SET public_id = to_char(ordered.d, 'DDMMYY') || lpad(ordered.seq::text, 2, '0')
        FROM ordered
        WHERE t.id = ordered.id
        """
    )

    op.execute(
        """
        INSERT INTO daily_counters(counter_date, counter)
        SELECT created_at::date AS counter_date, COUNT(*)::bigint AS counter
        FROM tickets
        GROUP BY created_at::date
        ON CONFLICT (counter_date) DO UPDATE SET counter = EXCLUDED.counter
        """
    )

    op.alter_column("tickets", "public_id", nullable=False)
    op.create_index("ix_tickets_public_id", "tickets", ["public_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tickets_public_id", table_name="tickets")
    op.drop_constraint("fk_tickets_closed_by_user_id_users", "tickets", type_="foreignkey")
    op.drop_column("tickets", "closed_photo_file_id")
    op.drop_column("tickets", "closed_comment")
    op.drop_column("tickets", "closed_by_user_id")
    op.drop_column("tickets", "public_id")
    op.drop_table("daily_counters")
