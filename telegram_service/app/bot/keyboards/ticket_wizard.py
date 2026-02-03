from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.db.enums import AdSource, TicketCategory, ticket_category_label
from app.domain.enums_mapping import ad_source_label


async def category_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=ticket_category_label(TicketCategory.PC)),
                KeyboardButton(text=ticket_category_label(TicketCategory.TV)),
            ],
            [
                KeyboardButton(text=ticket_category_label(TicketCategory.PHONE)),
                KeyboardButton(text=ticket_category_label(TicketCategory.PRINTER)),
            ],
            [KeyboardButton(text=ticket_category_label(TicketCategory.OTHER))],
        ],
        resize_keyboard=True,
    )


async def repeat_warning_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➡️ Продолжить", callback_data="repeat_continue")]])


async def schedule_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Сегодня"), KeyboardButton(text="Завтра")]],
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
            [KeyboardButton(text=ad_source_label(AdSource.AVITO)), KeyboardButton(text=ad_source_label(AdSource.LEAFLET))],
            [KeyboardButton(text=ad_source_label(AdSource.BUSINESS_CARD)), KeyboardButton(text=ad_source_label(AdSource.OTHER))],
            [KeyboardButton(text=ad_source_label(AdSource.UNKNOWN))],
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
