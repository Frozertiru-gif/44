from __future__ import annotations

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
        if user:
            user.display_name = display_name
            await session.flush()
            return user

        role = UserRole.JUNIOR_ADMIN
        if tg_user_id in self.settings.sys_admin_id_set():
            role = UserRole.SYS_ADMIN

        user = User(id=tg_user_id, role=role, display_name=display_name, is_active=True)
        session.add(user)
        await session.flush()
        return user

    async def list_users(self, session: AsyncSession, limit: int = 20) -> list[User]:
        result = await session.execute(select(User).order_by(User.id.desc()).limit(limit))
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
