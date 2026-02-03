from __future__ import annotations

import asyncio
import logging
import time
from typing import Iterable
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.engine import create_engine

logger = logging.getLogger(__name__)


def _mask_database_url(database_url: str) -> str:
    try:
        return make_url(database_url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid database url>"


async def _wait_for_db(timeout_seconds: int = 60, interval_seconds: int = 2) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, schema=settings.db_schema, poolclass=NullPool)
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            await engine.dispose()
            logger.info("Database is available")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("Database is not ready yet: %s", exc)
            await asyncio.sleep(interval_seconds)

    await engine.dispose()
    raise RuntimeError("Database did not become available in time") from last_error


async def _fetch_diagnostics(expected_heads: Iterable[str]) -> dict[str, object]:
    settings = get_settings()
    engine = create_engine(settings.database_url, schema=settings.db_schema, poolclass=NullPool)
    schema = settings.db_schema or "public"

    async with engine.connect() as connection:
        db_info = await connection.execute(
            text("SELECT current_database(), current_schema(), current_setting('search_path')")
        )
        current_database, current_schema, search_path = db_info.one()

        tables = {}
        for table in ("users", "tickets", "alembic_version"):
            regclass = await connection.execute(
                text("SELECT to_regclass(:table_name)"),
                {"table_name": f"{schema}.{table}"},
            )
            tables[table] = regclass.scalar()

        current_revisions: list[str] = []
        if tables["alembic_version"]:
            revision_rows = await connection.execute(
                text(f'SELECT version_num FROM "{schema}"."alembic_version"')
            )
            current_revisions = [row[0] for row in revision_rows.fetchall()]

    await engine.dispose()

    return {
        "database_url": _mask_database_url(settings.database_url),
        "expected_schema": schema,
        "current_database": current_database,
        "current_schema": current_schema,
        "search_path": search_path,
        "tables": tables,
        "expected_heads": list(expected_heads),
        "current_revisions": current_revisions,
        "expected_database": make_url(settings.database_url).database,
    }


def _format_diagnostics(diagnostics: dict[str, object]) -> str:
    tables = diagnostics["tables"]
    expected_heads = diagnostics["expected_heads"]
    current_revisions = diagnostics["current_revisions"]
    expected_database = diagnostics["expected_database"]

    return (
        "Database bootstrap diagnostics:\n"
        f"  DATABASE_URL: {diagnostics['database_url']}\n"
        f"  expected_database: {expected_database}\n"
        f"  expected_schema: {diagnostics['expected_schema']}\n"
        f"  current_database: {diagnostics['current_database']}\n"
        f"  current_schema: {diagnostics['current_schema']}\n"
        f"  search_path: {diagnostics['search_path']}\n"
        "  tables:\n"
        f"    users: {'present' if tables['users'] else 'missing'}\n"
        f"    tickets: {'present' if tables['tickets'] else 'missing'}\n"
        f"    alembic_version: {'present' if tables['alembic_version'] else 'missing'}\n"
        "  alembic:\n"
        f"    head: {', '.join(expected_heads) if expected_heads else '<none>'}\n"
        f"    current: {', '.join(current_revisions) if current_revisions else '<none>'}\n"
    )


def _validate_diagnostics(diagnostics: dict[str, object]) -> list[str]:
    errors: list[str] = []
    expected_schema = diagnostics["expected_schema"]
    expected_database = diagnostics["expected_database"]

    if diagnostics["current_database"] != expected_database:
        errors.append("Connected database does not match DATABASE_URL.")

    if diagnostics["current_schema"] != expected_schema:
        errors.append("Current schema does not match DB_SCHEMA.")

    search_path = diagnostics["search_path"]
    search_path_items = [item.strip() for item in str(search_path).split(",") if item.strip()]
    if not search_path_items or search_path_items[0] != expected_schema:
        errors.append("search_path does not start with DB_SCHEMA.")

    tables = diagnostics["tables"]
    for table_name in ("users", "tickets", "alembic_version"):
        if not tables[table_name]:
            errors.append(f"Required table {table_name} is missing.")

    expected_heads = set(diagnostics["expected_heads"])
    current_revisions = set(diagnostics["current_revisions"])
    if expected_heads and current_revisions != expected_heads:
        errors.append("Alembic version does not match head revision.")

    return errors


async def bootstrap_database() -> None:
    configure_logging()
    await _wait_for_db()
    diagnostics = await _fetch_diagnostics([])
    errors = _validate_diagnostics(diagnostics)

    if errors:
        logger.error("Database bootstrap failed. Reasons: %s", "; ".join(errors))
        logger.error(_format_diagnostics(diagnostics))
        raise SystemExit(1)

    logger.info("Database bootstrap verification succeeded.")
    logger.info(_format_diagnostics(diagnostics))


def main() -> None:
    asyncio.run(bootstrap_database())


if __name__ == "__main__":
    main()
