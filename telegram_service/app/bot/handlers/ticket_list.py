from __future__ import annotations

from math import ceil

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.permissions import CANCEL_ROLES, CREATE_ROLES, TICKET_LIST_ROLES
from app.bot.handlers.utils import format_ticket_card
from app.bot.keyboards.ticket_list import ticket_list_keyboard
from app.bot.states.ticket_list import AdminSearchStates
from app.bot.keyboards.main_menu import build_main_menu
from app.bot.keyboards.ticket_list import ticket_actions, ticket_list_filters
from app.db.session import async_session_factory
from app.services.audit_service import AuditService
from app.services.ticket_service import TicketService
from app.services.user_service import UserService

router = Router()
user_service = UserService()
ticket_service = TicketService()
audit_service = AuditService()


@router.message(F.text == "📋 Список заказов")
async def list_tickets(message: Message) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            message.from_user.id,
            message.from_user.full_name if message.from_user else None,
            message.from_user.username if message.from_user else None
        )
        await session.commit()

    if not user.is_active or user.role not in TICKET_LIST_ROLES:
        async with async_session_factory() as session:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=None,
                payload={"reason": "LIST_TICKETS"},
            )
            await session.commit()
        await message.answer("У вас нет доступа к списку заказов.")
        return

    show_search = user.role in CREATE_ROLES
    await message.answer("Фильтр списка:", reply_markup=ticket_list_filters(show_search=show_search))


@router.callback_query(F.data.startswith("adm:list:"))
async def list_tickets_filtered(callback: CallbackQuery, state: FSMContext) -> None:
    payload = _parse_kv_payload(callback.data, prefix="adm:list:")
    filter_key = payload.get("filter", "all")
    page = int(payload.get("page", 0))

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        if not user.is_active or user.role not in TICKET_LIST_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=None,
                payload={"reason": "LIST_TICKETS"},
            )
            await session.commit()
            await callback.answer(f"Нет доступа. Ваша роль: {user.role.value}", show_alert=True)
            return

        state_data = await state.get_data()
        page_size = state_data.get("page_size", 15)
        tickets, total = await ticket_service.list_for_actor_page(
            session,
            user,
            filter_key=filter_key,
            page=page,
            page_size=page_size,
        )

        text = _render_admin_list_text(
            tickets,
            total=total,
            page=page,
            page_size=page_size,
            title="Список заявок",
            actor=user,
        )
        if len(text) > 3800 and page_size > 10:
            page_size = 10
            tickets, total = await ticket_service.list_for_actor_page(
                session,
                user,
                filter_key=filter_key,
                page=page,
                page_size=page_size,
            )
            text = _render_admin_list_text(
                tickets,
                total=total,
                page=page,
                page_size=page_size,
                title="Список заявок",
                actor=user,
            )
        await state.update_data(page_size=page_size, search_ticket_id=None, search_phone=None)
        total_pages = max(1, ceil(total / page_size)) if total else 1
        keyboard = ticket_list_keyboard(
            ticket_ids=[ticket.id for ticket in tickets],
            page=page,
            total_pages=total_pages,
            filter_key=filter_key,
            search_mode=False,
        )

    await state.set_state(AdminSearchStates.results)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "adm:list:close")
async def close_admin_list(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "adm:search:start")
async def admin_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None,
        )
        if not user.is_active or user.role not in CREATE_ROLES:
            await callback.answer("Нет доступа", show_alert=True)
            return
    await state.set_state(AdminSearchStates.wait_query)
    await callback.message.edit_text("Введите ID заявки, публичный номер (ДДММГГNN) или номер телефона.")
    await callback.answer()


@router.message(AdminSearchStates.wait_query)
async def admin_search_query(message: Message, state: FSMContext) -> None:
    query = message.text.strip() if message.text else ""
    if not query:
        await message.answer("Введите ID заявки, публичный номер (ДДММГГNN) или номер телефона.")
        return
    digits = _normalize_phone_digits(query)
    public_id = query if query.isdigit() and len(query) == 8 else None
    ticket_id = int(query) if query.isdigit() and len(query) != 8 else None
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            message.from_user.id,
            message.from_user.full_name if message.from_user else None,
            message.from_user.username if message.from_user else None,
        )
        if not user.is_active or user.role not in CREATE_ROLES:
            await message.answer("У вас нет доступа к поиску.")
            return
        page_size = 15
        tickets, total = await ticket_service.search_for_actor_page(
            session,
            user,
            ticket_id=ticket_id,
            public_id=public_id,
            phone_digits=digits if ticket_id is None and public_id is None else None,
            page=0,
            page_size=page_size,
        )
        text = _render_admin_list_text(
            tickets,
            total=total,
            page=0,
            page_size=page_size,
            title="Результаты поиска",
            actor=user,
        )
        if len(text) > 3800 and page_size > 10:
            page_size = 10
            tickets, total = await ticket_service.search_for_actor_page(
                session,
                user,
                ticket_id=ticket_id,
                public_id=public_id,
                phone_digits=digits if ticket_id is None and public_id is None else None,
                page=0,
                page_size=page_size,
            )
            text = _render_admin_list_text(
                tickets,
                total=total,
                page=0,
                page_size=page_size,
                title="Результаты поиска",
                actor=user,
            )
        total_pages = max(1, ceil(total / page_size)) if total else 1
        keyboard = ticket_list_keyboard(
            ticket_ids=[ticket.id for ticket in tickets],
            page=0,
            total_pages=total_pages,
            filter_key="all",
            search_mode=True,
        )
    await state.set_state(AdminSearchStates.results)
    await state.update_data(search_ticket_id=ticket_id, search_public_id=public_id, search_phone=digits, page_size=page_size)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("adm:search:page="))
