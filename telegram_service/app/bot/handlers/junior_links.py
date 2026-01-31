from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.permissions import JUNIOR_LINK_ADMIN_ROLES
from app.bot.keyboards.junior_links import (
    junior_select_keyboard,
    master_links_keyboard,
    master_select_keyboard,
    relink_master_keyboard,
)
from app.bot.states.junior_links import JuniorLinkStates
from app.db.enums import UserRole
from app.db.models import MasterJuniorLink
from app.db.session import async_session_factory
from app.services.junior_link_service import JuniorLinkService
from app.services.user_service import UserService

router = Router()
user_service = UserService()
junior_link_service = JuniorLinkService()


def parse_percent(value: str) -> Decimal | None:
    cleaned = value.replace(" ", "").replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return amount


@router.message(F.text == "👥 Привязки младших мастеров")
async def junior_links_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session, message.from_user.id, message.from_user.full_name if message.from_user else None
        )
        await session.commit()

        if not user.is_active:
            await message.answer("У вас нет доступа.")
            return

        if user.role in JUNIOR_LINK_ADMIN_ROLES:
            masters = await user_service.list_users_by_roles(session, {UserRole.MASTER, UserRole.SUPER_ADMIN})
            if not masters:
                await message.answer("Нет мастеров для привязки.")
                return
            await message.answer("Выберите мастера:", reply_markup=master_select_keyboard(masters))
            return

        if user.role == UserRole.MASTER:
            links = await junior_link_service.get_active_juniors_for_master(session, user.id)
            allow_percent = len(links) >= 2
            if not links:
                await message.answer("Нет активных привязок.")
                return
            await message.answer(
                "Ваши младшие мастера:",
                reply_markup=master_links_keyboard(user.id, links, allow_manage=False, allow_percent=allow_percent),
            )
            return

    await message.answer("У вас нет прав для управления привязками.")


@router.callback_query(F.data.startswith("link_master:"))
async def link_master_card(callback: CallbackQuery) -> None:
    master_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in JUNIOR_LINK_ADMIN_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return

        links = await junior_link_service.get_active_juniors_for_master(session, master_id)
        active_count = len(links)
        allow_percent = actor.role in {UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN} or active_count <= 1

    text_lines = ["Привязки младших мастеров:"]
    if links:
        for link in links:
            junior = link.junior_master
            junior_label = junior.display_name if junior else f"ID {link.junior_master_id}"
            text_lines.append(f"- {junior_label}: {link.percent:.2f}%")
    else:
        text_lines.append("Нет активных привязок.")

    await callback.message.answer(
        "\n".join(text_lines),
        reply_markup=master_links_keyboard(master_id, links, allow_manage=True, allow_percent=allow_percent),
    )
    await callback.answer()


@router.callback_query(F.data == "link_back")
async def link_back(callback: CallbackQuery) -> None:
    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in JUNIOR_LINK_ADMIN_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return

        masters = await user_service.list_users_by_roles(session, {UserRole.MASTER, UserRole.SUPER_ADMIN})
    await callback.message.answer("Выберите мастера:", reply_markup=master_select_keyboard(masters))
    await callback.answer()


@router.callback_query(F.data.startswith("link_add:"))
async def link_add(callback: CallbackQuery, state: FSMContext) -> None:
    master_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in JUNIOR_LINK_ADMIN_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return

        juniors = await user_service.list_users_by_roles(session, {UserRole.JUNIOR_MASTER})
        if not juniors:
            await callback.answer("Нет младших мастеров", show_alert=True)
            return
    await state.update_data(action="add", master_id=master_id)
    await callback.message.answer("Выберите младшего мастера:", reply_markup=junior_select_keyboard(juniors, prefix="link_pick"))
    await callback.answer()


