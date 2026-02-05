from __future__ import annotations

import re
from datetime import date, timedelta
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.permissions import CREATE_ROLES
from app.bot.handlers.utils import (
    format_lead_card,
    format_ticket_card,
    format_ticket_public,
    format_ticket_preview,
    is_valid_phone,
    normalize_phone,
    parse_time,
    ticket_display_id,
)
from app.bot.keyboards.main_menu import build_main_menu
from app.bot.keyboards.request_chat import request_chat_keyboard
from app.bot.keyboards.ticket_wizard import (
    ad_source_keyboard,
    age_keyboard,
    category_keyboard,
    address_details_keyboard,
    confirm_keyboard,
    name_keyboard,
    repeat_warning_keyboard,
    schedule_keyboard,
    special_note_keyboard,
)
from app.bot.states.ticket_create import TicketCreateStates
from app.core.config import get_settings
from app.db.enums import AdSource, LeadStatus
from app.db.session import async_session_factory
from app.services.audit_service import AuditService
from app.domain.enums_mapping import parse_ad_source, parse_ticket_category
from app.services.lead_service import LeadService
from app.services.project_settings_service import ProjectSettingsService
from app.services.ticket_service import TicketService
from app.services.user_service import UserService

router = Router()
settings = get_settings()
user_service = UserService()
ticket_service = TicketService()
audit_service = AuditService()
project_settings_service = ProjectSettingsService()
lead_service = LeadService()


def _is_value_set(data: dict, key: str) -> bool:
    return key in data and data[key] not in (None, "")


