from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import MasterJuniorLink, User


def master_select_keyboard(masters: list[User]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=master.display_name or f"ID {master.id}", callback_data=f"link_master:{master.id}")]
            for master in masters
        ]
    )


def junior_select_keyboard(juniors: list[User], *, prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=junior.display_name or f"ID {junior.id}", callback_data=f"{prefix}:{junior.id}"
                )
            ]
            for junior in juniors
        ]
    )


def master_links_keyboard(
    master_id: int,
    links: list[MasterJuniorLink],
    *,
    allow_manage: bool,
    allow_percent: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if allow_manage:
        rows.append([InlineKeyboardButton(text="➕ Привязать младшего мастера", callback_data=f"link_add:{master_id}")])
    for link in links:
        junior = link.junior_master
        junior_label = junior.display_name if junior else f"ID {link.junior_master_id}"
        if allow_percent:
            rows.append(
                [InlineKeyboardButton(text=f"✏️ % для {junior_label}", callback_data=f"link_percent:{link.id}")]
            )
        if allow_manage:
            rows.append(
                [InlineKeyboardButton(text=f"🔁 Перепривязать {junior_label}", callback_data=f"link_relink:{link.id}")]
            )
            rows.append([InlineKeyboardButton(text=f"⛔️ Отвязать {junior_label}", callback_data=f"link_disable:{link.id}")])
    if allow_manage:
        rows.append([InlineKeyboardButton(text="⬅️ Назад к мастерам", callback_data="link_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def relink_master_keyboard(masters: list[User]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=master.display_name or f"ID {master.id}", callback_data=f"relink_master:{master.id}")]
            for master in masters
        ]
    )
