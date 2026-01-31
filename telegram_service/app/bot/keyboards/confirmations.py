from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def confirm_action_keyboard(confirm_data: str, cancel_data: str = "confirm_cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_data)],
            [InlineKeyboardButton(text="↩️ Отмена", callback_data=cancel_data)],
        ]
    )
