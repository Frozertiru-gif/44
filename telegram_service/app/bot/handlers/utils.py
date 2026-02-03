from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from app.db.enums import LeadAdSource, LeadStatus, TicketStatus, ticket_category_label
from app.domain.enums_mapping import ad_source_label
from app.db.models import Lead, Ticket


LEAD_STATUS_LABELS = {
    LeadStatus.NEW_RAW: "Новая",
    LeadStatus.NEED_INFO: "Нужно уточнить",
    LeadStatus.CONVERTED: "Конвертировано",
    LeadStatus.SPAM: "Спам",
}
LEAD_AD_SOURCE_LABELS = {
    LeadAdSource.AVITO: "Авито",
    LeadAdSource.FLYER: "Листовка",
    LeadAdSource.BUSINESS_CARD: "Визитка",
    LeadAdSource.OTHER: "Другое",
    LeadAdSource.UNKNOWN: "Неизвестно",
}


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


def format_ticket_schedule(preferred_date_dm: str | None, scheduled_at: datetime | None) -> str:
    if scheduled_at:
        date_part = preferred_date_dm or scheduled_at.strftime("%d:%m")
        return f"{date_part} {scheduled_at.strftime('%H:%M')}"
    if preferred_date_dm:
        return preferred_date_dm
    return "Не указано"


def format_ticket_card(ticket: Ticket) -> str:
    repeat_label = "⚠️ ПОВТОР\n" if ticket.is_repeat else ""
    scheduled = format_ticket_schedule(ticket.preferred_date_dm, ticket.scheduled_at)
    client_line = "-"
    if ticket.client_name or ticket.client_age_estimate:
        name = ticket.client_name or "Не указано"
        age = ticket.client_age_estimate if ticket.client_age_estimate is not None else "?"
        client_line = f"{name} ({age})"
    note = ticket.special_note or "-"
    ad = ad_source_label(ticket.ad_source)
    executor = format_executor_label(ticket)
    junior_master = format_junior_master_label(ticket)
    transfer = format_transfer_label(ticket)
    finance = format_finance_block(ticket)
    return (
        f"{repeat_label}Заказ #{ticket.id}\n"
        f"Категория: {ticket_category_label(ticket.category)}\n"
        f"Телефон: {ticket.client_phone}\n"
        f"Адрес: {ticket.client_address or '-'}\n"
        f"Удобное время: {scheduled}\n"
        f"Клиент: {client_line}\n"
        f"Проблема: {ticket.problem_text}\n"
        f"Пометки: {note}\n"
        f"Реклама: {ad}\n"
        f"Статус: {ticket.status.value}"
        f"{executor}"
        f"{junior_master}"
        f"{finance}"
        f"{transfer}"
    )


