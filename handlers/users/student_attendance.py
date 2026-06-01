"""
Tinglovchi bot handlerlari.
- Yuz rasmi yuklash (ro'yxatdan o'tgandan keyin yoki rasmi yo'q bo'lsa)
- Kirish/chiqish endi web app orqali amalga oshiriladi (lokatsiya + Face ID)
"""
import os
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, bot
from states.users import StudentPhotoUpload
from keyboards.inline.main_inline import student_main_keyboard, student_reply_keyboard
from utils.db_api.database import (
    save_student_face_photo,
    get_student_groups_for_telegram,
    get_registered_group_members_with_status,
    set_group_member_attendance,
)
from utils.face_check import detect_face

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)


# ============================================================
# YUZ RASMI YUKLASH (ro'yxatdan o'tgandan keyin yoki rasmi yo'q bo'lganda)
# ============================================================

@router.message(StudentPhotoUpload.waiting_for_photo, F.photo)
async def student_photo_upload(message: Message, state: FSMContext):
    user_id = message.from_user.id

    await message.answer("⏳ Rasm tekshirilmoqda...")

    photo = message.photo[-1]
    file  = await bot.get_file(photo.file_id)

    # Vaqtinchalik fayl — /tmp (ruxsat muammosi bo'lmaydi)
    import tempfile
    tmp_path = os.path.join(tempfile.gettempdir(), f"student_{user_id}_face.jpg")

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
            "Rasmda yuz aniqlanmadi yoki rasm sifati past.\n"
            "Iltimos, <b>yuzingiz to'liq va aniq ko'ringan holda</b> qayta rasm yuboring:",
            parse_mode="HTML"
        )
        return  # Holatni saqlaymiz — qayta rasm kutiladi

    # Doimiy joyga saqlash — MEDIA_ROOT/student_faces/
    from django.conf import settings
    save_dir = os.path.join(settings.MEDIA_ROOT, "student_faces")
    os.makedirs(save_dir, exist_ok=True)
    file_name    = f"student_{user_id}.jpg"
    final_path   = os.path.join(save_dir, file_name)
    relative_path = os.path.join("student_faces", file_name)

    try:
        import shutil
        shutil.move(tmp_path, final_path)
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    saved = await save_student_face_photo(telegram_id=user_id, photo_path=relative_path)

    if saved:
        await state.clear()
        await message.answer(
            "✅ <b>Yuz rasmi saqlandi!</b>\n\n"
            "Endi kirish va chiqishda Face ID tekshiruvi ishlaydi.",
            parse_mode="HTML",
            reply_markup=student_reply_keyboard()
        )
        await message.answer(
            "👇 Davomat uchun tugmani bosing:",
            reply_markup=student_main_keyboard()
        )
    else:
        await message.answer(
            "❌ Rasm saqlanishda xatolik yuz berdi.\n"
            "Iltimos, qayta urinib ko'ring."
        )


@router.message(StudentPhotoUpload.waiting_for_photo, ~F.photo)
async def student_photo_wrong_input(message: Message):
    await message.answer(
        "❌ Iltimos, faqat <b>rasm</b> yuboring.\n\n"
        "📌 Eslatma: Faylni hujjat sifatida emas, oddiy rasm sifatida yuboring.",
        parse_mode="HTML"
    )


@router.message(F.text == "🎓 Davomat", StateFilter(None))
async def student_davomat_button(message: Message):
    """Tinglovchi '🎓 Davomat' tugmasini bosdi — WebApp inline klaviaturasini ko'rsatamiz."""
    await message.answer(
        "👇 Davomat uchun tugmani bosing:",
        reply_markup=student_main_keyboard()
    )


# ============================================================
# GURUH DAVOMATI — o'z guruh a'zolarini belgilash
# ============================================================

