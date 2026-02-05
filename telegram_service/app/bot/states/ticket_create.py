from aiogram.fsm.state import State, StatesGroup


class TicketCreateStates(StatesGroup):
    category = State()
    phone = State()
    client_address = State()
    address_details = State()
    repeat_confirm = State()
    schedule_choice = State()
    schedule_time = State()
    client_name = State()
    client_age = State()
    problem = State()
    special_note = State()
    special_note_custom = State()
    ad_source = State()
    confirm = State()
