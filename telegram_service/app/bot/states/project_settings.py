from aiogram.fsm.state import State, StatesGroup


class ProjectSettingsStates(StatesGroup):
    field = State()
    value = State()
