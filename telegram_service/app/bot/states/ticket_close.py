from aiogram.fsm.state import State, StatesGroup


class TicketCloseStates(StatesGroup):
    revenue = State()
    expense = State()
    junior = State()
    comment = State()
    photo = State()
    confirm = State()
