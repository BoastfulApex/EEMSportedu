from aiogram.fsm.state import State, StatesGroup


class UserForm(StatesGroup):
    go_reg = State()


class EmployeeRegistration(StatesGroup):
    waiting_for_photo = State()


class StudentGroupSelect(StatesGroup):
    selecting = State()   # tinglovchi o'z ismini tanlayapti


class StudentPhotoUpload(StatesGroup):
    waiting_for_photo = State()   # yangi ro'yxatdan o'tgan yoki rasmi yo'q student


class StudentCheckState(StatesGroup):
    waiting_for_photo = State()   # foto kutilmoqda (check_in yoki check_out)


class ReportDateRange(StatesGroup):
    waiting_start = State()   # foydalanuvchi boshlanish sanasini kiritadi
    waiting_end   = State()   # foydalanuvchi tugash sanasini kiritadi


class EduAdminAttendance(StatesGroup):
    waiting_for_photo = State()   # edu_admin tinglovchi rasmini yuborishi kutilmoqda


class EmployeeNameInput(StatesGroup):
    waiting_for_name = State()   # xodim ism-familiyasini kiritishi kutilmoqda


class EduStudentReg(StatesGroup):
    waiting_for_photo = State()   # edu admin tinglovchi rasmi kutilmoqda


class StudentLoginAuth(StatesGroup):
    waiting_for_login    = State()   # tinglovchi loginini kiritmoqda
    waiting_for_password = State()   # tinglovchi parolini kiritmoqda
