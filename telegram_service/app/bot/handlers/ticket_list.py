from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.permissions import CANCEL_ROLES, TICKET_LIST_ROLES
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

    await message.answer("Фильтр списка:", reply_markup=ticket_list_filters())


@router.callback_query(F.data.startswith("list:"))
async def list_tickets_filtered(callback: CallbackQuery) -> None:
    filter_key = callback.data.split(":", 1)[1]

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session, callback.from_user.id, callback.from_user.full_name if callback.from_user else None
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
            await callback.answer("Нет доступа", show_alert=True)
            return

        tickets = await ticket_service.list_for_actor(session, user, filter_key=filter_key)

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
        ticket = await ticket_service.get_ticket_for_actor(session, ticket_id, user)

    if not ticket:
        await callback.answer("Нет доступа к заказу", show_alert=True)
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
