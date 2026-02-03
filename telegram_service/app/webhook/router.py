from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from aiogram import Bot
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.bot.handlers.permissions import CREATE_ROLES
from app.bot.handlers.utils import is_valid_phone, normalize_phone
from app.core.config import get_settings
from app.db.enums import LeadStatus
from app.db.models import Lead, User
from app.db.session import async_session_factory


logger = logging.getLogger(__name__)
router = APIRouter()

MESSAGE_LIMIT = 3500


class LeadWebhookPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    external_id: UUID
    ts: datetime
    name: str | None = None
    phone: str
    message: str
    source: str | None = None
    category_id: str | None = Field(default=None, alias="categoryId")
    category_title: str | None = Field(default=None, alias="categoryTitle")
    issue_title: str | None = Field(default=None, alias="issueTitle")
    ip: str | None = None
    ua: str | None = None


def _truncate(value: str, limit: int = MESSAGE_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"


def _build_message(payload: LeadWebhookPayload, normalized_phone: str) -> str:
    name = payload.name.strip() if payload.name else "-"
    message = payload.message.strip()
    source = payload.source.strip() if payload.source else "-"
    context = " / ".join(
        item for item in [payload.category_title, payload.issue_title] if item and item.strip()
    )
    lines = [
        "📥 Новая заявка с сайта",
        f"Дата: {payload.ts.isoformat()}",
        f"Имя: {name}",
        f"Телефон: {normalized_phone}",
        f"Текст: {message}",
        f"Источник: {source}",
    ]
    if context:
        lines.append(f"Категория/проблема: {context}")
    if payload.ip:
        lines.append(f"IP: {payload.ip}")
    if payload.ua:
        lines.append(f"UA: {payload.ua}")
    return _truncate("\n".join(lines))


async def _get_ticket_managers(session) -> list[User]:
    result = await session.execute(
        select(User).where(User.role.in_(CREATE_ROLES), User.is_active.is_(True)).order_by(User.id.desc())
    )
    return list(result.scalars().all())


@router.post("/webhook/lead")
async def lead_webhook(payload: LeadWebhookPayload, request: Request) -> dict[str, bool]:
    settings = get_settings()
    if not settings.webhook_secret:
        logger.warning("[webhook:lead] rejected: webhook secret missing")
        raise HTTPException(status_code=503, detail="Webhook not configured")

    header_secret = request.headers.get("x-webhook-secret")
    if not header_secret or header_secret != settings.webhook_secret:
        logger.warning("[webhook:lead] rejected: invalid secret")
        raise HTTPException(status_code=401, detail="Unauthorized")

    normalized_phone = normalize_phone(payload.phone.strip())
    if not normalized_phone or not is_valid_phone(normalized_phone):
        logger.info("[webhook:lead] rejected: invalid phone")
        raise HTTPException(status_code=400, detail="Invalid phone")

    async with async_session_factory() as session:
        existing = await session.get(Lead, payload.external_id)
        if existing:
            logger.info("[webhook:lead] duplicate external_id=%s", payload.external_id)
            return {"ok": True, "duplicate": True}

        lead = Lead(
            id=payload.external_id,
            source=payload.source.strip() if payload.source else "site",
            client_name=payload.name.strip() if payload.name else None,
            client_phone=normalized_phone,
            problem_text=payload.message.strip(),
            status=LeadStatus.NEW_RAW,
            meta={
                "external_ts": payload.ts.isoformat(),
                "category_id": payload.category_id,
                "category_title": payload.category_title,
                "issue_title": payload.issue_title,
                "ip": payload.ip,
                "ua": payload.ua,
                "source": payload.source,
            },
            created_at=payload.ts,
            updated_at=datetime.utcnow(),
        )
        session.add(lead)
        await session.commit()

        logger.info("[webhook:lead] accepted external_id=%s", payload.external_id)

        recipients = await _get_ticket_managers(session)
        if not recipients:
            logger.info("[notify] no recipients for external_id=%s", payload.external_id)
            return {"ok": True, "duplicate": False}

        message = _build_message(payload, normalized_phone)
        async with Bot(settings.bot_token) as bot:
            for user in recipients:
                try:
                    await bot.send_message(chat_id=user.id, text=message)
                    logger.info("[notify] sent user_id=%s external_id=%s", user.id, payload.external_id)
                except Exception:  # noqa: BLE001 - log and continue
                    logger.exception(
                        "[notify] failed user_id=%s external_id=%s", user.id, payload.external_id
                    )

    return {"ok": True, "duplicate": False}
