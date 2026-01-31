from aiogram import Router
from aiogram.types import Message

router = Router()


@router.message()
async def help_handler(message: Message) -> None:
    if message.text != "ℹ️ Помощь":
        return
    await message.answer(
        "Доступные команды:\n"
        "/start — начать работу\n"
        "➕ Создать заказ — создать заказ вручную\n"
        "📋 Список заказов — посмотреть последние заявки"
    )
