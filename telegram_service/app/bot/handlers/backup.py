from __future__ import annotations

import logging
from pathlib import Path

from aiogram import F, Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.permissions import BACKUP_ADMIN_ROLES
from app.bot.keyboards.backup import (
    backup_menu_keyboard,
    backup_restore_confirm_keyboard,
    backup_restore_file_confirm_keyboard,
)
from app.bot.states.backup import BackupRestoreStates
from app.core.config import get_settings
from app.db.session import async_session_factory
from app.services.audit_service import AuditService
from app.services.backup_service import (
    MAX_BACKUP_SIZE_BYTES,
    BackupError,
    BackupNotFound,
    BackupOperationInProgress,
    BackupService,
)
from app.services.user_service import UserService

router = Router()
user_service = UserService()
audit_service = AuditService()
backup_service = BackupService(get_settings())
logger = logging.getLogger(__name__)


def _format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    units = ["KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        size /= 1024
        if size < 1024:
            return f"{size:.2f} {unit}"
    return f"{size:.2f} PB"


async def _ensure_admin(message: Message) -> tuple[bool, int | None]:
    if message.chat.type != "private":
        await message.answer("Операции бэкапа доступны только в личном чате.")
        return False, None
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            message.from_user.id,
            message.from_user.full_name if message.from_user else None,
            message.from_user.username if message.from_user else None,
        )
        await session.commit()
        if not user.is_active or user.role not in BACKUP_ADMIN_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="backup",
                entity_id=None,
                payload={"reason": "BACKUP_MENU"},
            )
            await session.commit()
            await message.answer("У вас нет доступа к резервным копиям.")
            return False, user.id
    return True, user.id


async def _ensure_admin_callback(callback: CallbackQuery) -> tuple[bool, int | None]:
    message = callback.message
    if message is None or message.chat.type != "private":
        await callback.answer("Доступно только в личном чате.", show_alert=True)
        return False, None
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session,
            callback.from_user.id,
            callback.from_user.full_name if callback.from_user else None,
            callback.from_user.username if callback.from_user else None,
        )
        await session.commit()
        if not user.is_active or user.role not in BACKUP_ADMIN_ROLES:
            await audit_service.log_audit_event(
                session,
                actor_id=user.id,
                action="PERMISSION_DENIED",
                entity_type="backup",
                entity_id=None,
                payload={"reason": "BACKUP_ACTION"},
            )
            await session.commit()
            await callback.answer("Нет доступа", show_alert=True)
            return False, user.id
    return True, user.id


@router.message(F.text == "🛡 Резервные копии")
async def backup_menu(message: Message) -> None:
    allowed, _ = await _ensure_admin(message)
    if not allowed:
        return
    await message.answer("🛡 Резервные копии", reply_markup=backup_menu_keyboard())


@router.callback_query(F.data == "backup:status")
async def backup_status(callback: CallbackQuery) -> None:
    allowed, actor_id = await _ensure_admin_callback(callback)
    if not allowed:
        return
    await callback.answer()
    try:
        metadata = backup_service.get_latest_metadata()
        text = (
            "📦 Последний бэкап\n"
            f"Создан: {metadata.created_at}\n"
            f"Файл: {metadata.filename}\n"
            f"Размер: {_format_bytes(metadata.size_bytes)}\n"
            f"SHA256: {metadata.sha256}"
        )
    except BackupNotFound:
        text = "Бэкапы не найдены."
    except BackupError as exc:
        text = f"Ошибка получения статуса: {exc}"

    async with async_session_factory() as session:
        if actor_id is not None:
            await audit_service.log_audit_event(
                session,
                actor_id=actor_id,
                action="BACKUP_STATUS_VIEWED",
                entity_type="backup",
                entity_id=None,
                payload=None,
            )
            await session.commit()
    await callback.message.answer(text)


