from __future__ import annotations

from decimal import Decimal, InvalidOperation
from math import ceil
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InputMediaPhoto, Message

from app.bot.handlers.permissions import MASTER_ROLES, TRANSFER_CONFIRM_ROLES
from app.bot.handlers.utils import (
    format_active_ticket_card,
    format_ticket_card,
    format_ticket_event_closed,
    format_ticket_event_status,
    format_ticket_event_taken,
    format_ticket_event_transfer,
    format_ticket_queue_card,
    format_closed_report,
    ticket_display_id,
)
from app.bot.keyboards.main_menu import build_main_menu
from app.bot.keyboards.ticket_execution import (
    active_ticket_actions,
    close_junior_keyboard,
    close_confirm_keyboard,
    close_photo_actions_keyboard,
    closed_ticket_actions,
    queue_ticket_actions,
    transfer_approval_actions,
    transfer_confirm_keyboard,
)
from app.bot.keyboards.ticket_list import worker_closed_keyboard
from app.bot.states.ticket_close import TicketCloseStates
from app.core.config import get_settings
from app.db.enums import TicketStatus, TransferStatus, UserRole, ticket_category_label
from app.db.session import async_session_factory
from app.services.audit_service import AuditService
from app.services.ticket_service import TicketService
from app.services.junior_link_service import JuniorLinkService
from app.services.user_service import UserService

router = Router()
settings = get_settings()
user_service = UserService()
ticket_service = TicketService()
junior_link_service = JuniorLinkService()
audit_service = AuditService()
logger = logging.getLogger(__name__)


def parse_amount(value: str) -> Decimal | None:
    cleaned = value.replace(" ", "").replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if amount < 0:
        return None
    return amount


@router.message(F.text == "🧾 Очередь")
async def queue_list(message: Message) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            message.from_user.id,
            message.from_user.full_name if message.from_user else None,
            message.from_user.username if message.from_user else None
        )
        await session.commit()
        if not user.is_active or user.role not in MASTER_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=None,
                payload={"reason": "QUEUE_LIST"},
            )
            await session.commit()
            await message.answer("У вас нет доступа к очереди.")
            return

        tickets = await ticket_service.list_queue(session)

    if not tickets:
        await message.answer("Очередь пуста.")
        return

    for ticket in tickets:
        await message.answer(format_ticket_queue_card(ticket), reply_markup=queue_ticket_actions(ticket.id))


@router.callback_query(F.data.startswith("queue_take:"))
async def queue_take(callback: CallbackQuery, bot: Bot) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])
    events_chat_id = settings.events_chat_id

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
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
            await callback.answer(f"Нет доступа. Ваша роль: {user.role.value}", show_alert=True)
            await session.commit()
            return

        ticket = await ticket_service.take_ticket(session, ticket_id, user.id)

        if not ticket:
            await session.rollback()
            await callback.answer("Заказ уже принят или недоступен.", show_alert=True)
            return

        await session.commit()

    await callback.message.edit_text(format_ticket_card(ticket))
    await bot.send_message(events_chat_id, format_ticket_event_taken(ticket))
    await callback.answer("Заказ принят")


@router.message(F.text == "🔥 Мои активные")
async def my_active(message: Message) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            message.from_user.id,
            message.from_user.full_name if message.from_user else None,
            message.from_user.username if message.from_user else None
        )
        await session.commit()
        if not user.is_active or user.role not in MASTER_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=None,
                payload={"reason": "LIST_ACTIVE"},
            )
            await session.commit()
            await message.answer("У вас нет доступа к активным заказам.")
            return

        tickets = await ticket_service.list_my_active(session, user.id)

    if not tickets:
        await message.answer("У вас нет активных заказов.")
        return

    for ticket in tickets:
        show_progress = ticket.status != TicketStatus.IN_PROGRESS
        show_close = ticket.status == TicketStatus.IN_PROGRESS
        await message.answer(
            format_active_ticket_card(ticket),
            reply_markup=active_ticket_actions(
                ticket.id,
                show_in_progress=show_progress,
                show_close=show_close,
            ),
        )


