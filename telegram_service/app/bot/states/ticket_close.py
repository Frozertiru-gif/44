from aiogram.fsm.state import State, StatesGroup


class TicketCloseStates(StatesGroup):
    revenue = State()
    expense = State()
    confirm = State()
