from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import UserRole
from app.db.models import MasterJuniorLink, User
from app.services.audit_service import AuditService


class JuniorLinkService:
    def __init__(self) -> None:
        self._audit = AuditService()

    async def link_junior_to_master(
        self,
        session: AsyncSession,
        *,
        master_id: int,
        junior_id: int,
        percent: Decimal,
        actor_id: int,
    ) -> MasterJuniorLink:
        await self._validate_actor_role(session, actor_id, allowed_roles={UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN})
        await self._validate_master_role(session, master_id)
        await self._validate_junior_role(session, junior_id)
        percent = self._validate_percent(percent)
        await self._ensure_no_active_link(session, junior_id)

        link = MasterJuniorLink(
            master_id=master_id,
            junior_master_id=junior_id,
            percent=percent,
            is_active=True,
            created_by=actor_id,
        )
        session.add(link)
        await session.flush()
        await self._audit.log_audit_event(
            session,
            actor_id=actor_id,
            action="JUNIOR_LINK_CREATED",
            entity_type="master_junior_link",
            entity_id=link.id,
            payload={"master_id": master_id, "junior_master_id": junior_id, "percent": float(percent)},
        )
        return link

    async def relink_junior(
        self,
        session: AsyncSession,
        *,
        junior_id: int,
        new_master_id: int,
        percent: Decimal,
        actor_id: int,
    ) -> MasterJuniorLink:
        await self._validate_actor_role(session, actor_id, allowed_roles={UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN})
        await self._validate_master_role(session, new_master_id)
        await self._validate_junior_role(session, junior_id)
        percent = self._validate_percent(percent)

        current_link = await self.get_active_link_for_junior(session, junior_id)
        if current_link:
            current_link.is_active = False
            current_link.updated_at = datetime.utcnow()
            await session.flush()
            await self._audit.log_audit_event(
                session,
                actor_id=actor_id,
                action="JUNIOR_LINK_DISABLED",
                entity_type="master_junior_link",
                entity_id=current_link.id,
                payload={"master_id": current_link.master_id, "junior_master_id": junior_id},
            )

        link = MasterJuniorLink(
            master_id=new_master_id,
            junior_master_id=junior_id,
            percent=percent,
            is_active=True,
            created_by=actor_id,
        )
        session.add(link)
        await session.flush()
        await self._audit.log_audit_event(
            session,
            actor_id=actor_id,
            action="JUNIOR_LINK_CHANGED",
            entity_type="master_junior_link",
            entity_id=link.id,
            payload={"master_id": new_master_id, "junior_master_id": junior_id, "percent": float(percent)},
        )
        return link

    async def set_link_percent(
        self,
        session: AsyncSession,
        *,
        link_id: int,
        percent: Decimal,
        actor_id: int,
    ) -> MasterJuniorLink:
        percent = self._validate_percent(percent)
        link = await session.get(MasterJuniorLink, link_id)
        if not link or not link.is_active:
            raise ValueError("Привязка не найдена")

        actor = await session.get(User, actor_id)
        if not actor:
            raise ValueError("Пользователь не найден")

        active_count = await self._count_active_links(session, link.master_id)
        if active_count <= 1:
            if actor.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN}:
                raise ValueError("Нет прав на изменение процента")
        else:
            if actor.role not in {UserRole.MASTER, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN}:
                raise ValueError("Нет прав на изменение процента")
        if actor.role == UserRole.MASTER and link.master_id != actor.id:
            raise ValueError("Нет прав на изменение процента")

        link.percent = percent
        link.updated_at = datetime.utcnow()
        await session.flush()
        await self._audit.log_audit_event(
            session,
            actor_id=actor_id,
            action="JUNIOR_PERCENT_CHANGED",
            entity_type="master_junior_link",
            entity_id=link.id,
            payload={"master_id": link.master_id, "junior_master_id": link.junior_master_id, "percent": float(percent)},
        )
        return link

    async def disable_link(self, session: AsyncSession, *, link_id: int, actor_id: int) -> MasterJuniorLink:
        await self._validate_actor_role(session, actor_id, allowed_roles={UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN})
        link = await session.get(MasterJuniorLink, link_id)
        if not link or not link.is_active:
            raise ValueError("Привязка не найдена")
        link.is_active = False
        link.updated_at = datetime.utcnow()
        await session.flush()
        await self._audit.log_audit_event(
            session,
            actor_id=actor_id,
            action="JUNIOR_LINK_DISABLED",
            entity_type="master_junior_link",
            entity_id=link.id,
            payload={"master_id": link.master_id, "junior_master_id": link.junior_master_id},
        )
        return link

    async def get_active_juniors_for_master(self, session: AsyncSession, master_id: int) -> list[MasterJuniorLink]:
        result = await session.execute(
            select(MasterJuniorLink)
            .options(selectinload(MasterJuniorLink.junior_master))
            .where(MasterJuniorLink.master_id == master_id, MasterJuniorLink.is_active.is_(True))
            .order_by(MasterJuniorLink.id.desc())
        )
        return list(result.scalars().all())

    async def get_active_master_for_junior(self, session: AsyncSession, junior_id: int) -> MasterJuniorLink | None:
        result = await session.execute(
            select(MasterJuniorLink)
            .options(selectinload(MasterJuniorLink.master))
            .where(MasterJuniorLink.junior_master_id == junior_id, MasterJuniorLink.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_active_link_for_junior(self, session: AsyncSession, junior_id: int) -> MasterJuniorLink | None:
        result = await session.execute(
            select(MasterJuniorLink).where(
                MasterJuniorLink.junior_master_id == junior_id, MasterJuniorLink.is_active.is_(True)
            )
        )
        return result.scalar_one_or_none()

    async def get_active_link(self, session: AsyncSession, master_id: int, junior_id: int) -> MasterJuniorLink | None:
        result = await session.execute(
            select(MasterJuniorLink)
            .options(selectinload(MasterJuniorLink.junior_master))
            .where(
                MasterJuniorLink.master_id == master_id,
                MasterJuniorLink.junior_master_id == junior_id,
                MasterJuniorLink.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    def _validate_percent(self, percent: Decimal) -> Decimal:
        if percent < 0 or percent > 100:
            raise ValueError("Процент должен быть от 0 до 100")
        if percent.as_tuple().exponent < -2:
            raise ValueError("Процент должен иметь максимум 2 знака после запятой")
        return percent

    async def _validate_master_role(self, session: AsyncSession, master_id: int) -> None:
        master = await session.get(User, master_id)
        if not master or master.role not in {UserRole.MASTER, UserRole.SUPER_ADMIN}:
            raise ValueError("Мастер не найден")

    async def _validate_junior_role(self, session: AsyncSession, junior_id: int) -> None:
        junior = await session.get(User, junior_id)
        if not junior or junior.role != UserRole.JUNIOR_MASTER:
            raise ValueError("Младший мастер не найден")

    async def _validate_actor_role(self, session: AsyncSession, actor_id: int, *, allowed_roles: set[UserRole]) -> None:
        actor = await session.get(User, actor_id)
        if not actor or actor.role not in allowed_roles:
            raise ValueError("Нет прав")

    async def _ensure_no_active_link(self, session: AsyncSession, junior_id: int) -> None:
        existing = await self.get_active_link_for_junior(session, junior_id)
        if existing:
            raise ValueError("У младшего мастера уже есть активная привязка")

    async def _count_active_links(self, session: AsyncSession, master_id: int) -> int:
        result = await session.execute(
            select(func.count()).select_from(MasterJuniorLink).where(
                MasterJuniorLink.master_id == master_id, MasterJuniorLink.is_active.is_(True)
            )
        )
        return int(result.scalar() or 0)
