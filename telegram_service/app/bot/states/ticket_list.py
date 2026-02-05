from aiogram.fsm.state import State, StatesGroup


class AdminSearchStates(StatesGroup):
    wait_query = State()
    results = State()