@router.message(F.text == "📦 Мои закрытые")
async def my_closed(message: Message) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            message.from_user.id,
            message.from_user.full_name if message.from_user else None,
            message.from_user.username if message.from_user else None
        )
        await session.commit()
        if not user.is_active or user.role not in MASTER_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=None,
                payload={"reason": "LIST_CLOSED"},
            )
            await session.commit()
            await message.answer("У вас нет доступа к закрытым заказам.")
            return

        tickets, total = await ticket_service.list_my_closed_page(session, user.id, page=0, page_size=12)

    await message.answer(
        _render_worker_closed_list(tickets, total=total, page=0, page_size=12),
        reply_markup=_worker_closed_keyboard(tickets, total=total, page=0),
    )


@router.callback_query(F.data.startswith("closed_open:"))
async def worker_closed_open(callback: CallbackQuery) -> None:
    try:
        ticket_id = int(callback.data.split(":", 1)[1])
        async with async_session_factory() as session:
            user = await user_service.ensure_user(
                session,
                callback.from_user.id,
                callback.from_user.full_name if callback.from_user else None,
                callback.from_user.username if callback.from_user else None,
            )
            ticket = await ticket_service.get_ticket_for_actor(session, ticket_id, user)

        if not ticket or (user.role in MASTER_ROLES and ticket.status != TicketStatus.CLOSED):
            await callback.answer("Нет доступа к заказу", show_alert=True)
            return

        allow_transfer = ticket.transfer_status == TransferStatus.NOT_SENT
        if callback.message:
            await callback.message.answer(
                format_ticket_card(ticket),
                reply_markup=closed_ticket_actions(ticket.id, allow_transfer=allow_transfer),
            )
        await callback.answer()
    except Exception:
        logger.exception("Failed to open closed ticket from callback", extra={"callback_data": callback.data})
        await callback.answer("Не удалось открыть заявку", show_alert=True)


@router.callback_query(F.data.startswith("wrk:closed:"))
async def worker_closed_pagination(callback: CallbackQuery) -> None:
    payload = _parse_kv_payload(callback.data, prefix="wrk:closed:")
    if "close" in callback.data:
        if callback.message:
            await callback.message.delete()
        await callback.answer()
        return

    page = int(payload.get("page", 0))
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None,
        )
        if not user.is_active or user.role not in MASTER_ROLES:
            await callback.answer("Нет доступа", show_alert=True)
            return
        tickets, total = await ticket_service.list_my_closed_page(session, user.id, page=page, page_size=12)
    text = _render_worker_closed_list(tickets, total=total, page=page, page_size=12)
    await callback.message.edit_text(
        text,
        reply_markup=_worker_closed_keyboard(tickets, total=total, page=page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("status_progress:"))
async def status_in_progress(callback: CallbackQuery, bot: Bot) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])
    events_chat_id = settings.events_chat_id

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        if not user.is_active or user.role not in MASTER_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=ticket_id,
                payload={"reason": "SET_IN_PROGRESS"},
                ticket_id=ticket_id,
            )
            await callback.answer(f"Нет доступа. Ваша роль: {user.role.value}", show_alert=True)
            await session.commit()
            return

        ticket = await ticket_service.set_in_progress(session, ticket_id, user.id)

        if not ticket:
            await session.rollback()
            await callback.answer("Нельзя сменить статус: заказ должен быть принят.", show_alert=True)
            return

        await session.commit()

    await callback.message.edit_text(format_ticket_card(ticket))
    await bot.send_message(events_chat_id, format_ticket_event_status(ticket))
    await callback.answer("Статус обновлен")


