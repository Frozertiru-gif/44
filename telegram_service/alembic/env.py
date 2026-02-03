from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.db.base import Base
from app.db.engine import create_engine
from app.db import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        transaction_per_migration=True,
        version_table_schema=settings.db_schema,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_engine(
        settings.database_url,
        schema=settings.db_schema,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        async with connection.begin():
            await connection.run_sync(ensure_schema)

        await connection.run_sync(do_run_migrations)

        await connection.run_sync(verify_post_commit)

    await connectable.dispose()


def ensure_schema(sync_conn) -> None:
    schema_name = settings.db_schema or "public"
    if schema_name != "public":
        safe_schema = schema_name.replace('"', '""')
        sync_conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{safe_schema}"'))


def do_run_migrations(sync_conn) -> None:
    context.configure(
        connection=sync_conn,
        target_metadata=target_metadata,
        compare_type=True,
        transaction_per_migration=True,
        version_table_schema=settings.db_schema,
    )
    with context.begin_transaction():
        context.run_migrations()


def verify_post_commit(sync_conn) -> None:
    schema_name = settings.db_schema or "public"
    missing_tables = []
    for table in ("alembic_version", "users", "tickets"):
        qualified_table = f"{schema_name}.{table}"
        result = sync_conn.execute(
            text("select to_regclass(:table_name)"),
            {"table_name": qualified_table},
        ).scalar()
        if result is None:
            missing_tables.append(qualified_table)
    if missing_tables:
        raise RuntimeError(
            "Post-commit verification failed; missing tables: "
            + ", ".join(missing_tables)
            + "."
        )


def run_migrations() -> None:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())


run_migrations()
