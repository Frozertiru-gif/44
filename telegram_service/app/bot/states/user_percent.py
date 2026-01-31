from aiogram.fsm.state import State, StatesGroup


class UserPercentStates(StatesGroup):
    percent = State()
    confirm = State()