def format_ticket_preview(data: dict) -> str:
    repeat_label = "⚠️ ПОВТОР\n" if data.get("is_repeat") else ""
    scheduled_at = data.get("scheduled_at")
    scheduled = format_ticket_schedule(data.get("preferred_date_dm"), scheduled_at)
    client_line = "-"
    if data.get("client_name") or data.get("client_age_estimate") is not None:
        name = data.get("client_name") or "Не указано"
        age = data.get("client_age_estimate") if data.get("client_age_estimate") is not None else "?"
        client_line = f"{name} ({age})"
    note = data.get("special_note") or "-"
    ad_source = data.get("ad_source")
    ad_value = ad_source_label(ad_source)
    repeat_ids = data.get("repeat_ticket_ids") or []
    repeat_info = f"\nПовторы: {', '.join(map(str, repeat_ids))}" if repeat_ids else ""
    return (
        f"{repeat_label}Новый заказ\n"
        f"Категория: {ticket_category_label(data.get('category'))}\n"
        f"Телефон: {data.get('client_phone')}\n"
        f"Адрес: {data.get('client_address') or '-'}\n"
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
        lines.append(f"#{ticket.id} {ticket_category_label(ticket.category)} {ticket.client_phone} {marker}{status}")
    return "\n".join(lines) if lines else "Нет заказов."


def format_lead_card(lead: Lead, *, repeat_count: int | None = None) -> str:
    lead_id_short = str(lead.id).split("-", maxsplit=1)[0]
    scheduled = lead.preferred_datetime.strftime("%Y-%m-%d %H:%M") if lead.preferred_datetime else "Не указано"
    ad_source = LEAD_AD_SOURCE_LABELS.get(lead.ad_source, "Неизвестно") if lead.ad_source else "-"
    status_label = LEAD_STATUS_LABELS.get(lead.status, lead.status.value)
    lines = [
        f"📥 Сырая заявка #{lead_id_short}",
        f"Телефон: {lead.client_phone or '-'}",
        f"Клиент: {lead.client_name or '-'}",
        f"Удобно: {scheduled}",
        f"Проблема: {lead.problem_text}",
        f"Реклама: {ad_source}",
        f"Пометка: {lead.special_note or '-'}",
        f"Статус: {status_label}",
    ]
    if lead.converted_ticket_id:
        lines.append(f"✅ Конвертировано в заказ #{lead.converted_ticket_id}")
    if repeat_count:
        lines.append(f"По телефону найдены прошлые заявки: {repeat_count}")
    return "\n".join(lines)


def format_executor_label(ticket: Ticket) -> str:
    if not ticket.assigned_executor_id:
        return ""
    executor_obj = ticket.__dict__.get("assigned_executor")
    executor = executor_obj.display_name if executor_obj else None
    executor_label = executor or f"ID {ticket.assigned_executor_id}"
    return f"\nИсполнитель: {executor_label}"


def format_transfer_label(ticket: Ticket) -> str:
    if not ticket.transfer_status:
        return ""
    return f"\nПеревод: {ticket.transfer_status.value}"


def format_junior_master_label(ticket: Ticket) -> str:
    if not ticket.junior_master_id:
        return ""
    junior_obj = ticket.__dict__.get("junior_master")
    junior_label = junior_obj.display_name if junior_obj else None
    junior_text = junior_label or f"ID {ticket.junior_master_id}"
    return f"\nМладший мастер: {junior_text}"


def format_finance_block(ticket: Ticket) -> str:
    if ticket.status != TicketStatus.CLOSED:
        return ""
    revenue = ticket.revenue if ticket.revenue is not None else "-"
    expense = ticket.expense if ticket.expense is not None else "-"
    profit = ticket.net_profit if ticket.net_profit is not None else "-"
    return f"\nДоход: {revenue}\nРасход: {expense}\nЧистая прибыль: {profit}"


def format_ticket_queue_card(ticket: Ticket) -> str:
    repeat_label = "⚠️ ПОВТОР\n" if ticket.is_repeat else ""
    scheduled = format_ticket_schedule(ticket.preferred_date_dm, ticket.scheduled_at)
    problem = ticket.problem_text.replace("\n", " ").strip()
    if len(problem) > 60:
        problem = f"{problem[:57]}..."
    return (
        f"{repeat_label}Заказ #{ticket.id}\n"
        f"Категория: {ticket_category_label(ticket.category)}\n"
        f"Телефон: {ticket.client_phone}\n"
        f"Адрес: {ticket.client_address or '-'}\n"
        f"Удобное время: {scheduled}\n"
        f"Проблема: {problem}"
    )


def format_active_ticket_card(ticket: Ticket) -> str:
    base = format_ticket_queue_card(ticket)
    return f"{base}\nСтатус: {ticket.status.value}"


def format_order_report(ticket: Ticket) -> str:
    executor_obj = ticket.__dict__.get("assigned_executor")
    executor = executor_obj.display_name if executor_obj else None
    executor_label = executor or (f"ID {ticket.assigned_executor_id}" if ticket.assigned_executor_id else "-")
    ad_source = ad_source_label(ticket.ad_source)
    revenue = ticket.revenue if ticket.revenue is not None else "-"
    expense = ticket.expense if ticket.expense is not None else "-"
    profit = ticket.net_profit if ticket.net_profit is not None else "-"
    return (
        f"Номер заказа: {ticket.id}\n"
        f"Кто выполнил: {executor_label}\n"
        f"Тип рекламы: {ad_source}\n"
        f"Скок отдал клиент: {revenue}\n"
        f"Расходы: {expense}\n"
        f"Чистый профит: {profit}"
    )
