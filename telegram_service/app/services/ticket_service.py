from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import AdSource, TicketCategory, TicketStatus, TransferStatus
from app.db.models import Ticket, User
from app.services.audit_service import AuditService


class TicketService:
    def __init__(self) -> None:
        self._audit = AuditService()
        self._money_round = Decimal("0.01")

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

    async def list_queue(self, session: AsyncSession, limit: int = 20) -> list[Ticket]:
        result = await session.execute(
            select(Ticket)
            .where(Ticket.status == TicketStatus.READY_FOR_WORK, Ticket.assigned_executor_id.is_(None))
            .order_by(Ticket.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_my_active(self, session: AsyncSession, executor_id: int, limit: int = 20) -> list[Ticket]:
        statuses = [TicketStatus.TAKEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]
        result = await session.execute(
            select(Ticket)
            .where(Ticket.assigned_executor_id == executor_id, Ticket.status.in_(statuses))
            .order_by(Ticket.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_my_closed(self, session: AsyncSession, executor_id: int, limit: int = 20) -> list[Ticket]:
        result = await session.execute(
            select(Ticket)
            .where(Ticket.assigned_executor_id == executor_id, Ticket.status == TicketStatus.CLOSED)
            .order_by(Ticket.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_transfer_pending(self, session: AsyncSession, limit: int = 20) -> list[Ticket]:
        result = await session.execute(
            select(Ticket)
            .options(selectinload(Ticket.assigned_executor))
            .where(Ticket.transfer_status == TransferStatus.SENT)
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
        result = await session.execute(
            select(Ticket)
            .options(selectinload(Ticket.assigned_executor), selectinload(Ticket.junior_master))
            .where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def cancel_ticket(self, session: AsyncSession, ticket: Ticket) -> Ticket:
        ticket.status = TicketStatus.CANCELLED
        await session.flush()
        return ticket

    async def take_ticket(self, session: AsyncSession, ticket_id: int, actor_id: int) -> Ticket | None:
        now = datetime.utcnow()
        result = await session.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.status == TicketStatus.READY_FOR_WORK,
                Ticket.assigned_executor_id.is_(None),
            )
            .values(
                assigned_executor_id=actor_id,
                status=TicketStatus.TAKEN,
                taken_at=now,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            return None
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if ticket:
            await self._audit.log_event(session, ticket_id=ticket.id, action="TICKET_TAKEN", actor_id=actor_id)
        return ticket

    async def set_in_progress(self, session: AsyncSession, ticket_id: int, actor_id: int) -> Ticket | None:
        now = datetime.utcnow()
        allowed = [TicketStatus.TAKEN, TicketStatus.WAITING]
        result = await session.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.assigned_executor_id == actor_id,
                Ticket.status.in_(allowed),
            )
            .values(status=TicketStatus.IN_PROGRESS, updated_at=now)
        )
        if result.rowcount == 0:
            return None
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if ticket:
            await self._audit.log_event(
                session,
                ticket_id=ticket.id,
                action="TICKET_STATUS_UPDATED",
                actor_id=actor_id,
                payload={"status": TicketStatus.IN_PROGRESS.value},
            )
        return ticket

    async def close_ticket(
        self,
        session: AsyncSession,
        ticket_id: int,
        actor_id: int,
        *,
        revenue: Decimal,
        expense: Decimal,
        junior_master_id: int | None,
        junior_master_percent: Decimal | None,
        allow_override: bool = False,
    ) -> Ticket | None:
        now = datetime.utcnow()
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if not ticket:
            return None
        executor_id = ticket.assigned_executor_id
        admin_id = ticket.created_by_admin_id
        if executor_id is None or admin_id is None:
            return None

        executor_percent = await self._get_user_percent(session, executor_id, field="master_percent")
        admin_percent = await self._get_user_percent(session, admin_id, field="admin_percent")
        junior_percent = junior_master_percent or Decimal("0")

        try:
            executor_percent = self._validate_percent(executor_percent)
            admin_percent = self._validate_percent(admin_percent)
            junior_percent = self._validate_percent(junior_percent)
        except ValueError:
            return None

        net_profit = revenue - expense
        if net_profit < 0:
            net_profit = Decimal("0")

        executor_earned = self._round_money(net_profit * executor_percent / Decimal("100"))
        admin_earned = self._round_money(net_profit * admin_percent / Decimal("100"))
        junior_earned = self._round_money(net_profit * junior_percent / Decimal("100"))
        project_take = net_profit - (executor_earned + admin_earned + junior_earned)
        if project_take < 0:
            project_take = Decimal("0.00")

        allowed = [TicketStatus.TAKEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]
        query = update(Ticket).where(Ticket.id == ticket_id, Ticket.status.in_(allowed))
        if not allow_override:
            query = query.where(Ticket.assigned_executor_id == actor_id)
        result = await session.execute(
            query.values(
                status=TicketStatus.CLOSED,
                closed_at=now,
                revenue=revenue,
                expense=expense,
                net_profit=net_profit,
                transfer_status=TransferStatus.NOT_SENT,
                transfer_sent_at=None,
                transfer_confirmed_at=None,
                transfer_confirmed_by=None,
                junior_master_id=junior_master_id,
                junior_master_percent_at_close=junior_percent if junior_master_id else None,
                junior_master_earned_amount=junior_earned if junior_master_id else None,
                executor_percent_at_close=executor_percent,
                admin_percent_at_close=admin_percent,
                executor_earned_amount=executor_earned,
                admin_earned_amount=admin_earned,
                project_take_amount=project_take,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            return None
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if ticket:
            await self._audit.log_event(
                session,
                ticket_id=ticket.id,
                action="TICKET_CLOSED",
                actor_id=actor_id,
                payload={
                    "revenue": float(revenue),
                    "expense": float(expense),
                    "net_profit": float(net_profit),
                    "junior_master_id": junior_master_id,
                    "junior_master_percent": float(junior_master_percent)
                    if junior_master_percent is not None
                    else None,
                },
            )
            await self._audit.log_event(
                session,
                ticket_id=ticket.id,
                action="TICKET_PAYOUTS_FIXED",
                actor_id=actor_id,
                payload={
                    "executor_percent": float(executor_percent),
                    "admin_percent": float(admin_percent),
                    "junior_percent": float(junior_percent) if junior_master_id else None,
                    "executor_earned": float(executor_earned),
                    "admin_earned": float(admin_earned),
                    "junior_earned": float(junior_earned) if junior_master_id else None,
                    "project_take": float(project_take),
                },
            )
        return ticket

    async def mark_transfer_sent(self, session: AsyncSession, ticket_id: int, actor_id: int) -> Ticket | None:
        now = datetime.utcnow()
        result = await session.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.assigned_executor_id == actor_id,
                Ticket.status == TicketStatus.CLOSED,
                Ticket.transfer_status == TransferStatus.NOT_SENT,
            )
            .values(transfer_status=TransferStatus.SENT, transfer_sent_at=now, updated_at=now)
        )
        if result.rowcount == 0:
            return None
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if ticket:
            await self._audit.log_event(
                session,
                ticket_id=ticket.id,
                action="TRANSFER_SENT",
                actor_id=actor_id,
            )
        return ticket

    async def confirm_transfer(
        self,
        session: AsyncSession,
        ticket_id: int,
        actor_id: int,
        *,
        approved: bool,
    ) -> Ticket | None:
        now = datetime.utcnow()
        status = TransferStatus.CONFIRMED if approved else TransferStatus.REJECTED
        action = "TRANSFER_CONFIRMED" if approved else "TRANSFER_REJECTED"
        result = await session.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id, Ticket.transfer_status == TransferStatus.SENT)
            .values(
                transfer_status=status,
                transfer_confirmed_by=actor_id,
                transfer_confirmed_at=now,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            return None
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if ticket:
            await self._audit.log_event(session, ticket_id=ticket.id, action=action, actor_id=actor_id)
        return ticket

    async def get_ticket_with_executor(self, session: AsyncSession, ticket_id: int) -> Ticket | None:
        result = await session.execute(
            select(Ticket)
            .options(selectinload(Ticket.assigned_executor), selectinload(Ticket.junior_master))
            .where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def list_for_master(
        self,
        session: AsyncSession,
        master_id: int,
        *,
        statuses: list[TicketStatus],
        limit: int = 20,
    ) -> list[Ticket]:
        result = await session.execute(
            select(Ticket)
            .options(selectinload(Ticket.assigned_executor), selectinload(Ticket.junior_master))
            .where(Ticket.assigned_executor_id == master_id, Ticket.status.in_(statuses))
            .order_by(Ticket.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_user_percent(self, session: AsyncSession, user_id: int, *, field: str) -> Decimal:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return Decimal("0")
        value = getattr(user, field, None)
        return value if value is not None else Decimal("0")

    def _validate_percent(self, percent: Decimal) -> Decimal:
        if percent < 0 or percent > 100:
            raise ValueError("Процент должен быть от 0 до 100")
        if percent.as_tuple().exponent < -2:
            raise ValueError("Процент должен иметь максимум 2 знака после запятой")
        return percent

    def _round_money(self, value: Decimal) -> Decimal:
        return value.quantize(self._money_round, rounding=ROUND_HALF_UP)
