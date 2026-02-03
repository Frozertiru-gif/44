import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher

from app.bot.handlers import finance, help as help_handler
from app.bot.handlers import issues, junior_links, junior_tickets, project_settings, request_chat, start, ticket_create, ticket_execution, ticket_list, users
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.diagnostics import log_database_context


logger = logging.getLogger(__name__)


async def main() -> None:
    configure_logging()
    settings = get_settings()
    logger.info("SYS_ADMIN_IDS: %s", sorted(settings.sys_admin_id_set()))
    logger.info("SUPER_ADMIN: %s", [settings.super_admin] if settings.super_admin is not None else [])
    await log_database_context(logger)
    bot = Bot(settings.bot_token)
    dispatcher = Dispatcher()

    dispatcher.include_router(start.router)
    dispatcher.include_router(ticket_create.router)
    dispatcher.include_router(ticket_execution.router)
    dispatcher.include_router(ticket_list.router)
    dispatcher.include_router(request_chat.router)
    dispatcher.include_router(users.router)
    dispatcher.include_router(junior_links.router)
    dispatcher.include_router(junior_tickets.router)
    dispatcher.include_router(finance.router)
    dispatcher.include_router(issues.router)
    dispatcher.include_router(project_settings.router)
    dispatcher.include_router(help_handler.router)

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
        server.should_exit = True
        polling_task.cancel()
        await asyncio.gather(polling_task, server_task, return_exceptions=True)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
