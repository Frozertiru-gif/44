from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.db.enums import AdSource, TicketCategory


async def category_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TicketCategory.PC.value), KeyboardButton(text=TicketCategory.TV.value)],
            [KeyboardButton(text=TicketCategory.PHONE.value), KeyboardButton(text=TicketCategory.PRINTER.value)],
            [KeyboardButton(text=TicketCategory.OTHER.value)],
        ],
        resize_keyboard=True,
    )


async def repeat_warning_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➡️ Продолжить", callback_data="repeat_continue")]])


async def schedule_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Сегодня"), KeyboardButton(text="Завтра"), KeyboardButton(text="Пропустить")]],
        resize_keyboard=True,
    )


async def name_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Пропустить")]], resize_keyboard=True)


async def age_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Не знаю"), KeyboardButton(text="Пропустить")]], resize_keyboard=True)


async def special_note_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Гарантия"), KeyboardButton(text="Повторный выезд")],
            [KeyboardButton(text="Срочно"), KeyboardButton(text="Другое")],
            [KeyboardButton(text="Нет")],
        ],
        resize_keyboard=True,
    )


async def ad_source_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=AdSource.AVITO.value), KeyboardButton(text=AdSource.FLYER.value)],
            [KeyboardButton(text=AdSource.CARD.value), KeyboardButton(text=AdSource.OTHER.value)],
            [KeyboardButton(text=AdSource.UNKNOWN.value)],
        ],
        resize_keyboard=True,
    )


async def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать", callback_data="ticket_confirm"),
                InlineKeyboardButton(text="✏️ Отмена", callback_data="ticket_cancel"),
            ]
        ]
    )
