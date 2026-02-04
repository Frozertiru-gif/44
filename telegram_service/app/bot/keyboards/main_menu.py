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
    if role in {UserRole.MASTER, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN}:
        rows.append([KeyboardButton(text="🧾 Очередь")])
        rows.append([KeyboardButton(text="🔥 Мои активные")])
        rows.append([KeyboardButton(text="📦 Мои закрытые")])
        rows.append([KeyboardButton(text="💰 Мои деньги")])
    if role in {UserRole.JUNIOR_MASTER}:
        rows.append([KeyboardButton(text="📋 Заявки моего мастера")])
        rows.append([KeyboardButton(text="💵 Моя зарплата")])
    if role in {UserRole.ADMIN}:
        rows.append([KeyboardButton(text="💵 Моя зарплата")])
    if role in {UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN}:
        rows.append([KeyboardButton(text="➕ Добавить доход")])
        rows.append([KeyboardButton(text="➖ Добавить расход")])
    if role in {UserRole.SYS_ADMIN, UserRole.SUPER_ADMIN}:
        rows.append([KeyboardButton(text="👥 Пользователи")])
        rows.append([KeyboardButton(text="✅ Подтверждения")])
        rows.append([KeyboardButton(text="📊 Сводка проекта")])
        rows.append([KeyboardButton(text="📌 Доли от кассы")])
        rows.append([KeyboardButton(text="⬇️ Экспорт Excel")])
        rows.append([KeyboardButton(text="📍 Проблемы")])
        rows.append([KeyboardButton(text="⚙️ Настройки проекта")])
        rows.append([KeyboardButton(text="🛡 Резервные копии")])
    if role in {UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN, UserRole.MASTER}:
        rows.append([KeyboardButton(text="👥 Привязки младших мастеров")])
    rows.append([KeyboardButton(text="ℹ️ Помощь")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
