from aiogram.fsm.state import State, StatesGroup


class EmployeeForm(StatesGroup):
    get_id = State()
    get_name = State()


class AddLocation(StatesGroup):
    waiting_for_location = State()


class ApproveEmployee(StatesGroup):
    """Xodimni tasdiqlash jarayoni uchun holatlar"""
    selecting_filial = State()         # (eski — ishlatilmaydi)
    selecting_schedule = State()       # Admin tayyor jadval tanlaydi
    selecting_weekdays = State()       # (eski — ishlatilmaydi)
    waiting_for_time_range = State()   # (eski — ishlatilmaydi)
    confirm_more_schedules = State()   # (eski — ishlatilmaydi)


class SetEmployeeForm(StatesGroup):
    waiting_for_time_range = State()
    select_weekdays = State()
    confirm = State()


class ChartsForm(StatesGroup):
    get_date = State()
