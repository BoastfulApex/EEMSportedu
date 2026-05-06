"""
Edu admin — Tinglovchini bot orqali ro'yxatdan o'tkazish.

Flow:
  1. "👤 Tinglovchilarni ro'yxatdan o'tkazish" → hozirgi oydagi guruhlar
  2. Guruh tanlandi → guruhdagi tinglovchilar ro'yxati
  3. Tinglovchi tanlandi → foto yuborish so'raladi
  4. Foto yuborildi → face_image saqlanadi (telegram_id o'zgarmaydi)
  5. Login va parol ko'rsatiladi
"""
import os
import tempfile
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from loader import dp, bot
from states.users import EduStudentReg
from utils.db_api.database import (
    get_active_groups_for_edu_admin,
    get_students_in_group_for_reg,
    save_student_face_by_id,
)
from utils.face_check import detect_face

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)

_BACK_MAIN = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")]
])


# ─────────────────────────────────────────────────────────────
# 1. GURUHLAR RO'YXATI
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "edu_reg_start")
async def edu_reg_show_groups(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    admin_id = callback.from_user.id

    from datetime import date
    today = date.today()
    month_names = {
        1: 'Yanvar', 2: 'Fevral', 3: 'Mart', 4: 'Aprel',
        5: 'May', 6: 'Iyun', 7: 'Iyul', 8: 'Avgust',
        9: 'Sentabr', 10: 'Oktabr', 11: 'Noyabr', 12: 'Dekabr',
    }

    groups = await get_active_groups_for_edu_admin(admin_id)

    if not groups:
        await callback.message.edit_text(
            f"📭 <b>{month_names[today.month]} {today.year}</b> uchun "
            f"faol guruhlar topilmadi.\n\n"
            f"Avval admin panelda guruh yarating.",
            parse_mode="HTML",
            reply_markup=_BACK_MAIN
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"📚 {g['name']}  ({g['student_count']} ta)",
            callback_data=f"edu_reg_group:{g['id']}"
        )]
        for g in groups
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")])

    await callback.message.edit_text(
        f"📋 <b>{month_names[today.month]} {today.year} — Faol guruhlar</b>\n\n"
        f"Tinglovchi rasmini yuklash uchun guruhni tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# 2. TINGLOVCHILAR RO'YXATI
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edu_reg_group:"))
async def edu_reg_show_students(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.split(":")[1])
    students = await get_students_in_group_for_reg(group_id)

    if not students:
        await callback.message.edit_text(
            "📭 Bu guruhda tinglovchilar topilmadi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Guruhlar", callback_data="edu_reg_start")],
                [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")],
            ])
        )
        await callback.answer()
        return

    buttons = []
    for s in students:
        face_icon = "📷" if s['has_face'] else "❌"
        tg_icon   = "✅" if s['has_tg'] else "—"
        buttons.append([InlineKeyboardButton(
            text=f"{face_icon} {s['full_name']}  [{tg_icon}]",
            callback_data=f"edu_reg_student:{s['id']}:{group_id}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Guruhlar", callback_data="edu_reg_start")])
    buttons.append([InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")])

    await callback.message.edit_text(
        "👤 <b>Tinglovchilar ro'yxati</b>\n\n"
        "<i>📷 — rasmi bor | ❌ — rasmi yo'q\n"
        "✅ — Telegram biriktirilgan | — — biriktirilmagan</i>\n\n"
        "Rasmini yuklash uchun tinglovchini tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# 3. TINGLOVCHI TANLANDI — FOTO SO'RASH
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edu_reg_student:"))
async def edu_reg_ask_photo(callback: CallbackQuery, state: FSMContext):
    parts    = callback.data.split(":")
    stu_id   = int(parts[1])
    group_id = int(parts[2])

    await state.set_state(EduStudentReg.waiting_for_photo)
    await state.update_data(student_id=stu_id, group_id=group_id)

    await callback.message.edit_text(
        "📸 <b>Tinglovchi rasmi</b>\n\n"
        "Tinglovchining <b>yuzini aniq ko'rsatadigan</b> rasmini yuboring.\n"
        "<i>Rasm sifatli va yoritilgan bo'lishi kerak.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔙 Orqaga",
                callback_data=f"edu_reg_group:{group_id}"
            )],
        ])
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# 4. FOTO QABUL QILISH
# ─────────────────────────────────────────────────────────────

@router.message(EduStudentReg.waiting_for_photo, F.photo)
async def edu_reg_receive_photo(message: Message, state: FSMContext):
    data       = await state.get_data()
    student_id = data['student_id']
    group_id   = data['group_id']

    await message.answer("⏳ <b>Rasm tekshirilmoqda...</b>", parse_mode="HTML")

    photo    = message.photo[-1]
    file     = await bot.get_file(photo.file_id)
    tmp_path = os.path.join(tempfile.gettempdir(), f"edu_reg_{student_id}.jpg")
    await bot.download_file(file.file_path, destination=tmp_path)

    # Yuz aniqlash
    has_face = detect_face(tmp_path)
    if not has_face:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        await message.answer(
            "❌ <b>Rasm qabul qilinmadi.</b>\n\n"
            "Rasmda yuz aniqlanmadi yoki sifat past.\n"
            "Iltimos, yuzingiz aniq ko'ringan rasmni qayta yuboring:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Guruhlar", callback_data="edu_reg_start")],
            ])
        )
        return  # holatni saqlaymiz — qayta rasm kutiladi

    # student_faces/ papkasiga ko'chiramiz
    from django.conf import settings
    save_dir  = os.path.join(settings.MEDIA_ROOT, "student_faces")
    os.makedirs(save_dir, exist_ok=True)
    file_name     = f"student_admin_{student_id}.jpg"
    final_path    = os.path.join(save_dir, file_name)
    relative_path = os.path.join("student_faces", file_name)

    try:
        import shutil
        shutil.move(tmp_path, final_path)
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    result = await save_student_face_by_id(student_id, relative_path)
    await state.clear()

    if not result:
        await message.answer(
            "❌ Rasm saqlanishda xatolik yuz berdi.\nIltimos, qayta urinib ko'ring.",
            reply_markup=_BACK_MAIN
        )
        return

    login    = result['login'] or "—"
    password = result['password'] or "—"

    await message.answer(
        f"✅ <b>Rasm muvaffaqiyatli saqlandi!</b>\n\n"
        f"👤 <b>{result['full_name']}</b>\n"
        f"{'─' * 28}\n"
        f"🔑 Login:  <code>{login}</code>\n"
        f"🔒 Parol:  <code>{password}</code>\n\n"
        f"<i>Tinglovchi shu login va parol orqali tizimga kiradi.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="👤 Yana bir tinglovchi",
                callback_data=f"edu_reg_group:{group_id}"
            )],
            [InlineKeyboardButton(text="🔙 Guruhlar", callback_data="edu_reg_start")],
            [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")],
        ])
    )


@router.message(EduStudentReg.waiting_for_photo, ~F.photo)
async def edu_reg_wrong_input(message: Message):
    await message.answer(
        "❌ Iltimos, faqat <b>rasm</b> yuboring.\n"
        "<i>Faylni hujjat sifatida emas, oddiy rasm sifatida yuboring.</i>",
        parse_mode="HTML"
    )
