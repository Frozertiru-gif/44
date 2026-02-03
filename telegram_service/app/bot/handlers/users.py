from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.permissions import USER_ADMIN_ROLES
from app.bot.keyboards.confirmations import confirm_action_keyboard
from app.bot.keyboards.users import user_list_keyboard, user_role_keyboard
from app.bot.states.user_percent import UserPercentStates
from app.db.enums import UserRole
from app.db.session import async_session_factory
from app.services.audit_service import AuditService
from app.services.user_service import UserService

router = Router()
user_service = UserService()
audit_service = AuditService()
logger = logging.getLogger(__name__)


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
    master_percent = f"{target.master_percent:.2f}" if target.master_percent is not None else "-"
    admin_percent = f"{target.admin_percent:.2f}" if target.admin_percent is not None else "-"
    await callback.message.answer(
        f"Пользователь {target.id}\n"
        f"Имя: {target.display_name or '-'}\n"
        f"Роль: {target.role.value}\n"
        f"Статус: {'активен' if target.is_active else 'выключен'}\n"
        f"% мастера: {master_percent}\n"
        f"% админа: {admin_percent}",
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

        old_role = target.role
        role = UserRole(role_value)
        await user_service.set_role(session, target, role)
        logger.info(
            "User role change requested: target_user_id=%s target_tg_user_id=%s old_role=%s new_role=%s",
            target.id,
            target.id,
            old_role.value,
            role.value,
        )
        await audit_service.log_audit_event(
            session,
            actor_id=actor.id,
            action="USER_ROLE_CHANGED",
            entity_type="user",
            entity_id=target.id,
            payload={"role": role.value},
        )
        await session.commit()
        logger.info(
            "User role change committed: target_user_id=%s target_tg_user_id=%s new_role=%s",
            target.id,
            target.id,
            role.value,
        )

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


@router.callback_query(F.data.startswith("user_percent:"))
async def user_percent_start(callback: CallbackQuery, state: FSMContext) -> None:
    _, percent_type, user_id = callback.data.split(":", 2)
    user_id_int = int(user_id)

    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in USER_ADMIN_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return
    await state.clear()
    await state.update_data(user_id=user_id_int, percent_type=percent_type)
    await state.set_state(UserPercentStates.percent)
    await callback.message.answer("Введите процент (0..100, до 2 знаков после запятой):")
    await callback.answer()


@router.message(UserPercentStates.percent)
async def user_percent_set(message: Message, state: FSMContext) -> None:
    text = (message.text or "").replace(",", ".").strip()
    try:
        percent = Decimal(text)
    except (InvalidOperation, ValueError):
        await message.answer("Введите корректный процент.")
        return

    data = await state.get_data()
    user_id = data.get("user_id")
    percent_type = data.get("percent_type")
    if not isinstance(user_id, int) or percent_type not in {"master", "admin"}:
        await message.answer("Сессия устарела.")
        await state.clear()
        return

    await state.update_data(percent=percent)
    await state.set_state(UserPercentStates.confirm)
    await message.answer(
        "Вы уверены? Это действие нельзя отменить.",
        reply_markup=confirm_action_keyboard("user_percent_confirm", "user_percent_cancel"),
    )


@router.callback_query(F.data == "user_percent_cancel")
async def user_percent_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Изменение отменено")


@router.callback_query(F.data == "user_percent_confirm")
async def user_percent_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    user_id = data.get("user_id")
    percent_type = data.get("percent_type")
    percent = data.get("percent")
    if not isinstance(user_id, int) or percent_type not in {"master", "admin"} or not isinstance(percent, Decimal):
        await callback.answer("Сессия устарела", show_alert=True)
        await state.clear()
        return

    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in USER_ADMIN_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=actor.id,
                action="PERMISSION_DENIED",
                entity_type="user",
                entity_id=user_id,
                payload={"reason": "SET_PERCENT"},
            )
            await callback.answer("Нет прав", show_alert=True)
            await session.commit()
            await state.clear()
            return

        target = await user_service.get_user(session, user_id)
        if not target:
            await callback.answer("Пользователь не найден.", show_alert=True)
            await state.clear()
            return

        try:
            if percent_type == "master":
                before_value = target.master_percent
                await user_service.set_master_percent(session, target, percent)
                action = "USER_MASTER_PERCENT_SET"
            else:
                before_value = target.admin_percent
                await user_service.set_admin_percent(session, target, percent)
                action = "USER_ADMIN_PERCENT_SET"
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return

        await audit_service.log_audit_event(
            session,
            actor_id=actor.id,
            action=action,
            entity_type="user",
            entity_id=target.id,
            payload={
                "before": {"percent": float(before_value)} if before_value is not None else None,
                "after": {"percent": float(percent)},
            },
        )
        await session.commit()

    await state.clear()
    await callback.message.answer("Процент обновлен.")
    await callback.answer()
