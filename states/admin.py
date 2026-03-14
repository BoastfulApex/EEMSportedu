from aiogram.fsm.state import State, StatesGroup


class EmployeeForm(StatesGroup):
    get_id = State()
    get_name = State()


class AddLocation(StatesGroup):
    waiting_for_location = State()


class ApproveEmployee(StatesGroup):
    """Xodimni tasdiqlash jarayoni uchun holатlar"""
    selecting_filial = State()         # Admin filial tanlaydi
    selecting_weekdays = State()       # Admin hafta kunlarini tanlaydi
    waiting_for_time_range = State()   # Admin vaqt kiritadi (09:00 - 18:00)
    confirm_more_schedules = State()   # Yana jadval qo'shish? (Ha / Yo'q)


class SetEmployeeForm(StatesGroup):
    waiting_for_time_range = State()
    select_weekdays = State()
    confirm = State()


class ChartsForm(StatesGroup):
    get_date = State()
