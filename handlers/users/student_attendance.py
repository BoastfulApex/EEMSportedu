"""
Tinglovchi bot handlerlari.
- Yuz rasmi yuklash (ro'yxatdan o'tgandan keyin yoki rasmi yo'q bo'lsa)
- Kirish/chiqish endi web app orqali amalga oshiriladi (lokatsiya + Face ID)
"""
import os
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from loader import dp, bot
from states.users import StudentPhotoUpload
from keyboards.inline.main_inline import student_main_keyboard
from utils.db_api.database import save_student_face_photo
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


# back_to_main callback — stats.py da yagona joyda boshqariladi
