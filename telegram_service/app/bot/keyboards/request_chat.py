from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.handlers.utils import format_executor_link
from app.db.enums import TicketStatus
from app.db.models import Ticket, User


def request_chat_keyboard(ticket: Ticket, bot_username: str) -> InlineKeyboardMarkup:
    deep_link = f"https://t.me/{bot_username}?start=ticket_{ticket.id}"
    buttons = [
        [InlineKeyboardButton(text="👀 Открыть в боте", url=deep_link)],
    ]
    action_row = [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{ticket.id}")]
    if ticket.status == TicketStatus.READY_FOR_WORK and ticket.assigned_executor_id is None:
        action_row.append(InlineKeyboardButton(text="✅ Принять заказ", callback_data=f"request_take:{ticket.id}"))
    if action_row:
        buttons.append(action_row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def lead_request_keyboard(lead_id: UUID) -> InlineKeyboardMarkup:
    lead_id_str = str(lead_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Оформить", callback_data=f"lead:convert:{lead_id_str}")],
            [
                InlineKeyboardButton(text="❓ Уточнить", callback_data=f"lead:need_info:{lead_id_str}"),
                InlineKeyboardButton(text="🗑 Спам", callback_data=f"lead:spam:{lead_id_str}"),
            ],
        ]
    )


def executor_only_keyboard(executor: User | None) -> InlineKeyboardMarkup | None:
    label, url = format_executor_link(executor)
    if not url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f"👤 Исполнитель: {label}", url=url)]],
    )
