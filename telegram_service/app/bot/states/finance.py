from aiogram.fsm.state import State, StatesGroup


class FinanceStates(StatesGroup):
    period_from = State()
    period_to = State()
    transaction_amount = State()
    transaction_category = State()
    transaction_comment = State()
    transaction_date = State()
    share_percent = State()