@router.callback_query(F.data.startswith("close_start:"))
async def close_start(callback: CallbackQuery, state: FSMContext) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        await session.commit()
        if not user.is_active or user.role not in MASTER_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=ticket_id,
                payload={"reason": "CLOSE_TICKET"},
                ticket_id=ticket_id,
            )
            await session.commit()
            await callback.answer(f"Нет доступа. Ваша роль: {user.role.value}", show_alert=True)
            return

        ticket = await ticket_service.get_ticket(session, ticket_id)
        if not ticket:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        if not ticket.assigned_executor_id:
            await callback.answer("Нет исполнителя для закрытия", show_alert=True)
            return
        if user.role not in {UserRole.SYS_ADMIN, UserRole.SUPER_ADMIN} and ticket.assigned_executor_id != user.id:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=ticket_id,
                payload={"reason": "CLOSE_TICKET_NOT_EXECUTOR"},
                ticket_id=ticket_id,
            )
            await session.commit()
            await callback.answer("Нет прав на закрытие", show_alert=True)
            return
        if ticket.status != TicketStatus.IN_PROGRESS:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="INVALID_STATE_TRANSITION",
                entity_type="ticket",
                entity_id=ticket_id,
                payload={"before": {"status": ticket.status.value}, "after": {"status": TicketStatus.CLOSED.value}},
                ticket_id=ticket_id,
            )
            await session.commit()
            await callback.answer("Нельзя закрыть заказ не из статуса 'В работе'.", show_alert=True)
            return

    await state.clear()
    await state.update_data(
        ticket_id=ticket_id,
        executor_id=ticket.assigned_executor_id,
        close_photos=[],
        close_photo_unique_ids=[],
    )
    await state.set_state(TicketCloseStates.revenue)
    await callback.message.answer("Введите доход по заказу:")
    await callback.answer()


@router.message(TicketCloseStates.revenue)
async def close_revenue(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text or "")
    if amount is None:
        await message.answer("Введите корректное число (>= 0).")
        return

    await state.update_data(revenue=amount)
    await state.set_state(TicketCloseStates.expense)
    await message.answer("Введите расходы по заказу:")


@router.message(TicketCloseStates.expense)
async def close_expense(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text or "")
    if amount is None:
        await message.answer("Введите корректное число (>= 0).")
        return

    data = await state.get_data()
    revenue = data.get("revenue")
    if not isinstance(revenue, Decimal):
        await state.set_state(TicketCloseStates.revenue)
        await message.answer("Введите доход по заказу:")
        return

    net_profit = revenue - amount
    if net_profit < 0:
        net_profit = Decimal("0")

    await state.update_data(expense=amount, net_profit=net_profit)
    data = await state.get_data()
    executor_id = data.get("executor_id")
    if not isinstance(executor_id, int):
        await message.answer("Не найден исполнитель заказа.")
        await state.clear()
        return

    async with async_session_factory() as session:
        links = await junior_link_service.get_active_juniors_for_master(session, executor_id)

    options = []
    for link in links:
        junior = link.junior_master
        label = junior.display_name if junior else f"ID {link.junior_master_id}"
        options.append((link.junior_master_id, label, f"{link.percent:.2f}"))

    await state.set_state(TicketCloseStates.junior)
    await message.answer(
        f"Доход: {revenue}\nРасход: {amount}\nЧистая прибыль: {net_profit}\n\n"
        f"Выберите младшего мастера:",
        reply_markup=close_junior_keyboard(options),
    )


@router.callback_query(F.data == "close_edit")
async def close_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TicketCloseStates.revenue)
    await callback.message.answer("Введите доход по заказу:")
    await callback.answer()


