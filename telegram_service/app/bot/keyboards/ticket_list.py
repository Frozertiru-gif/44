from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def ticket_list_filters() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Все", callback_data="list:all"),
                InlineKeyboardButton(text="Активные", callback_data="list:active"),
                InlineKeyboardButton(text="Повторы", callback_data="list:repeat"),
            ]
        ]
    )


def ticket_list_items(ticket_ids: list[int]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"Открыть #{ticket_id}", callback_data=f"ticket:{ticket_id}")]
        for ticket_id in ticket_ids
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def ticket_actions(ticket_id: int, can_cancel: bool) -> InlineKeyboardMarkup:
    buttons = []
    if can_cancel:
        buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data=f"ticket_cancel:{ticket_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else InlineKeyboardMarkup(inline_keyboard=[])