@router.callback_query(F.data.startswith("link_pick:"))
async def link_pick_junior(callback: CallbackQuery, state: FSMContext) -> None:
    junior_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    action = data.get("action")
    master_id = data.get("master_id")
    if action != "add" or not isinstance(master_id, int):
        await callback.answer("Сессия устарела", show_alert=True)
        await state.clear()
        return

    await state.update_data(junior_id=junior_id)
    await state.set_state(JuniorLinkStates.percent)
    await callback.message.answer("Введите процент для младшего мастера (0..100):")
    await callback.answer()


@router.callback_query(F.data.startswith("link_percent:"))
async def link_change_percent(callback: CallbackQuery, state: FSMContext) -> None:
    link_id = int(callback.data.split(":", 1)[1])
    await state.update_data(action="percent", link_id=link_id)
    await state.set_state(JuniorLinkStates.percent)
    await callback.message.answer("Введите новый процент (0..100):")
    await callback.answer()


@router.callback_query(F.data.startswith("link_relink:"))
async def link_relink(callback: CallbackQuery, state: FSMContext) -> None:
    link_id = int(callback.data.split(":", 1)[1])
    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in JUNIOR_LINK_ADMIN_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return
        link = await session.get(MasterJuniorLink, link_id)
    if not link:
        await callback.answer("Привязка не найдена", show_alert=True)
        return

    async with async_session_factory() as session:
        masters = await user_service.list_users_by_roles(session, {UserRole.MASTER, UserRole.SUPER_ADMIN})
        if not masters:
            await callback.answer("Нет доступных мастеров", show_alert=True)
            return
    await state.update_data(action="relink", junior_id=link.junior_master_id)
    await callback.message.answer("Выберите нового мастера:", reply_markup=relink_master_keyboard(masters))
    await callback.answer()


@router.callback_query(F.data.startswith("relink_master:"))
async def link_relink_master(callback: CallbackQuery, state: FSMContext) -> None:
    master_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    if data.get("action") != "relink":
        await callback.answer("Сессия устарела", show_alert=True)
        await state.clear()
        return
    await state.update_data(master_id=master_id)
    await state.set_state(JuniorLinkStates.percent)
    await callback.message.answer("Введите процент для новой привязки (0..100):")
    await callback.answer()


@router.callback_query(F.data.startswith("link_disable:"))
async def link_disable(callback: CallbackQuery) -> None:
    link_id = int(callback.data.split(":", 1)[1])
    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not actor.is_active or actor.role not in JUNIOR_LINK_ADMIN_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return
        try:
            async with session.begin():
                await junior_link_service.disable_link(session, link_id=link_id, actor_id=actor.id)
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return

    await callback.answer("Привязка отключена")


@router.message(JuniorLinkStates.percent)
async def link_percent_input(message: Message, state: FSMContext) -> None:
    percent = parse_percent(message.text or "")
    if percent is None:
        await message.answer("Введите корректный процент (0..100).")
        return

    data = await state.get_data()
    action = data.get("action")
    link_id = data.get("link_id")
    master_id = data.get("master_id")
    junior_id = data.get("junior_id")

    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, message.from_user.id, message.from_user.full_name if message.from_user else None
        )
        if not actor.is_active:
            await message.answer("Нет доступа.")
            await state.clear()
            return

        try:
            async with session.begin():
                if action == "add" and isinstance(master_id, int) and isinstance(junior_id, int):
                    await junior_link_service.link_junior_to_master(
                        session,
                        master_id=master_id,
                        junior_id=junior_id,
                        percent=percent,
                        actor_id=actor.id,
                    )
                elif action == "percent" and isinstance(link_id, int):
                    await junior_link_service.set_link_percent(
                        session,
                        link_id=link_id,
                        percent=percent,
                        actor_id=actor.id,
                    )
                elif action == "relink" and isinstance(master_id, int) and isinstance(junior_id, int):
                    await junior_link_service.relink_junior(
                        session,
                        junior_id=junior_id,
                        new_master_id=master_id,
                        percent=percent,
                        actor_id=actor.id,
                    )
                else:
                    await message.answer("Сессия устарела.")
                    await state.clear()
                    return
        except ValueError as exc:
            await message.answer(str(exc))
            return

    await state.clear()
    await message.answer("Данные сохранены.")
