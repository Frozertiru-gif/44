from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import TicketStatus, TransferStatus
from app.db.models import Ticket, User


class IssueService:
    async def list_transfer_overdue(
        self,
        session: AsyncSession,
        *,
        days: int,
        limit: int = 10,
    ) -> list[Ticket]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await session.execute(
            select(Ticket)
            .where(
                Ticket.status == TicketStatus.CLOSED,
                Ticket.transfer_status != TransferStatus.CONFIRMED,
                Ticket.closed_at.is_not(None),
                Ticket.closed_at <= cutoff,
            )
            .order_by(Ticket.closed_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_zero_profit(self, session: AsyncSession, *, limit: int = 10) -> list[Ticket]:
        result = await session.execute(
            select(Ticket)
            .where(Ticket.status == TicketStatus.CLOSED, Ticket.net_profit == 0)
            .order_by(Ticket.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_repeat_phones(self, session: AsyncSession, *, limit: int = 5) -> list[tuple[str, int]]:
        result = await session.execute(
            select(Ticket.client_phone, func.count(Ticket.id))
            .group_by(Ticket.client_phone)
            .having(func.count(Ticket.id) > 1)
            .order_by(func.count(Ticket.id).desc())
            .limit(limit)
        )
        return [(row[0], int(row[1])) for row in result.all()]

    async def list_master_pending_transfers(
        self, session: AsyncSession, *, limit: int = 5
    ) -> list[tuple[User | None, Decimal]]:
        result = await session.execute(
            select(Ticket.assigned_executor_id, func.coalesce(func.sum(Ticket.net_profit), 0))
            .where(
                Ticket.status == TicketStatus.CLOSED,
                Ticket.assigned_executor_id.is_not(None),
                Ticket.transfer_status != TransferStatus.CONFIRMED,
            )
            .group_by(Ticket.assigned_executor_id)
            .order_by(func.coalesce(func.sum(Ticket.net_profit), 0).desc())
            .limit(limit)
        )
        rows = result.all()
        if not rows:
            return []
        user_ids = [row[0] for row in rows if row[0] is not None]
        users_result = await session.execute(select(User).where(User.id.in_(user_ids)))
        user_map = {user.id: user for user in users_result.scalars().all()}
        return [(user_map.get(row[0]), Decimal(row[1] or 0)) for row in rows]
