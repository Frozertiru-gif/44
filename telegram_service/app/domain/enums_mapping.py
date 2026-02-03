from __future__ import annotations

import logging

from app.db.enums import AdSource, TICKET_CATEGORY_LABELS, TicketCategory

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

CATEGORY_TEXT_TO_CODE: dict[str, TicketCategory] = {
    **{_normalize_token(category.value): category for category in TicketCategory},
    **{_normalize_token(label): category for category, label in TICKET_CATEGORY_LABELS.items()},
    **{_normalize_token(alias): category for alias, category in _CATEGORY_ALIASES.items()},
}

AD_SOURCE_LABELS: dict[AdSource, str] = {
    AdSource.AVITO: "Авито",
    AdSource.LEAFLET: "Листовка",
    AdSource.BUSINESS_CARD: "Визитка",
    AdSource.OTHER: "Другое",
    AdSource.UNKNOWN: "Неизвестно",
}

_AD_SOURCE_ALIASES: dict[str, AdSource] = {
    "avito": AdSource.AVITO,
    "авито": AdSource.AVITO,
    "leaflet": AdSource.LEAFLET,
    "flyer": AdSource.LEAFLET,
    "листовка": AdSource.LEAFLET,
    "businesscard": AdSource.BUSINESS_CARD,
    "business_card": AdSource.BUSINESS_CARD,
    "card": AdSource.BUSINESS_CARD,
    "визитка": AdSource.BUSINESS_CARD,
    "other": AdSource.OTHER,
    "другое": AdSource.OTHER,
    "unknown": AdSource.UNKNOWN,
    "неизвестно": AdSource.UNKNOWN,
}

AD_SOURCE_TEXT_TO_CODE: dict[str, AdSource] = {
    **{_normalize_token(source.value): source for source in AdSource},
    **{_normalize_token(label): source for source, label in AD_SOURCE_LABELS.items()},
    **{_normalize_token(alias): source for alias, source in _AD_SOURCE_ALIASES.items()},
}


def parse_ticket_category(value: TicketCategory | str | None) -> TicketCategory:
    if isinstance(value, TicketCategory):
        return value
    token = _normalize_token(str(value or ""))
    if not token:
        return TicketCategory.OTHER
    category = CATEGORY_TEXT_TO_CODE.get(token)
    if not category:
        logger.warning("Unknown ticket category: %s", value)
        return TicketCategory.OTHER
    return category


def parse_ad_source(value: AdSource | str | None) -> AdSource:
    if isinstance(value, AdSource):
        return value
    token = _normalize_token(str(value or ""))
    if not token:
        return AdSource.UNKNOWN
    source = AD_SOURCE_TEXT_TO_CODE.get(token)
    if not source:
        logger.warning("Unknown ad source: %s", value)
        return AdSource.UNKNOWN
    return source


def ad_source_label(source: AdSource | None) -> str:
    if source is None:
        return "-"
    return AD_SOURCE_LABELS.get(source, source.value)
