from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    SYS_ADMIN = "SYS_ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    JUNIOR_ADMIN = "JUNIOR_ADMIN"
    MASTER = "MASTER"
    JUNIOR_MASTER = "JUNIOR_MASTER"


class TicketStatus(str, Enum):
    READY_FOR_WORK = "READY_FOR_WORK"
    IN_WORK = "IN_WORK"
    TAKEN = "TAKEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING = "WAITING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class TicketCategory(str, Enum):
    PC = "PC"
    TV = "TV"
    PHONE = "PHONE"
    PRINTER = "PRINTER"
    OTHER = "OTHER"


TICKET_CATEGORY_LABELS: dict[TicketCategory, str] = {
    TicketCategory.PC: "ПК",
    TicketCategory.TV: "ТВ",
    TicketCategory.PHONE: "Телефон",
    TicketCategory.PRINTER: "Принтер",
    TicketCategory.OTHER: "Другое",
}


def ticket_category_label(category: TicketCategory | None) -> str:
    if category is None:
        return "-"
    return TICKET_CATEGORY_LABELS.get(category, category.value)


class AdSource(str, Enum):
    AVITO = "AVITO"
    LEAFLET = "LEAFLET"
    BUSINESS_CARD = "BUSINESS_CARD"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class LeadStatus(str, Enum):
    NEW_RAW = "NEW_RAW"
    NEED_INFO = "NEED_INFO"
    CONVERTED = "CONVERTED"
    SPAM = "SPAM"


class LeadAdSource(str, Enum):
    AVITO = "AVITO"
    FLYER = "FLYER"
    BUSINESS_CARD = "BUSINESS_CARD"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class TransferStatus(str, Enum):
    NOT_SENT = "NOT_SENT"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class ProjectTransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
