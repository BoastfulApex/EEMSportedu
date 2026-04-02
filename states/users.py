from aiogram.fsm.state import State, StatesGroup


class UserForm(StatesGroup):
    go_reg = State()


class EmployeeRegistration(StatesGroup):
    waiting_for_photo = State()


class StudentGroupSelect(StatesGroup):
    selecting = State()   # tinglovchi o'z ismini tanlayapti


class ReportDateRange(StatesGroup):
    waiting_start = State()   # foydalanuvchi boshlanish sanasini kiritadi
    waiting_end   = State()   # foydalanuvchi tugash sanasini kiritadi