@router.callback_query(F.data.startswith("close_junior:"))
async def close_select_junior(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":", 1)[1]
    data = await state.get_data()
    executor_id = data.get("executor_id")
    revenue = data.get("revenue")
    expense = data.get("expense")
    net_profit = data.get("net_profit")
    if not isinstance(executor_id, int):
        await callback.answer("Сессия закрытия устарела", show_alert=True)
        await state.clear()
        return

    junior_id = None
    junior_percent = None
    junior_label = "Без младшего мастера"
    if choice != "none":
        junior_id = int(choice)
        async with async_session_factory() as session:
            link = await junior_link_service.get_active_link(session, executor_id, junior_id)
        if not link:
            await callback.answer("Младший мастер недоступен", show_alert=True)
            return
        junior_percent = link.percent
        junior = link.junior_master
        junior_label = junior.display_name if junior else f"ID {junior_id}"

    await state.update_data(junior_master_id=junior_id, junior_master_percent=junior_percent, junior_label=junior_label)
    await state.set_state(TicketCloseStates.comment)
    await callback.message.answer(
        f"Доход: {revenue}\nРасход: {expense}\nЧистая прибыль: {net_profit}\n"
        f"Младший мастер: {junior_label}\n\n"
        "Введите комментарий по закрытию (обязательно, можно написать '-' или 'без комментария')."
    )
    await callback.answer()


@router.message(TicketCloseStates.comment)
async def close_comment(message: Message, state: FSMContext) -> None:
    comment = (message.text or "").strip()
    if not comment:
        await message.answer("Комментарий обязателен. Введите текст или '-' .")
        return
    status_message = await message.answer(
        "Фото добавлено: 0. Отправьте ещё или нажмите «Готово».",
        reply_markup=close_photo_actions_keyboard(),
    )
    await state.update_data(
        closed_comment=comment,
        close_photos=[],
        close_photo_unique_ids=[],
        photos_count=0,
        photo_file_ids=[],
        photos_status_chat_id=status_message.chat.id,
        photos_status_message_id=status_message.message_id,
        photos_status_fallback_chat_id=status_message.chat.id,
    )
    await state.set_state(TicketCloseStates.photo)


@router.callback_query(TicketCloseStates.photo, F.data == "close_photo_skip")
async def close_photo_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(close_photos=[], close_photo_unique_ids=[], photos_count=0, photo_file_ids=[])
    await update_photos_status_message(
        state,
        callback.bot,
        text="Фото пропущено. Закрываю заявку…",
    )
    await _send_close_confirmation(callback.message, state)
    await callback.answer()


@router.callback_query(TicketCloseStates.photo, F.data == "close_photo_done")
async def close_photo_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    photos = data.get("close_photos")
    photo_count = len(photos) if isinstance(photos, list) else 0
    await update_photos_status_message(
        state,
        callback.bot,
        text=f"✅ Фото принято: {photo_count}. Закрываю заявку…",
    )
    await _send_close_confirmation(callback.message, state)
    await callback.answer()


@router.message(TicketCloseStates.photo, F.photo)
async def close_photo_from_photo(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1] if message.photo else None
    if not photo:
        await message.answer("Не удалось получить фото. Попробуйте ещё раз или нажмите «Готово».")
        return
    await _append_close_photo(
        message,
        state,
        file_id=photo.file_id,
        file_unique_id=getattr(photo, "file_unique_id", None),
    )


@router.message(TicketCloseStates.photo, F.document)
async def close_photo_from_document(message: Message, state: FSMContext) -> None:
    doc = message.document
    if not doc or not (doc.mime_type or "").startswith("image/"):
        await update_photos_status_message(state, message.bot, suffix="Нужен файл изображения.")
        return
    await _append_close_photo(
        message,
        state,
        file_id=doc.file_id,
        file_unique_id=getattr(doc, "file_unique_id", None),
    )


@router.message(TicketCloseStates.photo)
async def close_photo_invalid(message: Message, state: FSMContext) -> None:
    await update_photos_status_message(state, message.bot, suffix="Нужен файл изображения.")


