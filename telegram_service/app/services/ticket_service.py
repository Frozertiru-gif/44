from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AdSource, TicketCategory, TicketStatus
from app.db.models import Ticket


class TicketService:
    async def search_by_phone(self, session: AsyncSession, phone: str, limit: int = 5) -> list[Ticket]:
        result = await session.execute(
            select(Ticket).where(Ticket.client_phone == phone).order_by(Ticket.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def create_ticket(
        self,
        session: AsyncSession,
        *,
        category: TicketCategory,
        scheduled_at: datetime | None,
        client_name: str | None,
        client_age_estimate: int | None,
        client_phone: str,
        problem_text: str,
        special_note: str | None,
        ad_source: AdSource,
        created_by_admin_id: int,
        is_repeat: bool = False,
        repeat_ticket_ids: list[int] | None = None,
    ) -> Ticket:
        ticket = Ticket(
            status=TicketStatus.READY_FOR_WORK,
            category=category,
            scheduled_at=scheduled_at,
            client_name=client_name,
            client_age_estimate=client_age_estimate,
            client_phone=client_phone,
            problem_text=problem_text,
            special_note=special_note,
            ad_source=ad_source,
            is_repeat=is_repeat,
            repeat_ticket_ids=repeat_ticket_ids,
            created_by_admin_id=created_by_admin_id,
        )
        session.add(ticket)
        await session.flush()
        return ticket

    async def list_tickets(self, session: AsyncSession, limit: int = 20) -> list[Ticket]:
        result = await session.execute(select(Ticket).order_by(Ticket.id.desc()).limit(limit))
        return list(result.scalars().all())

    async def list_active(self, session: AsyncSession, limit: int = 20) -> list[Ticket]:
        result = await session.execute(
            select(Ticket)
            .where(Ticket.status != TicketStatus.CANCELLED)
            .order_by(Ticket.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_repeats(self, session: AsyncSession, limit: int = 20) -> list[Ticket]:
        result = await session.execute(
            select(Ticket).where(Ticket.is_repeat.is_(True)).order_by(Ticket.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_ticket(self, session: AsyncSession, ticket_id: int) -> Ticket | None:
        result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
        return result.scalar_one_or_none()

    async def cancel_ticket(self, session: AsyncSession, ticket: Ticket) -> Ticket:
        ticket.status = TicketStatus.CANCELLED
        await session.flush()
        return ticket
