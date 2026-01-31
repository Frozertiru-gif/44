from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from uuid import UUID


def request_chat_keyboard(ticket_id: int, bot_username: str) -> InlineKeyboardMarkup:
    deep_link = f"https://t.me/{bot_username}?start=ticket_{ticket_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👀 Открыть в боте", url=deep_link)],
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{ticket_id}"),
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel:{ticket_id}"),
            ],
        ]
    )


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