async def _append_close_photo(message: Message, state: FSMContext, *, file_id: str, file_unique_id: str | None) -> None:
    data = await state.get_data()
    photos = data.get("close_photos")
    unique_ids = data.get("close_photo_unique_ids")
    if not isinstance(photos, list):
        photos = []
    if not isinstance(unique_ids, list):
        unique_ids = []

    limit = max(1, settings.close_photo_limit)
    if len(photos) >= limit:
        await update_photos_status_message(state, message.bot, suffix=f"Слишком много фото. Максимум: {limit}.")
        return

    if file_unique_id and file_unique_id in unique_ids:
        return

    photos.append({"file_id": file_id, "file_unique_id": file_unique_id})
    if file_unique_id:
        unique_ids.append(file_unique_id)

    photo_file_ids = [item.get("file_id") for item in photos if isinstance(item, dict) and item.get("file_id")]
    photos_count = len(photos)

    await state.update_data(
        close_photos=photos,
        close_photo_unique_ids=unique_ids,
        photos_count=photos_count,
        photo_file_ids=photo_file_ids,
    )
    await update_photos_status_message(state, message.bot, count=photos_count)


async def update_photos_status_message(
    state: FSMContext,
    bot: Bot,
    *,
    count: int | None = None,
    suffix: str | None = None,
    text: str | None = None,
) -> None:
    data = await state.get_data()
    if text is None:
        if count is None:
            raw_count = data.get("photos_count")
            count = raw_count if isinstance(raw_count, int) else 0
        text = f"Фото добавлено: {count}. Отправьте ещё или нажмите «Готово»."
        if suffix:
            text = f"{text}\n\n{suffix}"

    chat_id = data.get("photos_status_chat_id")
    message_id = data.get("photos_status_message_id")
    keyboard = close_photo_actions_keyboard()
    if isinstance(chat_id, int) and isinstance(message_id, int):
        try:
            await bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return

    fallback_chat_id = data.get("photos_status_fallback_chat_id")
    if not isinstance(fallback_chat_id, int):
        fallback_chat_id = chat_id if isinstance(chat_id, int) else None
    if not isinstance(fallback_chat_id, int):
        return

    status_message = await bot.send_message(
        chat_id=fallback_chat_id,
        text=text,
        reply_markup=keyboard,
    )
    await state.update_data(
        photos_status_chat_id=status_message.chat.id,
        photos_status_message_id=status_message.message_id,
        photos_status_fallback_chat_id=status_message.chat.id,
    )


async def _send_close_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    revenue = data.get("revenue")
    expense = data.get("expense")
    net_profit = data.get("net_profit")
    junior_label = data.get("junior_label") or "Без младшего мастера"
    comment = data.get("closed_comment")
    photos = data.get("close_photos")
    photo_count = len(photos) if isinstance(photos, list) else 0
    await state.set_state(TicketCloseStates.confirm)
    await message.answer(
        f"Доход: {revenue}\nРасход: {expense}\nЧистая прибыль: {net_profit}\n"
        f"Младший мастер: {junior_label}\n"
        f"Комментарий: {comment}\n"
        f"Фото: {photo_count}\n\n"
        "Вы уверены? Это действие нельзя отменить.",
        reply_markup=close_confirm_keyboard(),
    )


