import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.bot.handlers import backup, finance, help as help_handler
from app.bot.handlers import issues, junior_links, junior_tickets, project_settings, request_chat, start, ticket_create, ticket_execution, ticket_list, users
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.diagnostics import log_database_context
from app.services.backup_service import (
    BackupError,
    BackupNotFound,
    BackupOperationInProgress,
    BackupOperationLock,
    BackupService,
)


logger = logging.getLogger(__name__)


def _parse_backup_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw_value = value.strip()
    if raw_value.endswith("Z"):
        raw_value = f"{raw_value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def run_daily_backup(
    *,
    bot: Bot,
    backup_service: BackupService,
    lock: BackupOperationLock,
    chat_id: int,
    reason: str,
) -> None:
    logger.info("Daily backup job fired", extra={"reason": reason})
    try:
        async with lock.acquire():
            await backup_service.run_backup_script()
            await backup_service.send_latest_to_backup_chat(bot)
        logger.info("Daily backup job success", extra={"reason": reason})
    except BackupOperationInProgress:
        logger.warning("Daily backup job skipped because another backup is running", extra={"reason": reason})
    except Exception:  # noqa: BLE001
        logger.exception("Daily backup job failed", extra={"reason": reason})
        try:
            await bot.send_message(chat_id=chat_id, text="Автобэкап не выполнен, подробности в логах.")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to send autobackup failure notification")


async def run_catchup_backup(
    *,
    bot: Bot,
    backup_service: BackupService,
    lock: BackupOperationLock,
    chat_id: int,
) -> None:
    try:
        metadata = backup_service.get_latest_metadata()
    except BackupNotFound:
        logger.info("No backups found; running catch-up backup.")
        await run_daily_backup(
            bot=bot,
            backup_service=backup_service,
            lock=lock,
            chat_id=chat_id,
            reason="catchup_missing",
        )
        return
    except BackupError as exc:
        logger.warning("Failed to read backup metadata for catch-up: %s", exc)
        return

    last_backup_at = _parse_backup_datetime(metadata.created_at)
    if last_backup_at is None:
        logger.warning("Failed to parse last backup timestamp; skipping catch-up.")
        return
    if datetime.now(timezone.utc) - last_backup_at <= timedelta(hours=24):
        logger.info("Catch-up backup not required; last backup is recent.")
        return

    logger.info("Last backup is older than 24 hours; running catch-up backup.")
    await run_daily_backup(
        bot=bot,
        backup_service=backup_service,
        lock=lock,
        chat_id=chat_id,
        reason="catchup_stale",
    )


async def main() -> None:
    configure_logging()
    settings = get_settings()
    logger.info("SYS_ADMIN_IDS: %s", sorted(settings.sys_admin_id_set()))
    logger.info("SUPER_ADMIN: %s", [settings.super_admin] if settings.super_admin is not None else [])
    await log_database_context(logger)
    bot = Bot(settings.bot_token)
    dispatcher = Dispatcher()
    backup_service = BackupService(settings)
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    daily_lock = BackupOperationLock(backup_dir / ".daily_backup.lock")

    dispatcher.include_router(start.router)
    dispatcher.include_router(ticket_create.router)
    dispatcher.include_router(ticket_execution.router)
    dispatcher.include_router(ticket_list.router)
    dispatcher.include_router(request_chat.router)
    dispatcher.include_router(users.router)
    dispatcher.include_router(backup.router)
    dispatcher.include_router(junior_links.router)
    dispatcher.include_router(junior_tickets.router)
    dispatcher.include_router(finance.router)
    dispatcher.include_router(issues.router)
    dispatcher.include_router(project_settings.router)
    dispatcher.include_router(help_handler.router)

    scheduler = AsyncIOScheduler(timezone="UTC")
    job = scheduler.add_job(
        run_daily_backup,
        CronTrigger(hour=3, minute=15, timezone="UTC"),
        kwargs={
            "bot": bot,
            "backup_service": backup_service,
            "lock": daily_lock,
            "chat_id": settings.backup_chat_id,
            "reason": "scheduled",
        },
        id="daily_backup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Daily backup scheduler started, next_run_time=%s", job.next_run_time)
    asyncio.create_task(
        run_catchup_backup(
            bot=bot,
            backup_service=backup_service,
            lock=daily_lock,
            chat_id=settings.backup_chat_id,
        )
    )

    config = uvicorn.Config(
        "app.webhook.app:app",
        host="0.0.0.0",
        port=settings.webhook_port,
        log_level="info",
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    polling_task = asyncio.create_task(dispatcher.start_polling(bot))
    server_task = asyncio.create_task(server.serve())

    try:
        done, pending = await asyncio.wait(
            {polling_task, server_task},
            return_when=asyncio.FIRST_EXCEPTION,
        )
        for task in done:
            if task.exception():
                raise task.exception()
    finally:
        scheduler.shutdown(wait=False)
        server.should_exit = True
        polling_task.cancel()
        await asyncio.gather(polling_task, server_task, return_exceptions=True)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
