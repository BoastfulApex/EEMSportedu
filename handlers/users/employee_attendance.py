"""
Xodim — o'z filialidagi xodimlar va tinglovchilar davomatini qayd qilish.

Flow (xodimlar):
  "👥 Xodimlar davomati" → filialdagi xodimlar ro'yxati → kirish/chiqish WebApp

Flow (tinglovchilar):
  "🎓 Tinglovchilar davomati" → filialdagi guruhlar ro'yxati → tinglovchilar → WebApp
"""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
)

from loader import dp
from data.config import BASE_URL
from utils.db_api.database import (
    get_employees_for_employee,
    get_employees_for_hr_admin,
    get_active_groups_for_employee,
    get_active_groups_for_edu_admin,
    get_all_students_in_group,
    get_employee_by_telegram_id,
)

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)

_HR_WEB_APP_URL = BASE_URL.rstrip('/') + '/web_app/hr-admin/web-app/'
_EDU_WEB_APP_URL = BASE_URL.rstrip('/') + '/students/edu-admin/web-app/'

_BACK_EMP_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Xodimlar", callback_data="emp_attend_list")]
])
_BACK_STU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Guruhlar", callback_data="emp_stu_groups")]
])


# ─────────────────────────────────────────────────────────────
# XODIMLAR DAVOMATI
# ─────────────────────────────────────────────────────────────

@router.message(F.text == "👥 Xodimlar davomati", StateFilter(None))
async def emp_show_employees(message: Message):
    await _send_emp_list(message.from_user.id, message.answer)


@router.callback_query(F.data == "emp_attend_list")
async def emp_attend_list_cb(callback: CallbackQuery):
    await _send_emp_list(callback.from_user.id, callback.message.edit_text)
    await callback.answer()


async def _send_emp_list(user_id: int, send_fn):
    employees = await get_employees_for_employee(user_id)
    if not employees:
        employees = await get_employees_for_hr_admin(user_id)

    if not employees:
        await send_fn(
            "📭 <b>Filialda xodimlar topilmadi.</b>",
            parse_mode="HTML",
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"👤 {e['name']}",
            web_app=WebAppInfo(url=f"{_HR_WEB_APP_URL}?employee_telegram_id={e['telegram_user_id']}")
        )]
        for e in employees
    ]
    await send_fn(
        f"👥 <b>Xodimni tanlang</b>\n\nJami: {len(employees)} ta xodim",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


# ─────────────────────────────────────────────────────────────
# TINGLOVCHILAR DAVOMATI
# ─────────────────────────────────────────────────────────────

@router.message(F.text == "🎓 Tinglovchilar davomati", StateFilter(None))
async def emp_show_groups(message: Message):
    await _send_stu_groups(message.from_user.id, message.answer)


@router.callback_query(F.data == "emp_stu_groups")
async def emp_stu_groups_cb(callback: CallbackQuery):
    await _send_stu_groups(callback.from_user.id, callback.message.edit_text)
    await callback.answer()


async def _send_stu_groups(user_id: int, send_fn):
    groups = await get_active_groups_for_employee(user_id)
    if not groups:
        groups = await get_active_groups_for_edu_admin(user_id)

    if not groups:
        await send_fn(
            "📭 <b>Hozirgi oyda filialda faol guruhlar topilmadi.</b>",
            parse_mode="HTML",
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"📚 {g['name']}  ({g['student_count']} ta)",
            callback_data=f"emp_stu_group:{g['id']}"
        )]
        for g in groups
    ]
    await send_fn(
        "📚 <b>Guruhni tanlang</b>\n\nDavomat qilmoqchi bo'lgan guruhni tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("emp_stu_group:"))
async def emp_show_students(callback: CallbackQuery):
    group_id = int(callback.data.split(":")[1])
    students = await get_all_students_in_group(group_id)

    if not students:
        await callback.message.edit_text(
            "📭 <b>Bu guruhda tinglovchilar topilmadi.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Guruhlar", callback_data="emp_stu_groups")],
            ])
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"👤 {s['full_name']}",
            web_app=WebAppInfo(url=f"{_EDU_WEB_APP_URL}?student_id={s['id']}")
        )]
        for s in students
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Guruhlar", callback_data="emp_stu_groups")])

    await callback.message.edit_text(
        f"👥 <b>Tinglovchini tanlang</b>\n\nJami: {len(students)} ta tinglovchi",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()
