from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from app.db.enums import AdSource, TicketCategory, TicketStatus
from app.db.models import Ticket


CATEGORY_MAP = {item.value: item for item in TicketCategory}
ADSOURCE_MAP = {item.value: item for item in AdSource}


def normalize_phone(raw: str) -> str:
    digits = "".join(char for char in raw if char.isdigit())
    if raw.strip().startswith("+"):
        return f"+{digits}"
    return digits


def is_valid_phone(phone: str) -> bool:
    digits = phone.lstrip("+")
    return digits.isdigit() and 7 <= len(digits) <= 15


def parse_time(value: str, target_date: date) -> datetime | None:
    try:
        hours, minutes = value.split(":")
        hour = int(hours)
        minute = int(minutes)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return datetime.combine(target_date, datetime.min.time()).replace(hour=hour, minute=minute)
    except ValueError:
        return None


def format_ticket_card(ticket: Ticket) -> str:
    repeat_label = "⚠️ ПОВТОР\n" if ticket.is_repeat else ""
    scheduled = ticket.scheduled_at.strftime("%Y-%m-%d %H:%M") if ticket.scheduled_at else "Не указано"
    client_line = "-"
    if ticket.client_name or ticket.client_age_estimate:
        name = ticket.client_name or "Не указано"
        age = ticket.client_age_estimate if ticket.client_age_estimate is not None else "?"
        client_line = f"{name} ({age})"
    note = ticket.special_note or "-"
    ad = ticket.ad_source.value if ticket.ad_source else "-"
    return (
        f"{repeat_label}Заказ #{ticket.id}\n"
        f"Категория: {ticket.category.value}\n"
        f"Телефон: {ticket.client_phone}\n"
        f"Удобное время: {scheduled}\n"
        f"Клиент: {client_line}\n"
        f"Проблема: {ticket.problem_text}\n"
        f"Пометки: {note}\n"
        f"Реклама: {ad}\n"
        f"Статус: {ticket.status.value}"
    )


def format_ticket_preview(data: dict) -> str:
    repeat_label = "⚠️ ПОВТОР\n" if data.get("is_repeat") else ""
    scheduled_at = data.get("scheduled_at")
    scheduled = scheduled_at.strftime("%Y-%m-%d %H:%M") if scheduled_at else "Не указано"
    client_line = "-"
    if data.get("client_name") or data.get("client_age_estimate") is not None:
        name = data.get("client_name") or "Не указано"
        age = data.get("client_age_estimate") if data.get("client_age_estimate") is not None else "?"
        client_line = f"{name} ({age})"
    note = data.get("special_note") or "-"
    ad_source = data.get("ad_source")
    ad_value = ad_source.value if ad_source else "-"
    repeat_ids = data.get("repeat_ticket_ids") or []
    repeat_info = f"\nПовторы: {', '.join(map(str, repeat_ids))}" if repeat_ids else ""
    return (
        f"{repeat_label}Новый заказ\n"
        f"Категория: {data.get('category').value}\n"
        f"Телефон: {data.get('client_phone')}\n"
        f"Удобное время: {scheduled}\n"
        f"Клиент: {client_line}\n"
        f"Проблема: {data.get('problem_text')}\n"
        f"Пометки: {note}\n"
        f"Реклама: {ad_value}"
        f"{repeat_info}"
    )


def format_ticket_list(tickets: Iterable[Ticket]) -> str:
    lines = []
    for ticket in tickets:
        marker = "⚠️" if ticket.is_repeat else ""
        status = "" if ticket.status == TicketStatus.READY_FOR_WORK else f" ({ticket.status.value})"
        lines.append(f"#{ticket.id} {ticket.category.value} {ticket.client_phone} {marker}{status}")
    return "\n".join(lines) if lines else "Нет заказов."