async def _advance_after_schedule(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("scheduled_at") is None and not _is_value_set(data, "preferred_date_dm"):
        await state.set_state(TicketCreateStates.schedule_choice)
        await message.answer("Удобная дата?", reply_markup=await schedule_keyboard())
        return
    if not _is_value_set(data, "client_name"):
        await state.set_state(TicketCreateStates.client_name)
        await message.answer("Имя клиента:", reply_markup=await name_keyboard())
        return
    if data.get("client_age_estimate") is None:
        await state.set_state(TicketCreateStates.client_age)
        await message.answer("Возраст (примерно):", reply_markup=await age_keyboard())
        return
    if not _is_value_set(data, "problem_text"):
        await state.set_state(TicketCreateStates.problem)
        await message.answer("Опишите проблему:")
        return
    if not _is_value_set(data, "special_note"):
        await state.set_state(TicketCreateStates.special_note)
        await message.answer("Спецпометка:", reply_markup=await special_note_keyboard())
        return
    if not _is_value_set(data, "ad_source"):
        await state.set_state(TicketCreateStates.ad_source)
        await message.answer("Источник рекламы:", reply_markup=await ad_source_keyboard())
        return
    await state.set_state(TicketCreateStates.confirm)
    data = await state.get_data()
    await message.answer(format_ticket_preview(data), reply_markup=await confirm_keyboard())


async def _advance_after_phone(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not _is_value_set(data, "client_address"):
        await state.set_state(TicketCreateStates.client_address)
        await message.answer("Введите адрес клиента:")
        return
    if "address_details" not in data:
        await state.set_state(TicketCreateStates.address_details)
        await message.answer(
            'Введите "квартира / подъезд / этаж" (можно одной строкой). Например: "кв 12, подъезд 2, этаж 5".',
            reply_markup=await address_details_keyboard(),
        )
        return
    if data.get("scheduled_at") is None and not _is_value_set(data, "preferred_date_dm"):
        await state.set_state(TicketCreateStates.schedule_choice)
        await message.answer("Удобная дата?", reply_markup=await schedule_keyboard())
        return
    await _advance_after_schedule(message, state)


@router.message(F.text == "➕ Создать заказ")
async def start_ticket_creation(message: Message, state: FSMContext) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            message.from_user.id,
            message.from_user.full_name if message.from_user else None,
            message.from_user.username if message.from_user else None
        )
        await session.commit()

    if not user.is_active or user.role not in CREATE_ROLES:
        await message.answer("Нет доступа. Обратитесь к администратору.")
        return

    await state.clear()
    await state.set_state(TicketCreateStates.category)
    await message.answer("Выберите категорию:", reply_markup=await category_keyboard())


@router.message(TicketCreateStates.category)
async def ticket_category(message: Message, state: FSMContext) -> None:
    category = parse_ticket_category(message.text or "")
    await state.update_data(category=category)
    data = await state.get_data()
    if data.get("client_phone"):
        async with async_session_factory() as session:
            repeats = await ticket_service.search_by_phone(session, data["client_phone"])
        repeat_ids = [ticket.id for ticket in repeats]
        is_repeat = len(repeat_ids) > 0
        await state.update_data(client_phone=data["client_phone"], is_repeat=is_repeat, repeat_ticket_ids=repeat_ids)
        if is_repeat:
            await state.set_state(TicketCreateStates.repeat_confirm)
            await message.answer(
                f"⚠️ Повторный клиент: ранее были #{', #'.join(map(str, repeat_ids))}",
                reply_markup=await repeat_warning_keyboard(),
            )
            return
        await _advance_after_phone(message, state)
        return

    await state.set_state(TicketCreateStates.phone)
    await message.answer("Введите телефон клиента:")


@router.message(TicketCreateStates.phone)
async def ticket_phone(message: Message, state: FSMContext) -> None:
    raw_phone = message.text or ""
    phone = normalize_phone(raw_phone)
    if not is_valid_phone(phone):
        await message.answer("Введите корректный телефон.")
        return

    async with async_session_factory() as session:
        repeats = await ticket_service.search_by_phone(session, phone)

    repeat_ids = [ticket.id for ticket in repeats]
    is_repeat = len(repeat_ids) > 0

    await state.update_data(client_phone=phone, is_repeat=is_repeat, repeat_ticket_ids=repeat_ids)
    if is_repeat:
        await state.set_state(TicketCreateStates.repeat_confirm)
        await message.answer(
            f"⚠️ Повторный клиент: ранее были #{', #'.join(map(str, repeat_ids))}",
            reply_markup=await repeat_warning_keyboard(),
        )
        return

    await _advance_after_phone(message, state)


@router.message(TicketCreateStates.client_address)
async def ticket_client_address(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("Введите адрес клиента (не менее 5 символов).")
        return
    await state.update_data(client_address=text)
    await _advance_after_phone(message, state)


@router.message(TicketCreateStates.address_details)
async def ticket_address_details(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    details = None if text in {"Пропустить", "-"} else text
    if details is not None and len(details) < 2:
        await message.answer('Введите минимум 2 символа или нажмите "Пропустить".')
        return

    await state.update_data(address_details=details)
    await _advance_after_phone(message, state)


@router.callback_query(F.data == "repeat_continue")
async def repeat_continue(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _advance_after_phone(callback.message, state)


@router.message(TicketCreateStates.schedule_choice)
async def ticket_schedule_choice(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if text == "Пропустить":
        await message.answer("Дата обязательна.")
        return

    if text in {"Сегодня", "Завтра"}:
        target_date = date.today() if text == "Сегодня" else date.today() + timedelta(days=1)
        preferred_date_dm = target_date.strftime("%d.%m")
    else:
        match = re.fullmatch(r"\d{2}\.\d{2}", text.strip())
        if not match:
            await message.answer("Введите дату в формате дд.мм (например 09.02).")
            return
        day, month = map(int, text.split(".", maxsplit=1))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            await message.answer("Введите дату в формате дд.мм (например 09.02).")
            return
        try:
            target_date = date(date.today().year, month, day)
        except ValueError:
            await message.answer("Введите дату в формате дд.мм (например 09.02).")
            return
        preferred_date_dm = text.strip()

    await state.update_data(schedule_date=target_date)
    await state.update_data(preferred_date_dm=preferred_date_dm)
    await state.set_state(TicketCreateStates.schedule_time)
    await message.answer("Введите время (HH:MM):")


@router.message(TicketCreateStates.schedule_time)
async def ticket_schedule_time(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    target_date = data.get("schedule_date")
    if not isinstance(target_date, date):
        await state.set_state(TicketCreateStates.schedule_choice)
        await message.answer("Удобная дата?", reply_markup=await schedule_keyboard())
        return

    schedule = parse_time(message.text or "", target_date)
    if not schedule:
        await message.answer("Введите время в формате HH:MM.")
        return

    await state.update_data(scheduled_at=schedule)
    if not _is_value_set(data, "preferred_date_dm"):
        await state.update_data(preferred_date_dm=schedule.strftime("%d.%m"))
    await _advance_after_schedule(message, state)


@router.message(TicketCreateStates.client_name)
async def ticket_client_name(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    name = None if text == "Пропустить" else text
    await state.update_data(client_name=name)
    await state.set_state(TicketCreateStates.client_age)
    await message.answer("Возраст (примерно):", reply_markup=await age_keyboard())


@router.message(TicketCreateStates.client_age)
async def ticket_client_age(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if text in {"Пропустить", "Не знаю"}:
        age = None
    else:
        try:
            age = int(text)
        except ValueError:
            await message.answer("Введите число или выберите 'Не знаю'.")
            return

    await state.update_data(client_age_estimate=age)
    await state.set_state(TicketCreateStates.problem)
    await message.answer("Опишите проблему:")


@router.message(TicketCreateStates.problem)
async def ticket_problem(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if not text.strip():
        await message.answer("Проблема обязательна.")
        return

    await state.update_data(problem_text=text)
    await state.set_state(TicketCreateStates.special_note)
    await message.answer("Спецпометка:", reply_markup=await special_note_keyboard())


@router.message(TicketCreateStates.special_note)
async def ticket_special_note(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if text == "Другое":
        await state.set_state(TicketCreateStates.special_note_custom)
        await message.answer("Введите спецпометку:")
        return

    if text == "Нет":
        note = None
    else:
        note = text
    await state.update_data(special_note=note)
    await state.set_state(TicketCreateStates.ad_source)
    await message.answer("Источник рекламы:", reply_markup=await ad_source_keyboard())


@router.message(TicketCreateStates.special_note_custom)
async def ticket_special_note_custom(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if not text.strip():
        await message.answer("Введите спецпометку.")
        return
    await state.update_data(special_note=text)
    await state.set_state(TicketCreateStates.ad_source)
    await message.answer("Источник рекламы:", reply_markup=await ad_source_keyboard())


@router.message(TicketCreateStates.ad_source)
async def ticket_ad_source(message: Message, state: FSMContext) -> None:
    source = parse_ad_source(message.text or "")
    await state.update_data(ad_source=source)
    await state.set_state(TicketCreateStates.confirm)
    data = await state.get_data()
    await message.answer(format_ticket_preview(data), reply_markup=await confirm_keyboard())


@router.callback_query(F.data == "ticket_confirm")
async def ticket_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    preferred_date_dm = data.get("preferred_date_dm")
    scheduled_at = data.get("scheduled_at")
    client_address = data.get("client_address")
    if not client_address:
        await callback.answer("Укажите адрес клиента.", show_alert=True)
        return
    if not scheduled_at and not preferred_date_dm:
        await callback.answer("Укажите удобную дату.", show_alert=True)
        return
    if scheduled_at and not preferred_date_dm:
        preferred_date_dm = scheduled_at.strftime("%d.%m")
    lead_id = data.get("lead_id")
    lead_message_chat_id = data.get("lead_message_chat_id")
    lead_message_id = data.get("lead_message_id")

    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None
        )
        if not user.is_active or user.role not in CREATE_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="ticket",
                entity_id=None,
                payload={"reason": "CREATE_TICKET"},
            )
            await session.commit()
            await callback.answer("Нет прав", show_alert=True)
            return

        lead = None
        if lead_id:
            lead = await lead_service.get_lead_for_update(session, UUID(str(lead_id)))
            if not lead:
                await callback.answer("Сырая заявка не найдена", show_alert=True)
                await state.clear()
                return
            if lead.status in {LeadStatus.CONVERTED, LeadStatus.SPAM}:
                await callback.answer("Заявка уже обработана", show_alert=True)
                await state.clear()
                return

        ticket = await ticket_service.create_ticket(
            session,
            category=data["category"],
            scheduled_at=scheduled_at,
            preferred_date_dm=preferred_date_dm,
            client_name=data.get("client_name"),
            client_age_estimate=data.get("client_age_estimate"),
            client_phone=data["client_phone"],
            client_address=client_address,
            address_details=data.get("address_details"),
            problem_text=data["problem_text"],
            special_note=data.get("special_note"),
            ad_source=data.get("ad_source", AdSource.UNKNOWN),
            created_by_admin_id=user.id,
            is_repeat=data.get("is_repeat", False),
            repeat_ticket_ids=data.get("repeat_ticket_ids"),
        )
        if not ticket:
            await callback.answer("Не удалось создать заказ", show_alert=True)
            await session.commit()
            return
        await audit_service.log_event(
            session,
            ticket_id=ticket.id,
            action="TICKET_CREATED",
            actor_id=user.id,
            payload={
                "before": None,
                "after": {
                    "status": ticket.status.value,
                    "category": ticket.category.value,
                    "client_phone": ticket.client_phone,
                },
            },
        )

        if lead:
            await lead_service.convert_to_ticket(session, lead=lead, ticket_id=ticket.id, actor_id=user.id)
        await session.commit()

    bot_info = await bot.get_me()
    async with async_session_factory() as session:
        requests_chat_id = await project_settings_service.get_requests_chat_id(session, settings.requests_chat_id)
    await bot.send_message(
        requests_chat_id,
        format_ticket_public(ticket),
        reply_markup=request_chat_keyboard(ticket, bot_info.username),
    )

    if lead and lead_message_chat_id and lead_message_id:
        await bot.edit_message_text(
            format_lead_card(lead),
            chat_id=lead_message_chat_id,
            message_id=lead_message_id,
            reply_markup=None,
        )

    await callback.message.answer(f"Заказ #{ticket_display_id(ticket)} создан.", reply_markup=await build_main_menu(user.role))
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "ticket_cancel")
async def ticket_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Создание заказа отменено.")
    await callback.answer()
