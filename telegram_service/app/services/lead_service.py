from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.utils import format_lead_card, normalize_phone
from app.bot.keyboards.request_chat import lead_request_keyboard
from app.core.config import get_settings
from app.db.enums import AdSource, LeadAdSource, LeadStatus
from app.db.models import Lead
from app.services.audit_service import AuditService
from app.services.project_settings_service import ProjectSettingsService
from app.services.ticket_service import TicketService


class LeadService:
    def __init__(self) -> None:
        self._audit = AuditService()
        self._ticket_service = TicketService()
        self._project_settings_service = ProjectSettingsService()

    async def get_lead(self, session: AsyncSession, lead_id: UUID) -> Lead | None:
        return await session.get(Lead, lead_id)

    async def get_lead_for_update(self, session: AsyncSession, lead_id: UUID) -> Lead | None:
        result = await session.execute(select(Lead).where(Lead.id == lead_id).with_for_update())
        return result.scalar_one_or_none()

    async def create_from_site(self, session: AsyncSession, *, external_id: UUID | str, payload: dict[str, Any]) -> Lead:
        lead_uuid = external_id if isinstance(external_id, UUID) else UUID(str(external_id))
        existing = await self.get_lead(session, lead_uuid)
        if existing:
            return existing

        phone = normalize_phone(payload.get("client_phone") or "")
        normalized_phone = phone if phone else None
        lead = Lead(
            id=lead_uuid,
            source=str(payload.get("source") or "site"),
            client_name=payload.get("client_name"),
            client_phone=normalized_phone,
            preferred_datetime=self._parse_datetime(payload.get("preferred_datetime")),
            client_age_estimate=self._parse_age(payload.get("client_age_estimate")),
            problem_text=str(payload.get("problem_text") or "Не указано"),
            special_note=payload.get("special_note"),
            ad_source=self._parse_ad_source(payload.get("ad_source")),
            status=LeadStatus.NEW_RAW,
            meta=payload.get("meta") or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(lead)
        await session.flush()

        await self._audit.log_audit_event(
            session,
            actor_id=None,
            action="LEAD_CREATED",
            entity_type="lead",
            entity_id=str(lead.id),
            payload={"source": lead.source},
        )

        await self._publish_to_requests_chat(session, lead)
        return lead

    async def set_status(
        self,
        session: AsyncSession,
        *,
        lead: Lead,
        status: LeadStatus,
        actor_id: int | None,
        payload: dict[str, Any] | None = None,
    ) -> Lead:
        lead.status = status
        lead.updated_at = datetime.utcnow()
        await session.flush()
        await self._audit.log_audit_event(
            session,
            actor_id=actor_id,
            action="LEAD_STATUS_UPDATED",
            entity_type="lead",
            entity_id=str(lead.id),
            payload={"status": status.value, **(payload or {})},
        )
        return lead

    async def convert_to_ticket(
        self,
        session: AsyncSession,
        *,
        lead: Lead,
        ticket_id: int,
        actor_id: int | None,
    ) -> Lead:
        lead.status = LeadStatus.CONVERTED
        lead.converted_ticket_id = ticket_id
        lead.updated_at = datetime.utcnow()
        await session.flush()
        await self._audit.log_audit_event(
            session,
            actor_id=actor_id,
            action="LEAD_CONVERTED",
            entity_type="lead",
            entity_id=str(lead.id),
            payload={"ticket_id": ticket_id},
        )
        return lead

    def map_lead_to_ticket_ad_source(self, ad_source: LeadAdSource | None) -> AdSource:
        if ad_source == LeadAdSource.AVITO:
            return AdSource.AVITO
        if ad_source == LeadAdSource.FLYER:
            return AdSource.FLYER
        if ad_source == LeadAdSource.BUSINESS_CARD:
            return AdSource.CARD
        if ad_source == LeadAdSource.OTHER:
            return AdSource.OTHER
        return AdSource.UNKNOWN

    def build_ticket_prefill(self, lead: Lead) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if lead.client_phone:
            data["client_phone"] = lead.client_phone
        if lead.client_name:
            data["client_name"] = lead.client_name
        if lead.client_age_estimate is not None:
            data["client_age_estimate"] = lead.client_age_estimate
        if lead.problem_text:
            data["problem_text"] = lead.problem_text
        if lead.special_note:
            data["special_note"] = lead.special_note
        if lead.ad_source:
            data["ad_source"] = self.map_lead_to_ticket_ad_source(lead.ad_source)
        if lead.preferred_datetime:
            data["scheduled_at"] = lead.preferred_datetime
        return data

    async def _publish_to_requests_chat(self, session: AsyncSession, lead: Lead) -> None:
        settings = get_settings()
        async with Bot(settings.bot_token) as bot:
            requests_chat_id = await self._project_settings_service.get_requests_chat_id(
                session, settings.requests_chat_id
            )
            repeat_count = 0
            if lead.client_phone:
                repeats = await self._ticket_service.search_by_phone(session, lead.client_phone)
                repeat_count = len(repeats)
            await bot.send_message(
                requests_chat_id,
                format_lead_card(lead, repeat_count=repeat_count),
                reply_markup=lead_request_keyboard(lead.id),
            )

    def _parse_ad_source(self, value: Any) -> LeadAdSource:
        if isinstance(value, LeadAdSource):
            return value
        if not value:
            return LeadAdSource.UNKNOWN
        raw = str(value).strip().upper()
        mapping = {
            "AVITO": LeadAdSource.AVITO,
            "FLYER": LeadAdSource.FLYER,
            "BUSINESS_CARD": LeadAdSource.BUSINESS_CARD,
            "CARD": LeadAdSource.BUSINESS_CARD,
            "ВИЗИТКА": LeadAdSource.BUSINESS_CARD,
            "ЛИСТОВКА": LeadAdSource.FLYER,
            "АВИТО": LeadAdSource.AVITO,
            "OTHER": LeadAdSource.OTHER,
            "UNKNOWN": LeadAdSource.UNKNOWN,
        }
        return mapping.get(raw, LeadAdSource.UNKNOWN)

    def _parse_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _parse_age(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