@router.callback_query(F.data == "close_confirm")
async def close_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    revenue = data.get("revenue")
    expense = data.get("expense")
    junior_master_id = data.get("junior_master_id")
    junior_master_percent = data.get("junior_master_percent")
    closed_comment = data.get("closed_comment")
    close_photos = data.get("close_photos")
    if not isinstance(close_photos, list):
        close_photos = []
    if (
        not isinstance(ticket_id, int)
        or not isinstance(revenue, Decimal)
        or not isinstance(expense, Decimal)
        or not isinstance(closed_comment, str)
    ):
        await callback.answer("Сессия закрытия устарела", show_alert=True)
        await state.clear()
        return
    events_chat_id = settings.events_chat_id
    closed_report_chat_id = settings.closed_report_chat_id

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        if not user.is_active or user.role not in MASTER_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=ticket_id,
                payload={"reason": "CLOSE_TICKET"},
                ticket_id=ticket_id,
            )
            await callback.answer(f"Нет доступа. Ваша роль: {user.role.value}", show_alert=True)
            await session.commit()
            await state.clear()
            return

        ticket = await ticket_service.close_ticket(
            session,
            ticket_id,
            user.id,
            revenue=revenue,
            expense=expense,
            junior_master_id=junior_master_id,
            junior_master_percent=junior_master_percent,
            closed_comment=closed_comment,
            close_photos=close_photos,
            allow_override=user.role in {UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN},
        )

        if not ticket:
            await session.rollback()
            await callback.answer("Нельзя закрыть заказ в текущем статусе.", show_alert=True)
            await state.clear()
            return

        await session.commit()

    await state.clear()
    await callback.message.answer("Заказ закрыт.")
    await callback.message.answer(format_ticket_card(ticket), reply_markup=await build_main_menu(user.role))
    await bot.send_message(events_chat_id, format_ticket_event_closed(ticket))
    report_text = format_closed_report(ticket)
    async with async_session_factory() as session:
        stored_photos = await ticket_service.get_close_photos(session, ticket.id)
    photo_file_ids = [item.file_id for item in stored_photos]
    if not photo_file_ids and ticket.closed_photo_file_id:
        photo_file_ids = [ticket.closed_photo_file_id]

    if photo_file_ids:
        media = [InputMediaPhoto(media=file_id) for file_id in photo_file_ids]
        media[0].caption = report_text
        await bot.send_media_group(closed_report_chat_id, media)
        if len(report_text) > 1024:
            await bot.send_message(closed_report_chat_id, report_text)
    else:
        await bot.send_message(closed_report_chat_id, report_text)
    await callback.answer()


@router.callback_query(F.data.startswith("transfer_sent:"))
async def transfer_sent(callback: CallbackQuery, bot: Bot) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])
    events_chat_id = settings.events_chat_id

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        if not user.is_active or user.role not in MASTER_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=ticket_id,
                payload={"reason": "TRANSFER_SENT"},
                ticket_id=ticket_id,
            )
            await callback.answer(f"Нет доступа. Ваша роль: {user.role.value}", show_alert=True)
            await session.commit()
            return

        ticket = await ticket_service.mark_transfer_sent(session, ticket_id, user.id)

        if not ticket:
            await session.rollback()
            await callback.answer("Нельзя отметить перевод: заказ не закрыт или перевод уже отмечен.", show_alert=True)
            return

        await session.commit()

    await callback.message.edit_text(format_ticket_card(ticket))
    await bot.send_message(events_chat_id, format_ticket_event_transfer(ticket))
    await callback.answer("Отметили перевод")


@router.message(F.text == "✅ Подтверждения")
async def transfer_confirmations(message: Message) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            message.from_user.id,
            message.from_user.full_name if message.from_user else None,
            message.from_user.username if message.from_user else None
        )
        await session.commit()
        if not user.is_active or user.role not in TRANSFER_CONFIRM_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=None,
                payload={"reason": "TRANSFER_CONFIRM_LIST"},
            )
            await session.commit()
            await message.answer("У вас нет доступа к подтверждениям.")
            return

        tickets = await ticket_service.list_transfer_pending(session)

    if not tickets:
        await message.answer("Нет переводов на подтверждение.")
        return

    for ticket in tickets:
        executor = ticket.assigned_executor.display_name if ticket.assigned_executor else None
        executor_label = executor or f"ID {ticket.assigned_executor_id}"
        net_profit = ticket.net_profit if ticket.net_profit is not None else "-"
        sent_at = ticket.transfer_sent_at.strftime("%Y-%m-%d %H:%M") if ticket.transfer_sent_at else "-"
        text = (
            f"Заказ #{ticket_display_id(ticket)}\n"
            f"Исполнитель: {executor_label}\n"
            f"Сумма к переводу: {net_profit}\n"
            f"Перевёл: {sent_at}"
        )
        await message.answer(text, reply_markup=transfer_approval_actions(ticket.id))


