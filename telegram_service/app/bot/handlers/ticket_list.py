from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.permissions import CANCEL_ROLES, CREATE_ROLES
from app.bot.handlers.utils import format_ticket_card, format_ticket_list
from app.bot.keyboards.main_menu import build_main_menu
from app.bot.keyboards.ticket_list import ticket_actions, ticket_list_filters, ticket_list_items
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
            session, message.from_user.id, message.from_user.full_name if message.from_user else None
        )
        await session.commit()

    if not user.is_active or user.role not in CREATE_ROLES:
        await message.answer("У вас нет доступа к списку заказов.")
        return

    await message.answer("Фильтр списка:", reply_markup=ticket_list_filters())


@router.callback_query(F.data.startswith("list:"))
async def list_tickets_filtered(callback: CallbackQuery) -> None:
    filter_key = callback.data.split(":", 1)[1]

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not user.is_active or user.role not in CREATE_ROLES:
            await callback.answer("Нет доступа", show_alert=True)
            return

        if filter_key == "active":
            tickets = await ticket_service.list_active(session)
        elif filter_key == "repeat":
            tickets = await ticket_service.list_repeats(session)
        else:
            tickets = await ticket_service.list_tickets(session)

    ticket_ids = [ticket.id for ticket in tickets[:10]]
    await callback.message.answer(format_ticket_list(tickets), reply_markup=ticket_list_items(ticket_ids))
    await callback.answer()


@router.callback_query(F.data.startswith("ticket:"))
async def open_ticket(callback: CallbackQuery) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        ticket = await ticket_service.get_ticket(session, ticket_id)

    if not ticket:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    can_cancel = user.role in CANCEL_ROLES and user.is_active
    await callback.message.answer(format_ticket_card(ticket), reply_markup=ticket_actions(ticket_id, can_cancel))
    await callback.answer()


@router.callback_query(F.data.startswith("ticket_cancel:"))
async def cancel_ticket(callback: CallbackQuery) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
        )
        if not user.is_active or user.role not in CANCEL_ROLES:
            await callback.answer("Нет прав", show_alert=True)
            return

        ticket = await ticket_service.get_ticket(session, ticket_id)
        if not ticket:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        await ticket_service.cancel_ticket(session, ticket)
        await audit_service.log_event(session, ticket_id=ticket.id, action="TICKET_CANCELLED", actor_id=user.id)
        await session.commit()

    await callback.message.answer(f"Заказ #{ticket_id} отменен.", reply_markup=await build_main_menu(user.role))
    await callback.answer()
