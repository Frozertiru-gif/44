from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def period_keyboard(prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Этот месяц", callback_data=f"{prefix}:this_month"),
            InlineKeyboardButton(text="Прошлый месяц", callback_data=f"{prefix}:last_month"),
        ],
        [
            InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}:last_7"),
            InlineKeyboardButton(text="Все время", callback_data=f"{prefix}:all_time"),
        ],
        [InlineKeyboardButton(text="Произвольно", callback_data=f"{prefix}:custom")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def share_list_keyboard(entries: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"share_pick:{user_id}")]
            for user_id, label in entries
        ]
    )
