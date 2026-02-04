from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def backup_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Статус", callback_data="backup:status")],
            [InlineKeyboardButton(text="▶ Сделать бэкап сейчас", callback_data="backup:run")],
            [InlineKeyboardButton(text="📤 Отправить в backup-чат", callback_data="backup:send")],
            [InlineKeyboardButton(text="♻ Восстановить последний", callback_data="backup:restore_prompt")],
            [InlineKeyboardButton(text="📥 Восстановить из файла", callback_data="backup:restore_file_prompt")],
        ]
    )


def backup_restore_confirm_keyboard(actor_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ДА, ВОССТАНОВИТЬ", callback_data=f"backup:restore_confirm:{actor_id}")],
            [InlineKeyboardButton(text="↩️ Отмена", callback_data="backup:restore_cancel")],
        ]
    )


def backup_restore_file_confirm_keyboard(actor_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ДА, ВОССТАНОВИТЬ", callback_data=f"backup:restore_file_confirm:{actor_id}")],
            [InlineKeyboardButton(text="↩️ Отмена", callback_data="backup:restore_cancel")],
        ]
    )
