from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ProjectTransactionType
from app.db.models import ProjectTransaction
from app.services.audit_service import AuditService


class ProjectTransactionService:
    def __init__(self) -> None:
        self._audit = AuditService()

    async def add_transaction(
        self,
        session: AsyncSession,
        *,
        transaction_type: ProjectTransactionType,
        amount: Decimal,
        category: str,
        comment: str | None,
        occurred_at: datetime,
        created_by: int,
    ) -> ProjectTransaction:
        transaction = ProjectTransaction(
            type=transaction_type,
            amount=amount,
            category=category,
            comment=comment,
            occurred_at=occurred_at,
            created_by=created_by,
        )
        session.add(transaction)
        await session.flush()
        await self._audit.log_audit_event(
            session,
            actor_id=created_by,
            action="PROJECT_TX_ADDED",
            entity_type="project_transaction",
            entity_id=transaction.id,
            payload={
                "type": transaction_type.value,
                "amount": float(amount),
                "category": category,
                "comment": comment,
                "occurred_at": occurred_at.isoformat(),
            },
        )
        return transaction
