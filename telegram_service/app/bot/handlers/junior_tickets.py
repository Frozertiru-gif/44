from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.utils import format_ticket_card, format_ticket_list
from app.bot.keyboards.junior_tickets import junior_ticket_list_items
from app.db.enums import TicketStatus, UserRole
from app.db.session import async_session_factory
from app.services.junior_link_service import JuniorLinkService
from app.services.ticket_service import TicketService
from app.services.user_service import UserService

router = Router()
user_service = UserService()
ticket_service = TicketService()
junior_link_service = JuniorLinkService()


@router.message(F.text == "📋 Заявки моего мастера")
async def junior_master_tickets(message: Message) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            message.from_user.id,
            message.from_user.full_name if message.from_user else None,
            message.from_user.username if message.from_user else None
        )
        await session.commit()
        if not user.is_active or user.role != UserRole.JUNIOR_MASTER:
            await message.answer("У вас нет доступа.")
            return

        link = await junior_link_service.get_active_master_for_junior(session, user.id)
        if not link:
            await message.answer("У вас нет активной привязки к мастеру.")
            return

        statuses = [TicketStatus.IN_WORK, TicketStatus.TAKEN, TicketStatus.IN_PROGRESS, TicketStatus.CLOSED]
        tickets = await ticket_service.list_for_master(session, link.master_id, statuses=statuses)

    if not tickets:
        await message.answer("У мастера пока нет заявок в работе.")
        return

    ticket_ids = [ticket.id for ticket in tickets[:10]]
    await message.answer(format_ticket_list(tickets), reply_markup=junior_ticket_list_items(ticket_ids))


@router.callback_query(F.data.startswith("junior_ticket:"))
async def junior_master_ticket_card(callback: CallbackQuery) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        if not user.is_active or user.role != UserRole.JUNIOR_MASTER:
            await callback.answer("Нет прав", show_alert=True)
            return

        link = await junior_link_service.get_active_master_for_junior(session, user.id)
        if not link:
            await callback.answer("Нет активной привязки", show_alert=True)
            return

        ticket = await ticket_service.get_ticket(session, ticket_id)
        if not ticket or ticket.assigned_executor_id != link.master_id:
            await callback.answer("Нет доступа к заказу", show_alert=True)
            return

    await callback.message.answer(format_ticket_card(ticket))
    await callback.answer()
