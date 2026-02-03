from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.enums import UserRole


def user_list_keyboard(users: list[tuple[int, str | None]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_format_user_label(user_id, username),
                    callback_data=f"user:{user_id}",
                )
            ]
            for user_id, username in users
        ]
    )


def _format_user_label(user_id: int, username: str | None) -> str:
    if username:
        return f"Пользователь {user_id} (@{username})"
    return f"Пользователь {user_id}"


def user_role_keyboard(user_id: int) -> InlineKeyboardMarkup:
    roles = [
        UserRole.USER,
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
    rows.append([InlineKeyboardButton(text="💼 % мастера", callback_data=f"user_percent:master:{user_id}")])
    rows.append([InlineKeyboardButton(text="💼 % админа", callback_data=f"user_percent:admin:{user_id}")])
    rows.append([InlineKeyboardButton(text="🔒 Выключить", callback_data=f"user_disable:{user_id}")])
    rows.append([InlineKeyboardButton(text="🔓 Включить", callback_data=f"user_enable:{user_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