@router.callback_query(F.data == "backup:run")
async def backup_run(callback: CallbackQuery) -> None:
    allowed, actor_id = await _ensure_admin_callback(callback)
    if not allowed:
        return
    await callback.answer()
    await callback.message.answer("⏳ Запускаю бэкап...")
    try:
        metadata = await backup_service.run_backup_script()
        text = (
            "✅ Бэкап создан\n"
            f"Создан: {metadata.created_at}\n"
            f"Файл: {metadata.filename}\n"
            f"Размер: {_format_bytes(metadata.size_bytes)}\n"
            f"SHA256: {metadata.sha256}"
        )
        action = "BACKUP_CREATED"
        payload = {"filename": metadata.filename, "sha256": metadata.sha256}
    except BackupOperationInProgress:
        text = "Сейчас уже выполняется операция бэкапа или восстановления."
        action = "BACKUP_CREATE_SKIPPED"
        payload = {"reason": "BUSY"}
    except BackupError as exc:
        text = f"Ошибка создания бэкапа: {exc}"
        action = "BACKUP_CREATE_FAILED"
        payload = {"error": str(exc)}

    async with async_session_factory() as session:
        if actor_id is not None:
            await audit_service.log_audit_event(
                session,
                actor_id=actor_id,
                action=action,
                entity_type="backup",
                entity_id=None,
                payload=payload,
            )
            await session.commit()
    await callback.message.answer(text)


@router.callback_query(F.data == "backup:send")
async def backup_send(callback: CallbackQuery, bot: Bot) -> None:
    allowed, actor_id = await _ensure_admin_callback(callback)
    if not allowed:
        return
    await callback.answer()
    await callback.message.answer("⏳ Отправляю бэкап в backup-чат...")
    try:
        metadata = await backup_service.send_latest_to_backup_chat(bot)
        text = (
            "📤 Бэкап отправлен\n"
            f"Создан: {metadata.created_at}\n"
            f"Файл: {metadata.filename}\n"
            f"Размер: {_format_bytes(metadata.size_bytes)}\n"
            f"SHA256: {metadata.sha256}"
        )
        action = "BACKUP_SENT"
        payload = {
            "filename": metadata.filename,
            "chat_id": metadata.tg.get("chat_id") if metadata.tg else None,
            "message_id": metadata.tg.get("message_id") if metadata.tg else None,
        }
    except BackupNotFound:
        text = "Нет бэкапов для отправки."
        action = "BACKUP_SEND_FAILED"
        payload = {"error": "NOT_FOUND"}
    except BackupError as exc:
        text = f"Ошибка отправки бэкапа: {exc}"
        action = "BACKUP_SEND_FAILED"
        payload = {"error": str(exc)}

    async with async_session_factory() as session:
        if actor_id is not None:
            await audit_service.log_audit_event(
                session,
                actor_id=actor_id,
                action=action,
                entity_type="backup",
                entity_id=None,
                payload=payload,
            )
            await session.commit()
    await callback.message.answer(text)


@router.callback_query(F.data == "backup:restore_prompt")
async def backup_restore_prompt(callback: CallbackQuery) -> None:
    allowed, actor_id = await _ensure_admin_callback(callback)
    if not allowed:
        return
    await callback.answer()
    warning = (
        "⚠️ Восстановление полностью перезапишет базу данных.\n"
        "Убедитесь, что это действительно необходимо.\n\n"
        "Подтвердите восстановление:"
    )
    await callback.message.answer(warning, reply_markup=backup_restore_confirm_keyboard(actor_id or 0))


