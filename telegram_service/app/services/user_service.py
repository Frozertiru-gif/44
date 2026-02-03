from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.enums import UserRole
from app.db.models import User


class UserService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def ensure_user(self, session: AsyncSession, tg_user_id: int, display_name: str | None) -> User:
        result = await session.execute(select(User).where(User.id == tg_user_id))
        user = result.scalar_one_or_none()
        required_role: UserRole | None = None
        if self.settings.super_admin is not None and tg_user_id == self.settings.super_admin:
            required_role = UserRole.SUPER_ADMIN
        elif tg_user_id in self.settings.sys_admin_id_set():
            required_role = UserRole.SYS_ADMIN
        if user:
            user.display_name = display_name
            if required_role == UserRole.SUPER_ADMIN and user.role != UserRole.SUPER_ADMIN:
                user.role = UserRole.SUPER_ADMIN
            elif required_role == UserRole.SYS_ADMIN and user.role not in {UserRole.SYS_ADMIN, UserRole.SUPER_ADMIN}:
                user.role = UserRole.SYS_ADMIN
            await session.flush()
            return user

        role = required_role or UserRole.JUNIOR_ADMIN

        user = User(id=tg_user_id, role=role, display_name=display_name, is_active=True)
        session.add(user)
        await session.flush()
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
