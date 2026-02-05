from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app.bot.handlers.utils import ticket_display_id
from app.db.enums import TransferStatus, UserRole
from app.db.session import async_session_factory
from app.services.audit_service import AuditService
from app.services.issue_service import IssueService
from app.services.project_settings_service import ProjectSettingsService
from app.services.user_service import UserService

router = Router()
issue_service = IssueService()
user_service = UserService()
audit_service = AuditService()
project_settings_service = ProjectSettingsService()


@router.message(F.text == "📍 Проблемы")
async def issues_dashboard(message: Message) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            message.from_user.id,
            message.from_user.full_name if message.from_user else None,
            message.from_user.username if message.from_user else None,
        )
        await session.commit()
        if not user.is_active or user.role not in {UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN}:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="issues",
                entity_id=None,
                payload={"reason": "ISSUES_DASHBOARD"},
            )
            await session.commit()
            await message.answer("У вас нет доступа к проблемам.")
            return

        pending_days = await project_settings_service.get_threshold(session, "transfer_pending_days", default=3)
        overdue = await issue_service.list_transfer_overdue(session, days=pending_days)
        zero_profit = await issue_service.list_zero_profit(session)
        repeat_phones = await issue_service.list_repeat_phones(session)
        pending_transfers = await issue_service.list_master_pending_transfers(session)

    lines = ["📍 Проблемы"]

    if overdue:
        lines.append(f"\n🔔 Закрытые без подтверждения перевода > {pending_days} дн.")
        for ticket in overdue:
            status = ticket.transfer_status.value if ticket.transfer_status else TransferStatus.NOT_SENT.value
            lines.append(f"- #{ticket_display_id(ticket)} статус перевода: {status}")
    else:
        lines.append(f"\n🔔 Нет просроченных подтверждений (> {pending_days} дн.)")

    if zero_profit:
        lines.append("\n⚠️ Заказы с нулевой прибылью")
        for ticket in zero_profit:
            lines.append(f"- #{ticket_display_id(ticket)} клиент: {ticket.client_phone}")
    else:
        lines.append("\n⚠️ Заказов с нулевой прибылью нет")

    if repeat_phones:
        lines.append("\n📞 Частые повторы по телефону")
        for phone, count in repeat_phones:
            lines.append(f"- {phone}: {count} заказов")
    else:
        lines.append("\n📞 Повторов по телефонам нет")

    if pending_transfers:
        lines.append("\n💸 Мастера с большим долгом перевода")
        for user, amount in pending_transfers:
            label = user.display_name if user and user.display_name else f"ID {user.id}" if user else "Неизвестно"
            lines.append(f"- {label}: {amount}")
    else:
        lines.append("\n💸 Нет мастеров с долгом перевода")

    await message.answer("\n".join(lines))
