from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from data.config import URL, BASE_URL


# ============================================================
# XODIM ASOSIY MENYU
# ============================================================

async def employee_main_keyboard() -> InlineKeyboardMarkup:
    """Xodim uchun asosiy menyu — web app + hisobotlar"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔓 Kirish", web_app=WebAppInfo(url=f"{URL}?action=check_in")),
            InlineKeyboardButton(text="🔒 Chiqish", web_app=WebAppInfo(url=f"{URL}?action=check_out")),
        ],
        [InlineKeyboardButton(text="📊 Hisobotlar", callback_data="my_reports")],
    ])


def edu_admin_keyboard() -> InlineKeyboardMarkup:
    """O'quv bo'limi admin uchun asosiy menyu"""
    edu_web_app_url = BASE_URL.rstrip('/') + '/students/edu-admin/web-app/'
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📋 Tinglovchi davomatini qayd qilish",
                web_app=WebAppInfo(url=edu_web_app_url)
            ),
        ],
    ])


def student_main_keyboard() -> InlineKeyboardMarkup:
    """Tinglovchi uchun asosiy menyu — web app (lokatsiya + face ID) + hisobotlar"""
    student_url = BASE_URL.rstrip('/') + '/students/web_app/'
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔓 Kirish",
                web_app=WebAppInfo(url=f"{student_url}?action=check_in")
            ),
            InlineKeyboardButton(
                text="🔒 Chiqish",
                web_app=WebAppInfo(url=f"{student_url}?action=check_out")
            ),
        ],
        [InlineKeyboardButton(text="📊 Hisobotlar", callback_data="my_reports")],
    ])


async def go_web_app() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔓 Kirish", web_app=WebAppInfo(url=f"{URL}?action=check_in")),
            InlineKeyboardButton(text="🔒 Chiqish", web_app=WebAppInfo(url=f"{URL}?action=check_out")),
        ]
    ])


# ============================================================
# TASDIQLASH KLAVIATURALARI (admin uchun)
# ============================================================

def get_user_approval_keyboard(emp_user_id: int, org_id: int, filial_id: int) -> InlineKeyboardMarkup:
    """HR admin uchun: xodimni tasdiqlash yoki rad etish"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Tasdiqlash",
                callback_data=f"approve_emp:{emp_user_id}:{org_id}:{filial_id}"
            ),
            InlineKeyboardButton(
                text="❌ Rad etish",
                callback_data=f"reject_emp:{emp_user_id}"
            ),
        ]
    ])


def get_filial_keyboard_for_employee(filials, emp_user_id: int) -> InlineKeyboardMarkup:
    """Admin xodim uchun filial tanlaydi"""
    buttons = [
        [InlineKeyboardButton(
            text=f.filial_name,
            callback_data=f"emp_filial:{f.id}:{emp_user_id}"
        )]
        for f in filials
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def generate_weekday_keyboard(selected: set) -> InlineKeyboardMarkup:
    """Hafta kunlari tanlash — eski flow (SetEmployeeForm) uchun"""
    keyboard = []
    for weekday in ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]:
        button_text = f"✅ {weekday}" if weekday in selected else weekday
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"select_weekday:{weekday}"
        )])
    keyboard.append([
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_start"),
        InlineKeyboardButton(text="⏭ Davom etish", callback_data="continue_schedule"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def generate_approve_weekday_keyboard(selected: set) -> InlineKeyboardMarkup:
    """Hafta kunlari tanlash — yangi tasdiqlash flow (ApproveEmployee) uchun"""
    keyboard = []
    for weekday in ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]:
        button_text = f"✅ {weekday}" if weekday in selected else weekday
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"awday:{weekday}"
        )])
    keyboard.append([
        InlineKeyboardButton(text="⏭ Davom etish", callback_data="awday_done"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_more_schedule_keyboard() -> InlineKeyboardMarkup:
    """Yana jadval qo'shish yoki tugatish"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Yana jadval qo'shish", callback_data="more_sched"),
            InlineKeyboardButton(text="✅ Tugatish", callback_data="finish_sched"),
        ]
    ])


def get_schedule_selection_keyboard(schedules: list, selected_ids: set) -> InlineKeyboardMarkup:
    """Tayyor jadvallar ro'yxatidan tanlash"""
    buttons = []
    for s in schedules:
        mark = "✅ " if s['id'] in selected_ids else ""
        buttons.append([InlineKeyboardButton(
            text=f"{mark}{s['label']}",
            callback_data=f"asel:{s['id']}"
        )])
    if selected_ids:
        buttons.append([InlineKeyboardButton(
            text="✔️ Tasdiqlash",
            callback_data="asel_done"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================
# TASHKILOT / FILIAL TANLASH KLAVIATURALARI
# ============================================================

async def get_organization_selection_keyboard() -> InlineKeyboardMarkup:
    from utils.db_api.database import get_organizations
    orgs = await get_organizations()
    if not orgs:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Hozircha tashkilotlar yo'q", callback_data="none")]
        ])
    buttons = [
        [InlineKeyboardButton(text=o["name"], callback_data=f"org_{o['id']}")]
        for o in orgs
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_filial_selection_keyboard() -> InlineKeyboardMarkup:
    from utils.db_api.database import get_all_filials
    filiallar = await get_all_filials()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f.filial_name, callback_data=f"filial_{f.id}")]
        for f in filiallar
    ])


async def get_filial_selection_keyboard_by_org(org_id: int) -> InlineKeyboardMarkup:
    from utils.db_api.database import get_filials_by_org
    filials = await get_filials_by_org(org_id)
    if not filials:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bu tashkilotda filial topilmadi", callback_data="none")]
        ])
    buttons = [
        [InlineKeyboardButton(text=f["filial_name"], callback_data=f"filial_{f['id']}")]
        for f in filials
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================
# STATISTIKA KLAVIATURALARI (eski)
# ============================================================

def months_keyboard(months: list) -> InlineKeyboardMarkup:
    """Oylar ro'yxati klaviaturasi (eski stats flow)"""
    buttons = [
        [InlineKeyboardButton(
            text=m['month_name'],
            callback_data=f"stats_{m['year']}_{m['month']}"
        )]
        for m in months
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================
# YANGI HISOBOT KLAVIATURALARI
# ============================================================

def reports_menu_keyboard() -> InlineKeyboardMarkup:
    """Hisobot asosiy menyu klaviaturasi"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Kunlik", callback_data="rep_daily_months"),
            InlineKeyboardButton(text="🗓 Sana bo'yicha", callback_data="rep_daterange"),
        ],
        [InlineKeyboardButton(text="⏰ Kechikkan kunlarim", callback_data="rep_late_months")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")],
    ])


def report_months_keyboard(months: list, prefix: str) -> InlineKeyboardMarkup:
    """Hisobot uchun oy tanlash klaviaturasi"""
    buttons = [
        [InlineKeyboardButton(
            text=m['label'],
            callback_data=f"{prefix}_{m['year']}_{m['month']}"
        )]
        for m in months
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Hisobotlar", callback_data="my_reports")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================
# ADMIN MENYU (inline)
# ============================================================

async def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin uchun inline menyu (agar kerak bo'lsa)"""
    from keyboards.inline.menu_button import admin_menu_keyboard as reply_menu
    return await reply_menu()
