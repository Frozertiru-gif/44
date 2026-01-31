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
    CANCELLED = "CANCELLED"


class TicketCategory(str, Enum):
    PC = "ПК"
    TV = "ТВ"
    PHONE = "Телефон"
    PRINTER = "Принтер"
    OTHER = "Другое"


class AdSource(str, Enum):
    AVITO = "Авито"
    FLYER = "Листовка"
    CARD = "Визитка"
    OTHER = "Другое"
    UNKNOWN = "Неизвестно"
