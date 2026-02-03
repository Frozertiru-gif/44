from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine.url import make_url

from app.core.config import get_settings
from app.db.session import engine


async def log_database_context(logger: logging.Logger) -> None:
    settings = get_settings()
    safe_url = make_url(settings.database_url).render_as_string(hide_password=True)
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT current_database(), current_schema()"))
        current_database, current_schema = result.one()
    logger.info(
        "Database context: database=%s schema=%s database_url=%s",
        current_database,
        current_schema,
        safe_url,
    )
