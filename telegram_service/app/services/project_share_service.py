from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import UserRole
from app.db.models import ProjectShare, User
from app.services.audit_service import AuditService


class ProjectShareService:
    def __init__(self) -> None:
        self._audit = AuditService()

    async def set_share(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        percent: Decimal,
        actor_id: int,
    ) -> ProjectShare:
        actor = await session.get(User, actor_id)
        if not actor or actor.role not in {UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN}:
            await self._audit.log_audit_event(
                session,
                actor_id=actor_id,
                action="PERMISSION_DENIED",
                entity_type="project_share",
                entity_id=None,
                payload={"reason": "PROJECT_SHARE_SET"},
            )
            raise ValueError("Нет прав на изменение долей")
        percent = self._validate_percent(percent)
        existing = await session.execute(
            select(ProjectShare).where(ProjectShare.user_id == user_id, ProjectShare.is_active.is_(True))
        )
        current = existing.scalar_one_or_none()
        before_percent = current.percent if current else None
        if current:
            current.is_active = False

        share = ProjectShare(
            user_id=user_id,
            percent=percent,
            is_active=True,
            set_by=actor_id,
            set_at=datetime.utcnow(),
        )
        session.add(share)
        await session.flush()
        await self._audit.log_audit_event(
            session,
            actor_id=actor_id,
            action="PROJECT_SHARE_SET",
            entity_type="project_share",
            entity_id=share.id,
            payload={
                "before": {"percent": float(before_percent)} if before_percent is not None else None,
                "after": {"percent": float(percent)},
                "user_id": user_id,
            },
        )
        return share

    def _validate_percent(self, percent: Decimal) -> Decimal:
        if percent < 0 or percent > 100:
            raise ValueError("Процент должен быть от 0 до 100")
        if percent.as_tuple().exponent < -2:
            raise ValueError("Процент должен иметь максимум 2 знака после запятой")
        return percent
