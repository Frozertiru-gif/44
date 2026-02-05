from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import ProjectTransactionType, TicketStatus, TransferStatus
from app.db.models import ProjectShare, ProjectTransaction, Ticket, TicketMoneyOperation, User


@dataclass(frozen=True)
class DateRange:
    start: datetime | None
    end: datetime | None


class FinanceService:
    def __init__(self) -> None:
        self._money_round = Decimal("0.01")

    def build_range(self, start_date: date | None, end_date: date | None) -> DateRange:
        start = datetime.combine(start_date, datetime.min.time()) if start_date else None
        end = datetime.combine(end_date, datetime.max.time()) if end_date else None
        return DateRange(start=start, end=end)

    async def master_money(
        self,
        session: AsyncSession,
        master_id: int,
        *,
        date_range: DateRange,
    ) -> dict[str, Decimal]:
        to_transfer = func.coalesce(Ticket.net_profit, 0) - func.coalesce(
            Ticket.executor_earned_amount, 0
        )
        base = select(
            func.coalesce(func.sum(Ticket.executor_earned_amount), 0),
            func.coalesce(func.sum(to_transfer), 0),
            func.coalesce(
                func.sum(
                    case(
                        (Ticket.transfer_status == TransferStatus.CONFIRMED, to_transfer),
                        else_=0,
                    )
                ),
                0,
            ),
        ).where(Ticket.status == TicketStatus.CLOSED, Ticket.assigned_executor_id == master_id)
        base = self._apply_range(base, Ticket.closed_at, date_range)
        result = await session.execute(base)
        earned_executor, net_profit, confirmed = result.one()
        admin_query = select(func.coalesce(func.sum(Ticket.admin_earned_amount), 0)).where(
            Ticket.status == TicketStatus.CLOSED,
            Ticket.created_by_admin_id == master_id,
        )
        admin_query = self._apply_range(admin_query, Ticket.closed_at, date_range)
        admin_result = await session.execute(admin_query)
        earned_admin = admin_result.scalar() or 0
        share_percent_query = select(ProjectShare.percent).where(
            ProjectShare.user_id == master_id,
            ProjectShare.is_active.is_(True),
        )
        share_percent_result = await session.execute(share_percent_query)
        share_percent = share_percent_result.scalar_one_or_none()

        cash_base_query = select(func.coalesce(func.sum(Ticket.net_profit), 0)).where(
            Ticket.status == TicketStatus.CLOSED
        )
        cash_base_query = self._apply_range(cash_base_query, Ticket.closed_at, date_range)
        cash_base_result = await session.execute(cash_base_query)
        total_net_cash = Decimal(cash_base_result.scalar() or 0)
        cash_share_amount = Decimal("0.00")
        if share_percent:
            cash_share_amount = self.round_money(
                total_net_cash * Decimal(share_percent) / Decimal("100")
            )

        earned = Decimal(earned_executor or 0) + Decimal(earned_admin or 0) + cash_share_amount
        pending = Decimal(net_profit) - Decimal(confirmed)
        return {
            "earned": earned,
            "net_profit": Decimal(net_profit or 0),
            "confirmed": Decimal(confirmed or 0),
            "pending": pending if pending > 0 else Decimal("0.00"),
            "cash_share_amount": cash_share_amount,
        }

    async def admin_salary(
        self,
        session: AsyncSession,
        admin_id: int,
        *,
        date_range: DateRange,
    ) -> Decimal:
        query = select(func.coalesce(func.sum(Ticket.admin_earned_amount), 0)).where(
            Ticket.status == TicketStatus.CLOSED,
            Ticket.created_by_admin_id == admin_id,
        )
        query = self._apply_range(query, Ticket.closed_at, date_range)
        result = await session.execute(query)
        return Decimal(result.scalar() or 0)

    async def junior_salary(
        self,
        session: AsyncSession,
        junior_id: int,
        *,
        date_range: DateRange,
    ) -> Decimal:
        query = select(func.coalesce(func.sum(Ticket.junior_master_earned_amount), 0)).where(
            Ticket.status == TicketStatus.CLOSED,
            Ticket.junior_master_id == junior_id,
        )
        query = self._apply_range(query, Ticket.closed_at, date_range)
        result = await session.execute(query)
        return Decimal(result.scalar() or 0)

    async def project_summary(
        self,
        session: AsyncSession,
        *,
        date_range: DateRange,
    ) -> dict[str, Decimal | int]:
        tickets_query = select(
            func.coalesce(func.sum(Ticket.net_profit), 0),
            func.coalesce(
                func.sum(
                    case(
                        (Ticket.transfer_status == TransferStatus.CONFIRMED, Ticket.net_profit),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(Ticket.executor_earned_amount), 0),
            func.coalesce(func.sum(Ticket.admin_earned_amount), 0),
            func.coalesce(func.sum(Ticket.junior_master_earned_amount), 0),
            func.coalesce(func.sum(Ticket.project_take_amount), 0),
            func.count(Ticket.id),
            func.coalesce(
                func.sum(case((Ticket.transfer_status == TransferStatus.CONFIRMED, 1), else_=0)),
                0,
            ),
            func.coalesce(func.sum(case((Ticket.is_repeat.is_(True), 1), else_=0)), 0),
        ).where(Ticket.status == TicketStatus.CLOSED)
        tickets_query = self._apply_range(tickets_query, Ticket.closed_at, date_range)
        tickets_row = (await session.execute(tickets_query)).one()

        income_sum = await self._transaction_sum(
            session, ProjectTransactionType.INCOME, date_range=date_range
        )
        expense_sum = await self._transaction_sum(
            session, ProjectTransactionType.EXPENSE, date_range=date_range
        )

        tickets_net_profit_should = Decimal(tickets_row[0] or 0)
        tickets_net_profit_received = Decimal(tickets_row[1] or 0)
        manual_income_sum = Decimal(income_sum or 0)
        manual_expense_sum = Decimal(expense_sum or 0)

        project_net_cash_should = tickets_net_profit_should + manual_income_sum - manual_expense_sum
        project_net_cash_received = tickets_net_profit_received + manual_income_sum - manual_expense_sum

        return {
            "tickets_net_profit_should": tickets_net_profit_should,
            "tickets_net_profit_received": tickets_net_profit_received,
            "manual_income_sum": manual_income_sum,
            "manual_expense_sum": manual_expense_sum,
            "project_net_cash_should": project_net_cash_should,
            "project_net_cash_received": project_net_cash_received,
            "earned_executor": Decimal(tickets_row[2] or 0),
            "earned_admin": Decimal(tickets_row[3] or 0),
            "earned_junior": Decimal(tickets_row[4] or 0),
            "project_take_sum": Decimal(tickets_row[5] or 0),
            "closed_count": int(tickets_row[6] or 0),
            "confirmed_count": int(tickets_row[7] or 0),
            "repeats_count": int(tickets_row[8] or 0),
        }

    async def list_tickets_for_export(
        self,
        session: AsyncSession,
        *,
        date_range: DateRange,
    ) -> list[Ticket]:
        query = (
            select(Ticket)
            .options(
                selectinload(Ticket.assigned_executor),
                selectinload(Ticket.junior_master),
                selectinload(Ticket.created_by),
            )
            .where(Ticket.status == TicketStatus.CLOSED)
            .order_by(Ticket.id.asc())
        )
        query = self._apply_range(query, Ticket.closed_at, date_range)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def list_manual_transactions(
        self,
        session: AsyncSession,
        *,
        date_range: DateRange,
    ) -> list[ProjectTransaction]:
        query = select(ProjectTransaction).options(selectinload(ProjectTransaction.creator)).order_by(
            ProjectTransaction.id.asc()
        )
        query = self._apply_range(query, ProjectTransaction.occurred_at, date_range)
        result = await session.execute(query)
        return list(result.scalars().all())


    async def list_ticket_money_operations(
        self,
        session: AsyncSession,
        *,
        date_range: DateRange,
    ) -> list[TicketMoneyOperation]:
        query = (
            select(TicketMoneyOperation)
            .options(selectinload(TicketMoneyOperation.ticket))
            .order_by(TicketMoneyOperation.created_at.asc(), TicketMoneyOperation.id.asc())
        )
        query = self._apply_range(query, TicketMoneyOperation.created_at, date_range)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def list_active_shares(self, session: AsyncSession) -> list[ProjectShare]:
        result = await session.execute(
            select(ProjectShare)
            .options(selectinload(ProjectShare.user))
            .where(ProjectShare.is_active.is_(True))
            .order_by(ProjectShare.user_id.asc())
        )
        return list(result.scalars().all())

    def round_money(self, value: Decimal) -> Decimal:
        return value.quantize(self._money_round, rounding=ROUND_HALF_UP)

    async def _transaction_sum(
        self,
        session: AsyncSession,
        transaction_type: ProjectTransactionType,
        *,
        date_range: DateRange,
    ) -> Decimal:
        query = select(func.coalesce(func.sum(ProjectTransaction.amount), 0)).where(
            ProjectTransaction.type == transaction_type
        )
        query = self._apply_range(query, ProjectTransaction.occurred_at, date_range)
        result = await session.execute(query)
        return Decimal(result.scalar() or 0)

    def _apply_range(self, query, column, date_range: DateRange):
        if date_range.start:
            query = query.where(column >= date_range.start)
        if date_range.end:
            query = query.where(column <= date_range.end)
        return query
