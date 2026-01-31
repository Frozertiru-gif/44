from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.enums import UserRole


def user_list_keyboard(user_ids: list[int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Пользователь {user_id}", callback_data=f"user:{user_id}")]
            for user_id in user_ids
        ]
    )


def user_role_keyboard(user_id: int) -> InlineKeyboardMarkup:
    roles = [
        UserRole.ADMIN,
        UserRole.JUNIOR_ADMIN,
        UserRole.MASTER,
        UserRole.JUNIOR_MASTER,
        UserRole.SUPER_ADMIN,
        UserRole.SYS_ADMIN,
    ]
    rows = []
    for role in roles:
        rows.append([InlineKeyboardButton(text=role.value, callback_data=f"role:{user_id}:{role.value}")])
    rows.append([InlineKeyboardButton(text="🔒 Выключить", callback_data=f"user_disable:{user_id}")])
    rows.append([InlineKeyboardButton(text="🔓 Включить", callback_data=f"user_enable:{user_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
