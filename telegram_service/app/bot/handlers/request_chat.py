from __future__ import annotations

from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery

from app.bot.handlers.permissions import CANCEL_ROLES, MASTER_ROLES, CREATE_ROLES
from app.bot.handlers.utils import (
    format_lead_card,
    format_ticket_card,
    format_ticket_event_cancelled,
    format_ticket_event_taken,
    ticket_display_id,
)
from app.bot.keyboards.request_chat import executor_only_keyboard, lead_request_keyboard
from app.bot.keyboards.ticket_wizard import category_keyboard
from app.bot.states.ticket_create import TicketCreateStates
from app.core.config import get_settings
from app.db.enums import LeadStatus
from app.db.session import async_session_factory
from app.services.audit_service import AuditService
from app.services.lead_service import LeadService
from app.services.ticket_service import TicketService
from app.services.user_service import UserService

router = Router()
user_service = UserService()
ticket_service = TicketService()
audit_service = AuditService()
lead_service = LeadService()
settings = get_settings()


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_from_request_chat(callback: CallbackQuery, bot: Bot) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None,
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

    await bot.send_message(settings.events_chat_id, format_ticket_event_cancelled(ticket))
    await callback.answer("Заказ отменен")


@router.callback_query(F.data.startswith("request_take:"))
async def request_take(callback: CallbackQuery, bot: Bot) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None,
        )
        if not user.is_active or user.role not in MASTER_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=ticket_id,
                payload={"reason": "TAKE_TICKET"},
                ticket_id=ticket_id,
            )
            await session.commit()
            await callback.answer(f"Нет доступа. Ваша роль: {user.role.value}", show_alert=True)
            return

        ticket = await ticket_service.take_ticket(session, ticket_id, user.id)

        if not ticket:
            await session.rollback()
            await callback.answer("Заказ уже принят или недоступен.", show_alert=True)
            return
        await session.commit()

    await bot.send_message(settings.events_chat_id, format_ticket_event_taken(ticket))
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=executor_only_keyboard(ticket.assigned_executor))
        except TelegramBadRequest:
            pass
    if ticket.assigned_executor_id == user.id:
        await bot.send_message(
            user.id,
            f"Вы приняли заявку #{ticket_display_id(ticket)}.\n\n{format_ticket_card(ticket)}",
        )
    await callback.answer("Заказ принят")


@router.callback_query(F.data.startswith("edit:"))
async def edit_stub(callback: CallbackQuery) -> None:
    await callback.answer("Редактирование будет добавлено на следующем шаге.", show_alert=True)


@router.callback_query(F.data.startswith("lead:"))
async def lead_action(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) < 3:
        await callback.answer("Некорректное действие", show_alert=True)
        return

    action = parts[1]
    try:
        lead_id = UUID(parts[2])
    except ValueError:
        await callback.answer("Некорректный lead id", show_alert=True)
        return

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None,
        )
        if not user.is_active or user.role not in CREATE_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="lead",
                entity_id=str(lead_id),
                payload={"reason": "LEAD_ACTION", "action": action},
            )
            await session.commit()
            await callback.answer("Нет прав", show_alert=True)
            return

        lead = await lead_service.get_lead(session, lead_id)
        if not lead:
            await callback.answer("Заявка не найдена", show_alert=True)
            return

        if action in {"need_info", "spam"}:
            if lead.status == LeadStatus.CONVERTED:
                await callback.answer("Заявка уже конвертирована", show_alert=True)
                return
            status = LeadStatus.NEED_INFO if action == "need_info" else LeadStatus.SPAM
            await lead_service.set_status(session, lead=lead, status=status, actor_id=user.id)
            await session.commit()
            await callback.message.edit_text(format_lead_card(lead), reply_markup=lead_request_keyboard(lead.id))
            await callback.answer("Статус обновлен")
            return

        if action != "convert":
            await callback.answer("Неизвестное действие", show_alert=True)
            return

        if lead.status in {LeadStatus.CONVERTED, LeadStatus.SPAM}:
            await callback.answer("Нельзя оформить эту заявку", show_alert=True)
            return

        prefill = lead_service.build_ticket_prefill(lead)
        private_state = FSMContext(
            storage=state.storage,
            key=StorageKey(
                bot_id=bot.id,
                chat_id=callback.from_user.id,
                user_id=callback.from_user.id,
            ),
        )
        await private_state.clear()
        await private_state.update_data(
            lead_id=str(lead.id),
            lead_message_chat_id=callback.message.chat.id if callback.message else None,
            lead_message_id=callback.message.message_id if callback.message else None,
            **prefill,
        )
        await private_state.set_state(TicketCreateStates.category)
        await bot.send_message(callback.from_user.id, "Выберите категорию:", reply_markup=await category_keyboard())
        await callback.answer("Открываю оформление в личных сообщениях")
