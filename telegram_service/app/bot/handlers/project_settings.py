from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.project_settings import project_settings_keyboard
from app.bot.states.project_settings import ProjectSettingsStates
from app.db.enums import UserRole
from app.db.session import async_session_factory
from app.services.audit_service import AuditService
from app.services.project_settings_service import ProjectSettingsService
from app.services.user_service import UserService

router = Router()
user_service = UserService()
project_settings_service = ProjectSettingsService()
audit_service = AuditService()


def _format_thresholds(thresholds: dict | None) -> str:
    if not thresholds:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in thresholds.items())


def _parse_thresholds(raw: str) -> dict[str, int] | None:
    cleaned = raw.strip()
    if not cleaned:
        return {}
    items = [item.strip() for item in cleaned.split(",") if item.strip()]
    thresholds: dict[str, int] = {}
    for item in items:
        if "=" not in item:
            return None
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            return None
        try:
            thresholds[key] = int(value)
        except ValueError:
            return None
    return thresholds


@router.message(F.text == "⚙️ Настройки проекта")
async def project_settings_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session, message.from_user.id, message.from_user.full_name if message.from_user else None
        )
        await session.commit()
        if not user.is_active or user.role not in {UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN}:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="project_settings",
                entity_id=None,
                payload={"reason": "VIEW_SETTINGS"},
            )
            await session.commit()
            await message.answer("У вас нет доступа к настройкам проекта.")
            return

        settings = await project_settings_service.get_settings(session)

    text = (
        "⚙️ Настройки проекта\n"
        f"requests_chat_id: {settings.requests_chat_id or '-'}\n"
        f"currency: {settings.currency}\n"
        f"rounding_mode: {settings.rounding_mode}\n"
        f"thresholds: {_format_thresholds(settings.thresholds)}"
    )
    await message.answer(text, reply_markup=project_settings_keyboard())


@router.callback_query(F.data.startswith("settings_field:"))
async def project_settings_field(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    if field not in {"requests_chat_id", "currency", "rounding_mode", "thresholds"}:
        await callback.answer("Неизвестное поле", show_alert=True)
        return
    await state.clear()
    await state.update_data(field=field)
    await state.set_state(ProjectSettingsStates.value)
    prompt = {
        "requests_chat_id": "Введите chat_id или 'none' для очистки:",
        "currency": "Введите валюту (например, RUB):",
        "rounding_mode": "Введите режим округления (например, HALF_UP):",
        "thresholds": "Введите thresholds в формате key=value, через запятую:",
    }[field]
    await callback.message.answer(prompt)
    await callback.answer()


@router.message(ProjectSettingsStates.value)
async def project_settings_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("field")
    if field not in {"requests_chat_id", "currency", "rounding_mode", "thresholds"}:
        await message.answer("Сессия устарела.")
        await state.clear()
        return

    raw = (message.text or "").strip()
    updates = {}
    if field == "requests_chat_id":
        if raw.lower() in {"none", "null", "-"}:
            updates["requests_chat_id"] = None
        else:
            try:
                updates["requests_chat_id"] = int(raw)
            except ValueError:
                await message.answer("Введите числовой chat_id или 'none'.")
                return
    elif field == "currency":
        if not raw:
            await message.answer("Введите валюту.")
            return
        updates["currency"] = raw.upper()
    elif field == "rounding_mode":
        if not raw:
            await message.answer("Введите режим округления.")
            return
        updates["rounding_mode"] = raw.upper()
    elif field == "thresholds":
        parsed = _parse_thresholds(raw)
        if parsed is None:
            await message.answer("Введите thresholds в формате key=value, через запятую.")
            return
        updates["thresholds"] = parsed

    async with async_session_factory() as session:
        actor = await user_service.ensure_user(
            session, message.from_user.id, message.from_user.full_name if message.from_user else None
        )
        if not actor.is_active or actor.role not in {UserRole.SUPER_ADMIN, UserRole.SYS_ADMIN}:
            await audit_service.log_audit_event(
                session,
                actor_id=actor.id,
                action="PERMISSION_DENIED",
                entity_type="project_settings",
                entity_id=None,
                payload={"reason": "UPDATE_SETTINGS"},
            )
            await session.commit()
            await message.answer("У вас нет доступа.")
            await state.clear()
            return

        settings = await project_settings_service.get_settings(session)
        before = {field: getattr(settings, field)}
        await project_settings_service.update_settings(session, settings, updates=updates)
        await audit_service.log_audit_event(
            session,
            actor_id=actor.id,
            action="PROJECT_SETTINGS_UPDATED",
            entity_type="project_settings",
            entity_id=settings.id,
            payload={"before": before, "after": updates},
        )
        await session.commit()

    await state.clear()
    await message.answer("Настройки обновлены.")
