import asyncio

from aiogram import Bot, Dispatcher

from app.bot.handlers import help as help_handler
from app.bot.handlers import request_chat, start, ticket_create, ticket_execution, ticket_list, users
from app.core.config import get_settings
from app.core.logging import configure_logging


async def main() -> None:
    configure_logging()
    settings = get_settings()
    bot = Bot(settings.bot_token)
    dispatcher = Dispatcher()

    dispatcher.include_router(start.router)
    dispatcher.include_router(ticket_create.router)
    dispatcher.include_router(ticket_execution.router)
    dispatcher.include_router(ticket_list.router)
    dispatcher.include_router(request_chat.router)
    dispatcher.include_router(users.router)
    dispatcher.include_router(help_handler.router)

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
