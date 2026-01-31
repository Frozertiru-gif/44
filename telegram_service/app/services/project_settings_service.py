from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProjectSettings


class ProjectSettingsService:
    def __init__(self) -> None:
        self._defaults = {
            "currency": "RUB",
            "rounding_mode": "HALF_UP",
            "thresholds": {
                "large_expense": 10000,
                "transfer_pending_days": 3,
            },
        }

    async def get_settings(self, session: AsyncSession) -> ProjectSettings:
        result = await session.execute(select(ProjectSettings).order_by(ProjectSettings.id.asc()).limit(1))
        settings = result.scalar_one_or_none()
        if settings:
            return settings
        settings = ProjectSettings(
            requests_chat_id=None,
            currency=self._defaults["currency"],
            rounding_mode=self._defaults["rounding_mode"],
            thresholds=self._defaults["thresholds"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(settings)
        await session.flush()
        return settings

    async def update_settings(self, session: AsyncSession, settings: ProjectSettings, *, updates: dict[str, Any]) -> ProjectSettings:
        for key, value in updates.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        settings.updated_at = datetime.utcnow()
        await session.flush()
        return settings

    async def get_threshold(self, session: AsyncSession, key: str, default: int) -> int:
        settings = await self.get_settings(session)
        thresholds = settings.thresholds or {}
        value = thresholds.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    async def get_requests_chat_id(self, session: AsyncSession, fallback: int) -> int:
        settings = await self.get_settings(session)
        return settings.requests_chat_id or fallback
