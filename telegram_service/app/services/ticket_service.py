from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import AdSource, ProjectTransactionType, TicketCategory, TicketStatus, TransferStatus, UserRole
from app.db.models import DailyCounter, Ticket, TicketClosePhoto, TicketMoneyOperation, User
from app.services.audit_service import AuditService
from app.domain.enums_mapping import parse_ad_source, parse_ticket_category


class TicketService:
    ACTIVE_LIST_STATUSES = (
        TicketStatus.READY_FOR_WORK,
        TicketStatus.IN_WORK,
        TicketStatus.TAKEN,
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING,
    )

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
        category: TicketCategory | str | None,
        scheduled_at: datetime | None,
        preferred_date_dm: str | None,
        client_name: str | None,
        client_age_estimate: int | None,
        client_phone: str,
        client_address: str,
        address_details: str | None,
        problem_text: str,
        special_note: str | None,
        ad_source: AdSource | str | None,
        created_by_admin_id: int,
        is_repeat: bool = False,
        repeat_ticket_ids: list[int] | None = None,
    ) -> Ticket | None:
        actor = await session.get(User, created_by_admin_id)
        if not actor or actor.role not in {
            UserRole.ADMIN,
            UserRole.JUNIOR_ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.SYS_ADMIN,
        }:
            await self._log_permission_denied(
                session,
                actor_id=created_by_admin_id,
                ticket_id=None,
                reason="CREATE_TICKET",
            )
            return None
        normalized_category = parse_ticket_category(category)
        normalized_ad_source = parse_ad_source(ad_source)
        now = datetime.utcnow()
        try:
            public_id = await self._generate_ticket_public_id(session, now)
        except ValueError:
            return None
        ticket = Ticket(
            public_id=public_id,
            status=TicketStatus.READY_FOR_WORK,
            category=normalized_category,
            scheduled_at=scheduled_at,
            preferred_date_dm=preferred_date_dm,
            client_name=client_name,
            client_age_estimate=client_age_estimate,
            client_phone=client_phone,
            client_address=client_address,
            address_details=address_details,
            problem_text=problem_text,
            special_note=special_note,
            ad_source=normalized_ad_source,
            is_repeat=is_repeat,
            repeat_ticket_ids=repeat_ticket_ids,
            created_by_admin_id=created_by_admin_id,
            created_at=now,
            updated_at=now,
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
            .where(Ticket.status.in_(self.ACTIVE_LIST_STATUSES))
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
        statuses = [TicketStatus.IN_WORK, TicketStatus.TAKEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]
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

    async def list_my_closed_page(
        self,
        session: AsyncSession,
        executor_id: int,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[Ticket], int]:
        filters = [
            Ticket.assigned_executor_id == executor_id,
            Ticket.status == TicketStatus.CLOSED,
        ]
        total_result = await session.execute(select(func.count()).select_from(Ticket).where(*filters))
        total = int(total_result.scalar_one())
        result = await session.execute(
            select(Ticket)
            .where(*filters)
            .order_by(Ticket.closed_at.desc().nullslast(), Ticket.updated_at.desc())
            .offset(page * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

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
            .options(selectinload(Ticket.assigned_executor), selectinload(Ticket.junior_master), selectinload(Ticket.closed_by_user))
            .where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def get_ticket_for_actor(self, session: AsyncSession, ticket_id: int, actor: User) -> Ticket | None:
        ticket = await self.get_ticket(session, ticket_id)
        if not ticket:
            return None
        if self._can_view_ticket(actor, ticket):
            return ticket
        return None

    async def cancel_ticket(self, session: AsyncSession, ticket: Ticket) -> Ticket:
        ticket.status = TicketStatus.CANCELLED
        await session.flush()
        return ticket

    async def take_ticket(self, session: AsyncSession, ticket_id: int, actor_id: int) -> Ticket | None:
        """Assign a master to a ticket to prevent double-taking in a shared queue."""
        if not await self._ensure_actor_role(
            session,
            actor_id,
            {UserRole.MASTER, UserRole.JUNIOR_MASTER, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN},
        ):
            await self._log_permission_denied(
                session,
                actor_id=actor_id,
                ticket_id=ticket_id,
                reason="TAKE_TICKET",
            )
            return None
        before_ticket = await self.get_ticket(session, ticket_id)
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
                status=TicketStatus.IN_WORK,
                taken_at=now,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            await self._log_invalid_transition(session, ticket_id=ticket_id, actor_id=actor_id, reason="TAKE_TICKET")
            return None
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if ticket:
            await self._audit.log_event(
                session,
                ticket_id=ticket.id,
                action="TICKET_TAKEN",
                actor_id=actor_id,
                payload={
                    "before": {
                        "status": before_ticket.status.value if before_ticket else None,
                        "assigned_executor_id": before_ticket.assigned_executor_id if before_ticket else None,
                    },
                    "after": {
                        "status": ticket.status.value,
                        "assigned_executor_id": ticket.assigned_executor_id,
                    },
                },
            )
        return ticket

    async def set_in_progress(self, session: AsyncSession, ticket_id: int, actor_id: int) -> Ticket | None:
        if not await self._ensure_actor_role(
            session,
            actor_id,
            {UserRole.MASTER, UserRole.JUNIOR_MASTER, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN},
        ):
            await self._log_permission_denied(
                session,
                actor_id=actor_id,
                ticket_id=ticket_id,
                reason="SET_IN_PROGRESS",
            )
            return None
        before_ticket = await self.get_ticket(session, ticket_id)
        now = datetime.utcnow()
        allowed = [TicketStatus.IN_WORK, TicketStatus.TAKEN, TicketStatus.WAITING]
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
            await self._log_invalid_transition(
                session, ticket_id=ticket_id, actor_id=actor_id, reason="SET_IN_PROGRESS"
            )
            return None
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if ticket:
            await self._audit.log_event(
                session,
                ticket_id=ticket.id,
                action="TICKET_STATUS_UPDATED",
                actor_id=actor_id,
                payload={
                    "before": {"status": before_ticket.status.value if before_ticket else None},
                    "after": {"status": TicketStatus.IN_PROGRESS.value},
                },
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
        closed_comment: str,
        close_photos: list[dict[str, str | None]] | None = None,
        allow_override: bool = False,
    ) -> Ticket | None:
        """Freeze financial totals and payouts to ensure later disputes have a stable ledger."""
        now = datetime.utcnow()
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if not ticket:
            return None
        if not await self._ensure_actor_role(
            session,
            actor_id,
            {UserRole.MASTER, UserRole.JUNIOR_MASTER, UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN},
        ):
            await self._log_permission_denied(
                session,
                actor_id=actor_id,
                ticket_id=ticket_id,
                reason="CLOSE_TICKET",
            )
            return None
        executor_id = ticket.assigned_executor_id
        admin_id = ticket.created_by_admin_id
        if executor_id is None or admin_id is None:
            return None
        if not allow_override and executor_id != actor_id:
            await self._log_permission_denied(
                session,
                actor_id=actor_id,
                ticket_id=ticket_id,
                reason="CLOSE_TICKET_NOT_EXECUTOR",
            )
            return None
        before_status = ticket.status
        if ticket.status != TicketStatus.IN_PROGRESS:
            await self._log_invalid_transition(
                session,
                ticket_id=ticket_id,
                actor_id=actor_id,
                reason="CLOSE_TICKET_NOT_IN_PROGRESS",
                before={"status": ticket.status.value},
            )
            return None

        previous_revenue = Decimal(ticket.revenue or 0)
        previous_expense = Decimal(ticket.expense or 0)

        executor_percent = await self._get_user_percent(session, executor_id, field="master_percent")
        admin_percent = await self._get_user_percent(session, admin_id, field="admin_percent")
        junior_percent = junior_master_percent or Decimal("0")

        try:
            executor_percent = self._validate_percent(executor_percent)
            admin_percent = self._validate_percent(admin_percent)
            junior_percent = self._validate_percent(junior_percent)
        except ValueError:
            return None

        payouts = self.calculate_payouts(
            revenue=revenue,
            expense=expense,
            executor_percent=executor_percent,
            admin_percent=admin_percent,
            junior_percent=junior_percent,
        )
        if payouts is None:
            await self._log_invalid_transition(
                session,
                ticket_id=ticket_id,
                actor_id=actor_id,
                reason="CLOSE_TICKET_PAYOUTS_INVALID",
            )
            return None

        allowed = [TicketStatus.IN_PROGRESS]
        query = update(Ticket).where(Ticket.id == ticket_id, Ticket.status.in_(allowed))
        if not allow_override:
            query = query.where(Ticket.assigned_executor_id == actor_id)
        result = await session.execute(
            query.values(
                status=TicketStatus.CLOSED,
                closed_at=now,
                closed_by_user_id=actor_id,
                closed_comment=closed_comment,
                revenue=revenue,
                expense=expense,
                net_profit=payouts["net_profit"],
                transfer_status=TransferStatus.NOT_SENT,
                transfer_sent_at=None,
                transfer_confirmed_at=None,
                transfer_confirmed_by=None,
                junior_master_id=junior_master_id,
                junior_master_percent_at_close=junior_percent if junior_master_id else None,
                junior_master_earned_amount=payouts["junior_earned"] if junior_master_id else None,
                executor_percent_at_close=executor_percent,
                admin_percent_at_close=admin_percent,
                executor_earned_amount=payouts["executor_earned"],
                admin_earned_amount=payouts["admin_earned"],
                project_take_amount=payouts["project_take"],
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            await self._log_invalid_transition(
                session, ticket_id=ticket_id, actor_id=actor_id, reason="CLOSE_TICKET"
            )
            return None
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if ticket and close_photos:
            session.add_all(
                [
                    TicketClosePhoto(
                        ticket_id=ticket.id,
                        file_id=item["file_id"],
                        file_unique_id=item.get("file_unique_id"),
                        created_at=now,
                    )
                    for item in close_photos
                    if item.get("file_id")
                ]
            )

        await self._append_money_operations(
            session,
            ticket=ticket,
            revenue=revenue,
            expense=expense,
            old_revenue=previous_revenue,
            old_expense=previous_expense,
            comment=closed_comment,
        )
        if ticket:
            await self._audit.log_event(
                session,
                ticket_id=ticket.id,
                action="TICKET_CLOSED",
                actor_id=actor_id,
                payload={
                    "before": {"status": before_status.value if before_status else None},
                    "after": {"status": ticket.status.value},
                    "revenue": float(revenue),
                    "expense": float(expense),
                    "net_profit": float(payouts["net_profit"]),
                    "junior_master_id": junior_master_id,
                    "junior_master_percent": float(junior_master_percent)
                    if junior_master_percent is not None
                    else None,
                    "closed_comment": closed_comment,
                    "close_photo_count": len(close_photos or []),
                },
            )
            await self._audit.log_event(
                session,
                ticket_id=ticket.id,
                action="TICKET_PAYOUTS_FIXED",
                actor_id=actor_id,
                payload={
                    "before": None,
                    "after": {
                        "executor_percent": float(executor_percent),
                        "admin_percent": float(admin_percent),
                        "junior_percent": float(junior_percent) if junior_master_id else None,
                    },
                    "executor_percent": float(executor_percent),
                    "admin_percent": float(admin_percent),
                    "junior_percent": float(junior_percent) if junior_master_id else None,
                    "executor_earned": float(payouts["executor_earned"]),
                    "admin_earned": float(payouts["admin_earned"]),
                    "junior_earned": float(payouts["junior_earned"]) if junior_master_id else None,
                    "project_take": float(payouts["project_take"]),
                },
            )
        return ticket


    async def get_close_photos(self, session: AsyncSession, ticket_id: int) -> list[TicketClosePhoto]:
        result = await session.execute(
            select(TicketClosePhoto)
            .where(TicketClosePhoto.ticket_id == ticket_id)
            .order_by(TicketClosePhoto.id.asc())
        )
        return list(result.scalars().all())

    async def mark_transfer_sent(self, session: AsyncSession, ticket_id: int, actor_id: int) -> Ticket | None:
        now = datetime.utcnow()
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if not ticket:
            return None
        if ticket.assigned_executor_id != actor_id:
            await self._log_permission_denied(
                session,
                actor_id=actor_id,
                ticket_id=ticket_id,
                reason="TRANSFER_SENT_NOT_EXECUTOR",
            )
            return None
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
            await self._log_invalid_transition(
                session, ticket_id=ticket_id, actor_id=actor_id, reason="TRANSFER_SENT"
            )
            return None
        if ticket:
            await self._audit.log_event(
                session,
                ticket_id=ticket.id,
                action="TRANSFER_SENT",
                actor_id=actor_id,
                payload={
                    "before": {"transfer_status": ticket.transfer_status.value if ticket.transfer_status else None},
                    "after": {"transfer_status": TransferStatus.SENT.value},
                },
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
        """Confirm transfers centrally to stop accidental confirmations from executors."""
        now = datetime.utcnow()
        if not await self._ensure_actor_role(session, actor_id, {UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN}):
            await self._log_permission_denied(
                session,
                actor_id=actor_id,
                ticket_id=ticket_id,
                reason="TRANSFER_CONFIRM",
            )
            return None
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
            await self._log_invalid_transition(
                session, ticket_id=ticket_id, actor_id=actor_id, reason="TRANSFER_CONFIRM"
            )
            return None
        ticket = await self.get_ticket_with_executor(session, ticket_id)
        if ticket:
            await self._audit.log_event(
                session,
                ticket_id=ticket.id,
                action=action,
                actor_id=actor_id,
                payload={
                    "before": {"transfer_status": TransferStatus.SENT.value},
                    "after": {"transfer_status": status.value},
                },
            )
        return ticket

    async def get_ticket_with_executor(self, session: AsyncSession, ticket_id: int) -> Ticket | None:
        result = await session.execute(
            select(Ticket)
            .options(selectinload(Ticket.assigned_executor), selectinload(Ticket.junior_master), selectinload(Ticket.closed_by_user))
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
            .options(selectinload(Ticket.assigned_executor), selectinload(Ticket.junior_master), selectinload(Ticket.closed_by_user))
            .where(Ticket.assigned_executor_id == master_id, Ticket.status.in_(statuses))
            .order_by(Ticket.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_for_actor(
        self,
        session: AsyncSession,
        actor: User,
        *,
        filter_key: str,
        limit: int = 20,
    ) -> list[Ticket]:
        query = select(Ticket).order_by(Ticket.id.desc()).limit(limit)
        if filter_key == "active":
            query = query.where(Ticket.status != TicketStatus.CANCELLED)
        elif filter_key == "repeat":
            query = query.where(Ticket.is_repeat.is_(True))

        access_filter = self._build_access_filter(actor)
        if access_filter is False:
            return []
        if access_filter is not None:
            query = query.where(access_filter)

        result = await session.execute(query)
        return list(result.scalars().all())

    async def list_for_actor_page(
        self,
        session: AsyncSession,
        actor: User,
        *,
        filter_key: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Ticket], int]:
        base_query = select(Ticket).order_by(Ticket.id.desc())
        base_query = self._apply_filter_key(base_query, filter_key)
        access_filter = self._build_access_filter(actor)
        if access_filter is False:
            return [], 0
        if access_filter is not None:
            base_query = base_query.where(access_filter)
        total_query = select(func.count()).select_from(Ticket)
        total_query = self._apply_filter_key(total_query, filter_key)
        if access_filter is not None:
            total_query = total_query.where(access_filter)
        total_result = await session.execute(total_query)
        total = int(total_result.scalar_one())
        result = await session.execute(base_query.offset(page * page_size).limit(page_size))
        return list(result.scalars().all()), total

    async def search_for_actor_page(
        self,
        session: AsyncSession,
        actor: User,
        *,
        ticket_id: int | None = None,
        public_id: str | None = None,
        phone_digits: str | None = None,
        page: int,
        page_size: int,
    ) -> tuple[list[Ticket], int]:
        access_filter = self._build_access_filter(actor)
        if access_filter is False:
            return [], 0
        base_query = select(Ticket).order_by(Ticket.id.desc())
        filters = []
        if ticket_id is not None:
            filters.append(Ticket.id == ticket_id)
        elif public_id:
            filters.append(Ticket.public_id == public_id)
        elif phone_digits:
            phone_expr = func.regexp_replace(Ticket.client_phone, r"\D", "", "g")
            filters.append(phone_expr.ilike(f"%{phone_digits}%"))
        else:
            return [], 0
        if access_filter is not None:
            filters.append(access_filter)
        total_query = select(func.count()).select_from(Ticket).where(*filters)
        total_result = await session.execute(total_query)
        total = int(total_result.scalar_one())
        result = await session.execute(
            base_query.where(*filters).offset(page * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def _generate_ticket_public_id(self, session: AsyncSession, created_at: datetime) -> str:
        counter_day = created_at.date()
        seq_value = await self._next_daily_counter(session, counter_day)
        if seq_value > 99:
            raise ValueError(f"Превышен лимит заявок на дату {counter_day.isoformat()} (максимум 99)")
        return f"{counter_day.strftime('%d%m%y')}{seq_value:02d}"

    async def _next_daily_counter(self, session: AsyncSession, counter_day: date) -> int:
        statement = (
            pg_insert(DailyCounter)
            .values(counter_date=counter_day, counter=1)
            .on_conflict_do_update(
                index_elements=[DailyCounter.counter_date],
                set_={"counter": DailyCounter.counter + 1},
            )
            .returning(DailyCounter.counter)
        )
        result = await session.execute(statement)
        return int(result.scalar_one())

    async def _append_money_operations(
        self,
        session: AsyncSession,
        *,
        ticket: Ticket | None,
        revenue: Decimal,
        expense: Decimal,
        old_revenue: Decimal,
        old_expense: Decimal,
        comment: str | None,
    ) -> None:
        if ticket is None:
            return

        category_snapshot = ticket.category.value if ticket.category else "UNKNOWN"
        income_delta = self._round_money(revenue - old_revenue)
        expense_delta = self._round_money(expense - old_expense)

        operations: list[TicketMoneyOperation] = []
        if income_delta != Decimal("0.00"):
            operations.append(
                TicketMoneyOperation(
                    ticket_id=ticket.id,
                    op_type=ProjectTransactionType.INCOME,
                    amount=income_delta,
                    category_snapshot=category_snapshot,
                    comment=comment,
                )
            )
        if expense_delta != Decimal("0.00"):
            operations.append(
                TicketMoneyOperation(
                    ticket_id=ticket.id,
                    op_type=ProjectTransactionType.EXPENSE,
                    amount=expense_delta,
                    category_snapshot=category_snapshot,
                    comment=comment,
                )
            )

        if operations:
            session.add_all(operations)

    async def _get_user_percent(self, session: AsyncSession, user_id: int, *, field: str) -> Decimal:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return Decimal("0")
        value = getattr(user, field, None)
        return value if value is not None else Decimal("0")

    def calculate_payouts(
        self,
        *,
        revenue: Decimal,
        expense: Decimal,
        executor_percent: Decimal,
        admin_percent: Decimal,
        junior_percent: Decimal,
    ) -> dict[str, Decimal] | None:
        """Keep payout math centralized so financial invariants stay consistent across services."""
        net_profit = revenue - expense
        if net_profit < 0:
            net_profit = Decimal("0")
        net_profit = self._round_money(net_profit)

        executor_earned = self._round_money(net_profit * executor_percent / Decimal("100"))
        admin_earned = self._round_money(net_profit * admin_percent / Decimal("100"))
        junior_earned = self._round_money(net_profit * junior_percent / Decimal("100"))
        project_take = self._round_money(net_profit - (executor_earned + admin_earned + junior_earned))

        if executor_earned < 0 or admin_earned < 0 or junior_earned < 0 or project_take < 0:
            return None
        if executor_earned + admin_earned + junior_earned + project_take != net_profit:
            return None

        return {
            "net_profit": net_profit,
            "executor_earned": executor_earned,
            "admin_earned": admin_earned,
            "junior_earned": junior_earned,
            "project_take": project_take,
        }

    def _validate_percent(self, percent: Decimal) -> Decimal:
        if percent < 0 or percent > 100:
            raise ValueError("Процент должен быть от 0 до 100")
        if percent.as_tuple().exponent < -2:
            raise ValueError("Процент должен иметь максимум 2 знака после запятой")
        return percent

    def _round_money(self, value: Decimal) -> Decimal:
        return value.quantize(self._money_round, rounding=ROUND_HALF_UP)

    async def _ensure_actor_role(self, session: AsyncSession, actor_id: int, allowed_roles: set[UserRole]) -> bool:
        actor = await session.get(User, actor_id)
        if not actor or actor.role not in allowed_roles:
            return False
        return True

    def _build_access_filter(self, actor: User) -> bool | Any:
        if actor.role in {UserRole.MASTER, UserRole.JUNIOR_MASTER}:
            return Ticket.assigned_executor_id == actor.id
        if actor.role in {
            UserRole.ADMIN,
            UserRole.JUNIOR_ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.SYS_ADMIN,
        }:
            return None
        return False

    @staticmethod
    def _apply_filter_key(query, filter_key: str):
        if filter_key == "active":
            return query.where(Ticket.status.in_(TicketService.ACTIVE_LIST_STATUSES))
        if filter_key == "repeat":
            return query.where(Ticket.is_repeat.is_(True))
        return query

    def _can_view_ticket(self, actor: User, ticket: Ticket) -> bool:
        if actor.role in {
            UserRole.ADMIN,
            UserRole.JUNIOR_ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.SYS_ADMIN,
        }:
            return True
        if actor.role in {UserRole.MASTER, UserRole.JUNIOR_MASTER}:
            return ticket.assigned_executor_id == actor.id
        return False

    async def _log_invalid_transition(
        self,
        session: AsyncSession,
        *,
        ticket_id: int,
        actor_id: int,
        reason: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        ticket = await self.get_ticket(session, ticket_id)
        payload = {
            "reason": reason,
            "before": before or ({"status": ticket.status.value} if ticket else None),
            "after": after,
        }
        await self._audit.log_audit_event(
            session,
            actor_id=actor_id,
            action="INVALID_STATE_TRANSITION",
            entity_type="ticket",
            entity_id=ticket_id,
            payload=payload,
            ticket_id=ticket_id,
        )

    async def _log_permission_denied(
        self,
        session: AsyncSession,
        *,
        actor_id: int,
        ticket_id: int | None,
        reason: str,
    ) -> None:
        await self._audit.log_audit_event(
            session,
            actor_id=actor_id,
            action="PERMISSION_DENIED",
            entity_type="ticket",
            entity_id=ticket_id,
            payload={"reason": reason},
            ticket_id=ticket_id,
        )
