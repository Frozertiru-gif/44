from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_engine(database_url: str, schema: str = "public", **kwargs: Any) -> AsyncEngine:
    connect_args = dict(kwargs.pop("connect_args", {}) or {})
    server_settings = dict(connect_args.get("server_settings", {}) or {})
    schema_name = schema or "public"
    safe_schema = schema_name.replace('"', '""')
    server_settings["search_path"] = f'"{safe_schema}", public'
    connect_args["server_settings"] = server_settings

    return create_async_engine(database_url, connect_args=connect_args, **kwargs)
