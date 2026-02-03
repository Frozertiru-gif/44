from __future__ import annotations

from app.db.enums import TicketCategory
from app.domain.enums_mapping import parse_ticket_category


def normalize_ticket_category(value: TicketCategory | str | None) -> TicketCategory:
    return parse_ticket_category(value)
