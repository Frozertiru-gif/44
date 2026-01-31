from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.db.enums import UserRole


ROLE_CREATE = {
    UserRole.SYS_ADMIN,
    UserRole.SUPER_ADMIN,
    UserRole.ADMIN,
    UserRole.JUNIOR_ADMIN,
}


async def build_main_menu(role: UserRole) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    if role in ROLE_CREATE:
        rows.append([KeyboardButton(text="➕ Создать заказ")])
        rows.append([KeyboardButton(text="📋 Список заказов")])
    if role in {UserRole.SYS_ADMIN, UserRole.SUPER_ADMIN}:
        rows.append([KeyboardButton(text="👥 Пользователи")])
    rows.append([KeyboardButton(text="ℹ️ Помощь")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
