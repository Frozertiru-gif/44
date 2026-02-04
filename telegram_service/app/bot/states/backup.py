from aiogram.fsm.state import State, StatesGroup


class BackupRestoreStates(StatesGroup):
    waiting_for_document = State()
    confirm_restore = State()