@router.callback_query(F.data.startswith("backup:restore_confirm:"))
async def backup_restore_confirm(callback: CallbackQuery) -> None:
    allowed, actor_id = await _ensure_admin_callback(callback)
    if not allowed:
        return
    callback_actor = int(callback.data.split(":", 2)[2])
    if actor_id is None or callback_actor != actor_id:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("⏳ Восстанавливаю базу данных...")
    if actor_id is not None:
        try:
            async with async_session_factory() as session:
                await audit_service.log_audit_event(
                    session,
                    actor_id=actor_id,
                    action="BACKUP_RESTORE_STARTED",
                    entity_type="backup",
                    entity_id=None,
                    payload={"source": "latest_local"},
                )
                await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to write backup restore started audit event")

    try:
        await backup_service.restore_latest_local_backup()
        text = "✅ Восстановление завершено."
        action = "BACKUP_RESTORE_COMPLETED"
        payload = {"source": "latest_local"}
    except BackupOperationInProgress:
        text = "Сейчас уже выполняется операция бэкапа или восстановления."
        action = "BACKUP_RESTORE_SKIPPED"
        payload = {"reason": "BUSY"}
    except BackupError as exc:
        text = f"Ошибка восстановления: {exc}"
        action = "BACKUP_RESTORE_FAILED"
        payload = {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected restore error")
        text = "Неожиданная ошибка восстановления. Подробности в логах."
        action = "BACKUP_RESTORE_FAILED"
        payload = {"error": "UNEXPECTED"}

    if actor_id is not None:
        logger.info(
            "Backup restore finished",
            extra={"actor_id": actor_id, "action": action, "payload": payload},
        )
    try:
        backup_service.append_restore_outcome(
            f"actor_id={actor_id} action={action} payload={payload}"
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to write restore outcome log")
    await callback.message.answer(text)


@router.callback_query(F.data == "backup:restore_cancel")
async def backup_restore_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.answer("Восстановление отменено.")


@router.callback_query(F.data == "backup:restore_file_prompt")
async def backup_restore_file_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    allowed, _ = await _ensure_admin_callback(callback)
    if not allowed:
        return
    await callback.answer()
    await state.clear()
    await state.set_state(BackupRestoreStates.waiting_for_document)
    await callback.message.answer("Пришлите .dump.gpg документом.")


@router.message(BackupRestoreStates.waiting_for_document, F.document)
async def backup_restore_file_receive(message: Message, state: FSMContext, bot: Bot) -> None:
    allowed, actor_id = await _ensure_admin(message)
    if not allowed:
        return
    document = message.document
    if document is None:
        await message.answer("Пришлите файл .dump.gpg документом.")
        return
    filename = (document.file_name or "").strip()
    if not filename.lower().endswith(".dump.gpg"):
        await message.answer("Файл должен иметь расширение .dump.gpg. Пришлите файл заново.")
        return
    if document.file_size and document.file_size > MAX_BACKUP_SIZE_BYTES:
        await message.answer("Размер файла превышает допустимый лимит.")
        return
    dest_path = backup_service.build_import_path(filename)
    try:
        await backup_service.download_backup_from_file_id(bot, document.file_id, dest_path)
    except BackupError as exc:
        await message.answer(f"Ошибка получения файла: {exc}")
        return

    await state.update_data(restore_file_path=str(dest_path), actor_id=actor_id)
    await state.set_state(BackupRestoreStates.confirm_restore)
    await message.answer(
        "Файл получен, восстановление перезапишет БД. Подтвердить?",
        reply_markup=backup_restore_file_confirm_keyboard(actor_id or 0),
    )


@router.message(BackupRestoreStates.waiting_for_document)
async def backup_restore_file_invalid(message: Message) -> None:
    await message.answer("Пришлите .dump.gpg документом.")


@router.callback_query(F.data.startswith("backup:restore_file_confirm:"))
async def backup_restore_file_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    allowed, actor_id = await _ensure_admin_callback(callback)
    if not allowed:
        return
    callback_actor = int(callback.data.split(":", 2)[2])
    if actor_id is None or callback_actor != actor_id:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    data = await state.get_data()
    restore_path = data.get("restore_file_path")
    await callback.answer()
    await callback.message.answer("⏳ Восстанавливаю базу данных...")

    if not restore_path:
        await callback.message.answer("Файл для восстановления не найден. Пришлите файл заново.")
        await state.clear()
        return
    if actor_id is not None:
        try:
            async with async_session_factory() as session:
                await audit_service.log_audit_event(
                    session,
                    actor_id=actor_id,
                    action="BACKUP_RESTORE_STARTED",
                    entity_type="backup",
                    entity_id=None,
                    payload={"source": "uploaded_file"},
                )
                await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to write backup restore started audit event")

    try:
        await backup_service.restore_from_backup_file(Path(restore_path))
        text = "✅ Восстановление завершено."
        action = "BACKUP_RESTORE_COMPLETED"
        payload = {"source": "uploaded_file", "path": restore_path}
    except BackupOperationInProgress:
        text = "Сейчас уже выполняется операция бэкапа или восстановления."
        action = "BACKUP_RESTORE_SKIPPED"
        payload = {"reason": "BUSY"}
    except BackupError as exc:
        text = f"Ошибка восстановления: {exc}"
        action = "BACKUP_RESTORE_FAILED"
        payload = {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected restore error")
        text = "Неожиданная ошибка восстановления. Подробности в логах."
        action = "BACKUP_RESTORE_FAILED"
        payload = {"error": "UNEXPECTED"}

    if actor_id is not None:
        logger.info(
            "Backup restore finished",
            extra={"actor_id": actor_id, "action": action, "payload": payload},
        )
    try:
        backup_service.append_restore_outcome(
            f"actor_id={actor_id} action={action} payload={payload}"
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to write restore outcome log")
    await state.clear()
    await callback.message.answer(text)
