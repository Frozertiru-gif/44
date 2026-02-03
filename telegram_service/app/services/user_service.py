from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.enums import UserRole
from app.db.models import User

logger = logging.getLogger(__name__)

ROLE_PRIORITY = {
    UserRole.USER: 0,
    UserRole.JUNIOR_ADMIN: 1,
    UserRole.JUNIOR_MASTER: 2,
    UserRole.MASTER: 3,
    UserRole.ADMIN: 4,
    UserRole.SYS_ADMIN: 5,
    UserRole.SUPER_ADMIN: 6,
}


class UserService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def ensure_user(
        self,
        session: AsyncSession,
        tg_user_id: int,
        display_name: str | None,
        username: str | None = None,
        log_diagnostics: bool = False,
    ) -> User:
        result = await session.execute(select(User).where(User.id == tg_user_id))
        user = result.scalar_one_or_none()
        required_role: UserRole | None = None
        reason: str | None = None
        if self.settings.super_admin is not None and tg_user_id == self.settings.super_admin:
            required_role = UserRole.SUPER_ADMIN
            reason = "super_admin_env"
        elif tg_user_id in self.settings.sys_admin_id_set():
            required_role = UserRole.SYS_ADMIN
            reason = "sys_admin_env"
        if user:
            user.display_name = display_name
            user.username = username
            if required_role and ROLE_PRIORITY[required_role] > ROLE_PRIORITY[user.role]:
                old_role = user.role
                user.role = required_role
                logger.info(
                    "User role promoted via env: tg_user_id=%s db_user_id=%s old_role=%s new_role=%s reason=%s",
                    tg_user_id,
                    user.id,
                    old_role.value,
                    user.role.value,
                    reason,
                )
            await session.flush()
            if log_diagnostics:
                logger.info(
                    "Ensure user diagnostics: tg_user_id=%s db_user_id=%s role=%s display_name=%s",
                    tg_user_id,
                    user.id,
                    user.role.value,
                    user.display_name,
                )
            return user

        role = required_role or UserRole.USER

        user = User(id=tg_user_id, role=role, display_name=display_name, username=username, is_active=True)
        session.add(user)
        await session.flush()
        if log_diagnostics:
            logger.info(
                "Ensure user diagnostics: tg_user_id=%s db_user_id=%s role=%s display_name=%s",
                tg_user_id,
                user.id,
                user.role.value,
                user.display_name,
            )
        return user

    async def list_users(self, session: AsyncSession, limit: int = 20) -> list[User]:
        result = await session.execute(select(User).order_by(User.id.desc()).limit(limit))
        return list(result.scalars().all())

    async def list_users_by_roles(self, session: AsyncSession, roles: set[UserRole], limit: int = 50) -> list[User]:
        result = await session.execute(select(User).where(User.role.in_(roles)).order_by(User.id.desc()).limit(limit))
        return list(result.scalars().all())

    async def get_user(self, session: AsyncSession, user_id: int) -> User | None:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def set_role(self, session: AsyncSession, user: User, role: UserRole) -> User:
        user.role = role
        await session.flush()
        return user

    async def set_active(self, session: AsyncSession, user: User, is_active: bool) -> User:
        user.is_active = is_active
        await session.flush()
        return user

    async def set_master_percent(self, session: AsyncSession, user: User, percent: Decimal | None) -> User:
        if percent is not None:
            percent = self._validate_percent(percent)
        user.master_percent = percent
        await session.flush()
        return user

    async def set_admin_percent(self, session: AsyncSession, user: User, percent: Decimal | None) -> User:
        if percent is not None:
            percent = self._validate_percent(percent)
        user.admin_percent = percent
        await session.flush()
        return user

    def _validate_percent(self, percent: Decimal) -> Decimal:
        if percent < 0 or percent > 100:
            raise ValueError("Процент должен быть от 0 до 100")
        if percent.as_tuple().exponent < -2:
            raise ValueError("Процент должен иметь максимум 2 знака после запятой")
        return percent
