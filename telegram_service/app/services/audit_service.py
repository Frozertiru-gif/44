from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent, TicketEvent


class AuditService:
    def _enrich_payload(
        self,
        *,
        payload: dict[str, Any] | None,
        actor_id: int | None,
        ticket_id: int | None = None,
        entity_id: int | None = None,
    ) -> dict[str, Any]:
        enriched = dict(payload or {})
        enriched.setdefault("actor_id", actor_id)
        if ticket_id is not None:
            enriched.setdefault("ticket_id", ticket_id)
        if entity_id is not None:
            enriched.setdefault("entity_id", entity_id)
        enriched.setdefault("timestamp", datetime.utcnow().isoformat())
        return enriched

    async def log_event(
        self,
        session: AsyncSession,
        ticket_id: int,
        action: str,
        actor_id: int | None,
        payload: dict[str, Any] | None = None,
    ) -> TicketEvent:
        payload = self._enrich_payload(payload=payload, actor_id=actor_id, ticket_id=ticket_id)
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
        ticket_id: int | None = None,
    ) -> AuditEvent:
        payload = self._enrich_payload(
            payload=payload,
            actor_id=actor_id,
            ticket_id=ticket_id,
            entity_id=entity_id,
        )
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