@router.callback_query(F.data.startswith("transfer_confirm:"))
async def transfer_confirm_prompt(callback: CallbackQuery) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])
    await callback.message.answer(
        "Вы уверены? Это действие нельзя отменить.",
        reply_markup=transfer_confirm_keyboard(ticket_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("transfer_confirm_yes:"))
async def transfer_confirm(callback: CallbackQuery, bot: Bot) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])
    events_chat_id = settings.events_chat_id

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        if not user.is_active or user.role not in TRANSFER_CONFIRM_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=ticket_id,
                payload={"reason": "TRANSFER_CONFIRM"},
                ticket_id=ticket_id,
            )
            await callback.answer(f"Нет доступа. Ваша роль: {user.role.value}", show_alert=True)
            await session.commit()
            return

        ticket = await ticket_service.confirm_transfer(session, ticket_id, user.id, approved=True)

        if not ticket:
            await session.rollback()
            await callback.answer("Нельзя подтвердить перевод", show_alert=True)
            return

        await session.commit()

    await callback.message.edit_text(format_ticket_card(ticket))
    await bot.send_message(events_chat_id, format_ticket_event_transfer(ticket))
    await callback.answer("Перевод подтвержден")


@router.callback_query(F.data.startswith("transfer_confirm_no:"))
async def transfer_confirm_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Подтверждение отменено")


@router.callback_query(F.data.startswith("transfer_reject:"))
async def transfer_reject(callback: CallbackQuery, bot: Bot) -> None:
    ticket_id = int(callback.data.split(":", 1)[1])
    events_chat_id = settings.events_chat_id

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        if not user.is_active or user.role not in TRANSFER_CONFIRM_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=ticket_id,
                payload={"reason": "TRANSFER_REJECT"},
                ticket_id=ticket_id,
            )
            await callback.answer(f"Нет доступа. Ваша роль: {user.role.value}", show_alert=True)
            await session.commit()
            return

        ticket = await ticket_service.confirm_transfer(session, ticket_id, user.id, approved=False)

        if not ticket:
            await session.rollback()
            await callback.answer("Нельзя отклонить перевод", show_alert=True)
            return

        await session.commit()

    await callback.message.edit_text(format_ticket_card(ticket))
    await bot.send_message(events_chat_id, format_ticket_event_transfer(ticket))
    await callback.answer("Перевод отклонен")


def _render_worker_closed_list(tickets, *, total: int, page: int, page_size: int) -> str:
    total_pages = max(1, ceil(total / page_size)) if total else 1
    header = f"Закрытые заявки (страница {page + 1}/{total_pages})"
    if not tickets:
        return f"{header}\nУ вас нет закрытых заказов."
    lines = [header]
    for ticket in tickets:
        closed_at = ticket.closed_at or ticket.updated_at
        date_value = closed_at.strftime("%d.%m.%Y") if closed_at else "-"
        client_label = ticket.client_name or "-"
        category = ticket_category_label(ticket.category)
        lines.append(f"#{ticket_display_id(ticket)} • {date_value} • {category} • {client_label}")
    return "\n".join(lines)


def _worker_closed_keyboard(tickets, *, total: int, page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, ceil(total / 12)) if total else 1
    return worker_closed_keyboard(
        ticket_buttons=[(ticket.id, ticket_display_id(ticket)) for ticket in tickets],
        page=page,
        total_pages=total_pages,
    )


def _parse_kv_payload(payload: str, *, prefix: str) -> dict[str, str]:
    raw = payload[len(prefix):]
    parts = [part for part in raw.split(":") if part]
    parsed: dict[str, str] = {}
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            parsed[key] = value
    return parsed
