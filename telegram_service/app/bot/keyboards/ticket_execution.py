from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def queue_ticket_actions(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Принять", callback_data=f"queue_take:{ticket_id}")]]
    )


def active_ticket_actions(
    ticket_id: int,
    *,
    show_in_progress: bool,
    show_close: bool,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    if show_in_progress:
        buttons.append([InlineKeyboardButton(text="🛠 В работе", callback_data=f"status_progress:{ticket_id}")])
    if show_close:
        buttons.append([InlineKeyboardButton(text="✅ Закрыть", callback_data=f"close_start:{ticket_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def closed_ticket_actions(ticket_id: int, *, allow_transfer: bool) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    if allow_transfer:
        buttons.append([InlineKeyboardButton(text="📤 Я перевёл", callback_data=f"transfer_sent:{ticket_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def close_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💾 Подтвердить закрытие", callback_data="close_confirm")],
            [InlineKeyboardButton(text="↩️ Изменить суммы", callback_data="close_edit")],
        ]
    )


def transfer_approval_actions(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"transfer_confirm:{ticket_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"transfer_reject:{ticket_id}")],
        ]
    )
