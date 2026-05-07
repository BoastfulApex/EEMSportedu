"""
Edu Admin — Tinglovchi davomati qayd qilish.

Flow:
  1. "📋 Tinglovchi davomatini qayd qilish" → hozirgi oydagi guruhlar
  2. Guruh tanlandi → guruhdagi tinglovchilar ro'yxati
  3. Tinglovchi tanlandi → WebApp ochiladi (yuz tanish + lokatsiya)
"""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
)

from loader import dp
from data.config import BASE_URL
from keyboards.inline.main_inline import edu_admin_keyboard
from utils.db_api.database import (
    get_active_groups_for_edu_admin,
    get_all_students_in_group,
)

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)

_EDU_WEB_APP_URL = BASE_URL.rstrip('/') + '/students/edu-admin/web-app/'

_BACK_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")]
])


# ─────────────────────────────────────────────────────────────
# ASOSIY MENYU
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "edu_back_main")
async def edu_back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    from utils.db_api.database import is_user_employee
    from keyboards.inline.main_inline import edu_admin_employee_keyboard

    if await is_user_employee(callback.from_user.id):
        keyboard = edu_admin_employee_keyboard()
    else:
        keyboard = edu_admin_keyboard()

    await callback.message.edit_text(
        "📋 <b>O'quv bo'limi — Asosiy menyu</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# 1. GURUHLAR RO'YXATI
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "edu_mark_attendance")
async def edu_show_groups(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    admin_id = callback.from_user.id

    groups = await get_active_groups_for_edu_admin(admin_id)

    if not groups:
        await callback.message.edit_text(
            "📭 <b>Hozirgi oyda faol guruhlar topilmadi.</b>\n\n"
            "Avval admin panelda guruh yarating.",
            parse_mode="HTML",
            reply_markup=_BACK_KB
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"📚 {g['name']}  ({g['student_count']} ta)",
            callback_data=f"edu_attend_group:{g['id']}"
        )]
        for g in groups
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")])

    await callback.message.edit_text(
        "📚 <b>Guruhni tanlang</b>\n\n"
        "Davomat qilmoqchi bo'lgan guruhni tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# 2. TINGLOVCHILAR RO'YXATI
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edu_attend_group:"))
async def edu_show_students(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.split(":")[1])
    students = await get_all_students_in_group(group_id)

    if not students:
        await callback.message.edit_text(
            "📭 <b>Bu guruhda tinglovchilar topilmadi.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Guruhlar",     callback_data="edu_mark_attendance")],
                [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")],
            ])
        )
        await callback.answer()
        return

    # Har bir tinglovchi uchun WebApp tugmasi — student_id URL parametr sifatida
    buttons = [
        [InlineKeyboardButton(
            text=f"👤 {s['full_name']}",
            web_app=WebAppInfo(url=f"{_EDU_WEB_APP_URL}?student_id={s['id']}")
        )]
        for s in students
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Guruhlar",     callback_data="edu_mark_attendance")])
    buttons.append([InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")])

    await callback.message.edit_text(
        f"👥 <b>Tinglovchini tanlang</b>\n\n"
        f"Jami: {len(students)} ta tinglovchi\n"
        f"<i>Tanlangandan keyin yuz va lokatsiya tekshiruvi o'tkaziladi</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()
