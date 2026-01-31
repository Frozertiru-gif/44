from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.permissions import USER_ADMIN_ROLES
from app.bot.keyboards.users import user_list_keyboard, user_role_keyboard
from app.db.enums import UserRole
from app.db.session import async_session_factory
from app.services.audit_service import AuditService
from app.services.user_service import UserService

router = Router()
user_service = UserService()
audit_service = AuditService()


@router.message(F.text == "👥 Пользователи")
async def users_list(message: Message) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session, message.from_user.id, message.from_user.full_name if message.from_user else None
        )
        if not user.is_active or user.role not in USER_ADMIN_ROLES:
            await message.answer("У вас нет прав для управления пользователями.")
            return

        users = await user_service.list_users(session)

    user_ids = [item.id for item in users]
    await message.answer("Пользователи:", reply_markup=user_list_keyboard(user_ids))


@router.callback_query(F.data.startswith("user:"))
async def user_card(callback: CallbackQuery) -> None:
    user_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in USER_ADMIN_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return

        target = await user_service.get_user(session, user_id)

    if not target:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await callback.message.answer(
        f"Пользователь {target.id}\n"
        f"Имя: {target.display_name or '-'}\n"
        f"Роль: {target.role.value}\n"
        f"Статус: {'активен' if target.is_active else 'выключен'}",
        reply_markup=user_role_keyboard(target.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("role:"))
async def user_set_role(callback: CallbackQuery) -> None:
    _, user_id, role_value = callback.data.split(":", 2)
    user_id_int = int(user_id)

    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in USER_ADMIN_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return

        target = await user_service.get_user(session, user_id_int)
        if not target:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        role = UserRole(role_value)
        await user_service.set_role(session, target, role)
        await audit_service.log_audit_event(
            session,
            actor_id=actor.id,
            action="USER_ROLE_CHANGED",
            entity_type="user",
            entity_id=target.id,
            payload={"role": role.value},
        )
        await session.commit()

    await callback.answer("Роль обновлена")


@router.callback_query(F.data.startswith("user_disable:"))
async def user_disable(callback: CallbackQuery) -> None:
    user_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in USER_ADMIN_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return

        target = await user_service.get_user(session, user_id)
        if not target:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        await user_service.set_active(session, target, False)
        await audit_service.log_audit_event(
            session,
            actor_id=actor.id,
            action="USER_DISABLED",
            entity_type="user",
            entity_id=target.id,
            payload=None,
        )
        await session.commit()

    await callback.answer("Пользователь выключен")


@router.callback_query(F.data.startswith("user_enable:"))
async def user_enable(callback: CallbackQuery) -> None:
    user_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in USER_ADMIN_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return

        target = await user_service.get_user(session, user_id)
        if not target:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        await user_service.set_active(session, target, True)
        await audit_service.log_audit_event(
            session,
            actor_id=actor.id,
            action="USER_ENABLED",
            entity_type="user",
            entity_id=target.id,
            payload=None,
        )
        await session.commit()

    await callback.answer("Пользователь включен")
