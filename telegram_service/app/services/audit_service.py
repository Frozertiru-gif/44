from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent, TicketEvent


class AuditService:
    async def log_event(
        self,
        session: AsyncSession,
        ticket_id: int,
        action: str,
        actor_id: int | None,
        payload: dict[str, Any] | None = None,
    ) -> TicketEvent:
        event = TicketEvent(
            ticket_id=ticket_id,
            action=action,
            actor_id=actor_id,
            payload=payload,
        )
        session.add(event)
        await session.flush()
        return event

    async def log_audit_event(
        self,
        session: AsyncSession,
        *,
        actor_id: int | None,
        action: str,
        entity_type: str,
        entity_id: int | None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )
        session.add(event)
        await session.flush()
        return event