async def admin_search_page(callback: CallbackQuery, state: FSMContext) -> None:
    payload = _parse_kv_payload(callback.data, prefix="adm:search:")
    page = int(payload.get("page", 0))
    data = await state.get_data()
    ticket_id = data.get("search_ticket_id")
    public_id = data.get("search_public_id")
    phone_digits = data.get("search_phone")
    page_size = data.get("page_size", 15)
    if ticket_id is None and not public_id and not phone_digits:
        await callback.answer("Поиск не найден. Повторите поиск.", show_alert=True)
        return
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None,
        )
        if not user.is_active or user.role not in CREATE_ROLES:
            await callback.answer("Нет доступа", show_alert=True)
            return
        tickets, total = await ticket_service.search_for_actor_page(
            session,
            user,
            ticket_id=ticket_id,
            public_id=public_id,
            phone_digits=phone_digits,
            page=page,
            page_size=page_size,
        )
        text = _render_admin_list_text(
            tickets,
            total=total,
            page=page,
            page_size=page_size,
            title="Результаты поиска",
            actor=user,
        )
        total_pages = max(1, ceil(total / page_size)) if total else 1
        keyboard = ticket_list_keyboard(
            ticket_ids=[ticket.id for ticket in tickets],
            page=page,
            total_pages=total_pages,
            filter_key="all",
            search_mode=True,
        )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "adm:search:back")
async def admin_search_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Фильтр списка:", reply_markup=ticket_list_filters(show_search=True))
    await callback.answer()


@router.callback_query(F.data.startswith("ticket:"))
async def open_ticket(callback: CallbackQuery) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        ticket = await ticket_service.get_ticket_for_actor(session, ticket_id, user)

    if not ticket:
        await callback.answer("Нет доступа к заказу", show_alert=True)
        return

    can_cancel = user.role in CANCEL_ROLES and user.is_active
    await callback.message.answer(format_ticket_card(ticket), reply_markup=ticket_actions(ticket_id, can_cancel))
    await callback.answer()


def _render_admin_list_text(
    tickets,
    *,
    total: int,
    page: int,
    page_size: int,
    title: str,
    actor,
) -> str:
    total_pages = max(1, ceil(total / page_size)) if total else 1
    header = f"{title} (страница {page + 1}/{total_pages})"
    if not tickets:
        return f"{header}\nНет заявок."
    lines = [header]
    show_phone = actor.role in CREATE_ROLES
    for ticket in tickets:
        city = _short_city(ticket.client_address)
        date_value = ticket.created_at.strftime("%d.%m.%Y") if ticket.created_at else "-"
        phone = f" • {ticket.client_phone}" if show_phone else ""
        lines.append(
            f"#{ticket.public_id or ticket.id} • {ticket.status.value} • {date_value} • {city}{phone}"
        )
    return "\n".join(lines)


def _short_city(address: str | None) -> str:
    if not address:
        return "-"
    return address.split(",", maxsplit=1)[0].strip() or "-"


def _normalize_phone_digits(raw: str) -> str:
    return "".join(char for char in raw if char.isdigit())


def _parse_kv_payload(payload: str, *, prefix: str) -> dict[str, str]:
    raw = payload[len(prefix):]
    parts = [part for part in raw.split(":") if part]
    parsed: dict[str, str] = {}
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            parsed[key] = value
    return parsed


@router.callback_query(F.data.startswith("ticket_cancel:"))
async def cancel_ticket(callback: CallbackQuery) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        if not user.is_active or user.role not in CANCEL_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=ticket_id,
                payload={"reason": "CANCEL_TICKET"},
                ticket_id=ticket_id,
            )
            await session.commit()
            await callback.answer("Нет прав", show_alert=True)
            return

        ticket = await ticket_service.get_ticket(session, ticket_id)
        if not ticket:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        before_status = ticket.status
        await ticket_service.cancel_ticket(session, ticket)
        await audit_service.log_event(
            session,
            ticket_id=ticket.id,
            action="TICKET_CANCELLED",
            actor_id=user.id,
            payload={
                "before": {"status": before_status.value if before_status else None},
                "after": {"status": ticket.status.value},
            },
        )
        await session.commit()

    await callback.message.answer(f"Заказ #{ticket_id} отменен.", reply_markup=await build_main_menu(user.role))
    await callback.answer()
