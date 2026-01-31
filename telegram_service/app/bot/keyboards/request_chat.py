from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


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
