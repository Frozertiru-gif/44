from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from app.bot.keyboards.main_menu import build_main_menu
from app.bot.handlers.utils import format_ticket_card
from app.db.session import async_session_factory
from app.services.ticket_service import TicketService
from app.services.user_service import UserService

router = Router()
user_service = UserService()
ticket_service = TicketService()


@router.message(CommandStart())
async def start_handler(message: Message, command: CommandObject, bot: Bot) -> None:
    async with async_session_factory() as session:
        user = await user_service.ensure_user(
            session, message.from_user.id, message.from_user.full_name if message.from_user else None
        )
        await session.commit()

    args = (command.args or "").strip()
    if args and args.startswith("ticket_"):
        ticket_id = int(args.replace("ticket_", ""))
        async with async_session_factory() as session:
            ticket = await ticket_service.get_ticket(session, ticket_id)
        if ticket:
            await message.answer(format_ticket_card(ticket))
            return

    if not user.is_active:
        await message.answer("У вас нет доступа. Обратитесь к администратору.")
        return

    menu = await build_main_menu(user.role)
    await message.answer("Добро пожаловать!", reply_markup=menu)
