from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.handlers.permissions import CANCEL_ROLES
from app.bot.handlers.utils import format_ticket_card
from app.db.session import async_session_factory
from app.services.audit_service import AuditService
from app.services.ticket_service import TicketService
from app.services.user_service import UserService

router = Router()
user_service = UserService()
ticket_service = TicketService()
audit_service = AuditService()


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_from_request_chat(callback: CallbackQuery) -> None:
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

    await callback.message.edit_text(format_ticket_card(ticket))
    await callback.answer("Заказ отменен")


@router.callback_query(F.data.startswith("edit:"))
async def edit_stub(callback: CallbackQuery) -> None:
    await callback.answer("Редактирование будет добавлено на следующем шаге.", show_alert=True)
