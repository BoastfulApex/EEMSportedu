"""
Tinglovchi davomati qayd qilish.

Flow (edu admin):
  "📋 Tinglovchi davomati" → guruhlar ro'yxati → tinglovchilar → WebApp

Flow (tinglovchi):
  "📋 Tinglovchi davomati" → o'z guruhidagi tinglovchilar → WebApp
"""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
)

from loader import dp
from data.config import BASE_URL
from keyboards.inline.main_inline import edu_admin_keyboard
from utils.db_api.database import (
    get_active_groups_for_edu_admin,
    get_all_students_in_group,
    get_student_groups_for_telegram,
    is_user_student,
)

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)

_EDU_WEB_APP_URL = BASE_URL.rstrip('/') + '/students/edu-admin/web-app/'

_BACK_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")]
])


# ─────────────────────────────────────────────────────────────
# YORDAMCHI: edu admin uchun guruhlar ro'yxati
# ─────────────────────────────────────────────────────────────

async def _send_attendance_groups(admin_id: int, send_fn):
    """Edu admin uchun: faol guruhlar ro'yxatini yuboradi."""
    groups = await get_active_groups_for_edu_admin(admin_id)

    if not groups:
        await send_fn(
            "📭 <b>Hozirgi oyda faol guruhlar topilmadi.</b>\n\n"
            "Avval admin panelda guruh yarating.",
            parse_mode="HTML",
            reply_markup=_BACK_KB
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"📚 {g['name']}  ({g['student_count']} ta)",
            callback_data=f"edu_attend_group:{g['id']}"
        )]
        for g in groups
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")])

    await send_fn(
        "📚 <b>Guruhni tanlang</b>\n\n"
        "Davomat qilmoqchi bo'lgan guruhni tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# ─────────────────────────────────────────────────────────────
# TINGLOVCHI — o'z guruhdoshlari ro'yxati (guruh tanlash yo'q)
# ─────────────────────────────────────────────────────────────

async def _send_student_groupmates(telegram_id: int, send_fn):
    """Tinglovchining guruhdoshlari ro'yxatini edu_admin uslubida ko'rsatadi."""
    groups = await get_student_groups_for_telegram(telegram_id)

    if not groups:
        await send_fn(
            "⚠️ Siz hali hech qanday guruhga kiritilmagan yoki ro'yxatdan o'tmagansiz."
        )
        return

    # Birinchi (yagona) guruhni olamiz
    g = groups[0]
    students = await get_all_students_in_group(g['group_id'])

    if not students:
        await send_fn(
            f"📭 <b>{g['group_name']}</b> guruhida tinglovchilar topilmadi.",
            parse_mode="HTML"
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"👤 {s['full_name']}",
            web_app=WebAppInfo(url=f"{_EDU_WEB_APP_URL}?student_id={s['id']}")
        )]
        for s in students
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Yopish", callback_data="sgrp_close")])

    await send_fn(
        f"👥 <b>{g['group_name']}</b> — guruhdoshlar\n\n"
        f"Jami: {len(students)} ta tinglovchi\n"
        f"<i>Tanlangandan keyin yuz va lokatsiya tekshiruvi o'tkaziladi</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


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
# 1. GURUHLAR RO'YXATI (edu admin) / TO'G'RIDAN TO'G'RI (tinglovchi)
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "edu_mark_attendance")
async def edu_show_groups(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _send_attendance_groups(callback.from_user.id, callback.message.edit_text)
    await callback.answer()


@router.message(F.text == "📋 Tinglovchi davomati", StateFilter(None))
async def edu_show_groups_reply(message: Message, state: FSMContext):
    """Tinglovchi → o'z guruhidagi tinglovchilar; edu admin → guruh tanlash."""
    await state.clear()
    user_id = message.from_user.id

    if await is_user_student(user_id):
        await _send_student_groupmates(user_id, message.answer)
        return

    await _send_attendance_groups(user_id, message.answer)


# ─────────────────────────────────────────────────────────────
# 2. TINGLOVCHILAR RO'YXATI (edu admin guruh tanlagandan keyin)
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
                [InlineKeyboardButton(text="🔙 Guruhlar",      callback_data="edu_mark_attendance")],
                [InlineKeyboardButton(text="🔙 Asosiy menyu",  callback_data="edu_back_main")],
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



@router.callback_query(F.data == "sgrp_close")
async def student_groupmates_close(callback: CallbackQuery):
    """Tinglovchi guruhdoshlari xabarini yopish."""
    await callback.message.delete()
    await callback.answer()
