from __future__ import annotations

import logging

from app.db.enums import TicketCategory

logger = logging.getLogger(__name__)


def _normalize_token(value: str) -> str:
    return "".join(value.split()).casefold()


_CATEGORY_ALIASES: dict[str, TicketCategory] = {
    "pc": TicketCategory.PC,
    "пк": TicketCategory.PC,
    "computer": TicketCategory.PC,
    "компьютер": TicketCategory.PC,
    "tv": TicketCategory.TV,
    "телевизор": TicketCategory.TV,
    "phone": TicketCategory.PHONE,
    "telephone": TicketCategory.PHONE,
    "printer": TicketCategory.PRINTER,
    "other": TicketCategory.OTHER,
}

_CATEGORY_NORMALIZATION_MAP: dict[str, TicketCategory] = {
    **{_normalize_token(category.value): category for category in TicketCategory},
    **{_normalize_token(alias): category for alias, category in _CATEGORY_ALIASES.items()},
}


def normalize_ticket_category(value: TicketCategory | str | None) -> TicketCategory | None:
    if value is None:
        return None
    if isinstance(value, TicketCategory):
        return value
    token = _normalize_token(value)
    if not token:
        return None
    category = _CATEGORY_NORMALIZATION_MAP.get(token)
    if not category:
        logger.warning("Unknown ticket category: %s", value)
    return category
