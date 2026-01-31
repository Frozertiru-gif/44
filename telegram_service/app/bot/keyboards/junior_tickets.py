from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def junior_ticket_list_items(ticket_ids: list[int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Открыть #{ticket_id}", callback_data=f"junior_ticket:{ticket_id}")]
            for ticket_id in ticket_ids
        ]
    )
