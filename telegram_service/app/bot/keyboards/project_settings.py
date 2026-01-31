from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def project_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="requests_chat_id", callback_data="settings_field:requests_chat_id")],
            [InlineKeyboardButton(text="currency", callback_data="settings_field:currency")],
            [InlineKeyboardButton(text="rounding_mode", callback_data="settings_field:rounding_mode")],
            [InlineKeyboardButton(text="thresholds", callback_data="settings_field:thresholds")],
        ]
    )