def _members_keyboard(members: list, group_id: int) -> InlineKeyboardMarkup:
    """Guruhdoshlar ro'yxati — faqat ismlar."""
    buttons = [
        [InlineKeyboardButton(
            text=f"👤 {m['full_name']}",
            callback_data=f"sgrp_mark:{m['student_id']}:{group_id}"
        )]
        for m in members
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="sgrp_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "📋 Tinglovchi davomati", StateFilter(None))
async def student_group_attendance_btn(message: Message):
    """'📋 Tinglovchi davomati' tugmasi — guruhdoshlar ro'yxati."""
    from datetime import date
    user_id = message.from_user.id
    groups = await get_student_groups_for_telegram(user_id)

    if not groups:
        await message.answer(
            "⚠️ Siz hali hech qanday guruhga kiritilmagan yoki ro'yxatdan o'tmagansiz."
        )
        return

    if len(groups) == 1:
        g = groups[0]
        members = await get_registered_group_members_with_status(g['group_id'], date.today())
        if not members:
            await message.answer(
                f"📭 <b>{g['group_name']}</b> guruhida ro'yxatdan o'tgan tinglovchilar yo'q.",
                parse_mode="HTML"
            )
            return
        await message.answer(
            f"👥 <b>{g['group_name']}</b> — guruhdoshlar ro'yxati",
            parse_mode="HTML",
            reply_markup=_members_keyboard(members, g['group_id'])
        )
    else:
        buttons = [
            [InlineKeyboardButton(
                text=f"📚 {g['group_name']}",
                callback_data=f"sgrp_select:{g['group_id']}"
            )]
            for g in groups
        ]
        buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="sgrp_back")])
        await message.answer(
            "📚 Qaysi guruhni ko'rmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )


@router.callback_query(F.data.startswith("sgrp_select:"), StateFilter(None))
async def student_group_select(callback: CallbackQuery):
    from datetime import date
    group_id = int(callback.data.split(":")[1])
    members = await get_registered_group_members_with_status(group_id, date.today())

    if not members:
        await callback.message.edit_text(
            "📭 Bu guruhda ro'yxatdan o'tgan tinglovchilar yo'q.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="sgrp_back")]
            ])
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "👥 <b>Guruhdoshlar ro'yxati</b>",
        parse_mode="HTML",
        reply_markup=_members_keyboard(members, group_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sgrp_mark:"), StateFilter(None))
async def student_mark_member(callback: CallbackQuery):
    """Tinglovchi tanlandi — davomat status tugmalarini ko'rsat."""
    _, student_id, group_id = callback.data.split(":")
    student_id, group_id = int(student_id), int(group_id)

    status_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Keldi",    callback_data=f"sgrp_set:{student_id}:{group_id}:present"),
            InlineKeyboardButton(text="❌ Kelmadi",  callback_data=f"sgrp_set:{student_id}:{group_id}:absent"),
        ],
        [
            InlineKeyboardButton(text="⏰ Kechikdi", callback_data=f"sgrp_set:{student_id}:{group_id}:late"),
            InlineKeyboardButton(text="📝 Sababli",  callback_data=f"sgrp_set:{student_id}:{group_id}:excused"),
        ],
        [InlineKeyboardButton(text="🔙 Orqaga",     callback_data=f"sgrp_select:{group_id}")],
    ])
    await callback.message.edit_reply_markup(reply_markup=status_kb)
    await callback.answer()


@router.callback_query(F.data.startswith("sgrp_set:"), StateFilter(None))
async def student_set_member_status(callback: CallbackQuery):
    """Status saqlash va ro'yxatga qaytish."""
    from datetime import date
    _, student_id, group_id, status = callback.data.split(":")
    student_id, group_id = int(student_id), int(group_id)

    await set_group_member_attendance(student_id, group_id, date.today(), status)

    members = await get_registered_group_members_with_status(group_id, date.today())
    STATUS_LABEL = {'present': '✅ Keldi', 'absent': '❌ Kelmadi', 'late': '⏰ Kechikdi', 'excused': '📝 Sababli'}
    await callback.message.edit_text(
        "👥 <b>Guruhdoshlar ro'yxati</b>",
        parse_mode="HTML",
        reply_markup=_members_keyboard(members, group_id)
    )
    await callback.answer(STATUS_LABEL.get(status, status))


@router.callback_query(F.data == "sgrp_back", StateFilter(None))
async def student_group_back(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()


# back_to_main callback — stats.py da yagona joyda boshqariladi
