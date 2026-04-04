import os
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from loader import dp, bot
from states.users import StudentCheckState
from keyboards.inline.main_inline import student_main_keyboard
from utils.db_api.database import (
    student_mark_check_in,
    student_mark_check_out,
    get_student_by_telegram_id,
    save_student_face_photo,
)
from utils.face_check import detect_face

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)


# ============================================================
# KIRISH tugmasi bosilganda
# ============================================================

@router.callback_query(F.data == "student_check_in")
async def student_check_in_start(callback: CallbackQuery, state: FSMContext):
    student = await get_student_by_telegram_id(callback.from_user.id)
    if not student:
        await callback.answer("❌ Tinglovchi topilmadi!", show_alert=True)
        return

    await state.set_state(StudentCheckState.waiting_for_photo)
    await state.update_data(action="check_in")

    await callback.message.answer(
        "📸 Kirish uchun <b>yuzingiz aniq ko'rinib turgan</b> rasmingizni yuboring:",
        parse_mode="HTML"
    )
    await callback.answer()


# ============================================================
# CHIQISH tugmasi bosilganda
# ============================================================

@router.callback_query(F.data == "student_check_out")
async def student_check_out_start(callback: CallbackQuery, state: FSMContext):
    student = await get_student_by_telegram_id(callback.from_user.id)
    if not student:
        await callback.answer("❌ Tinglovchi topilmadi!", show_alert=True)
        return

    await state.set_state(StudentCheckState.waiting_for_photo)
    await state.update_data(action="check_out")

    await callback.message.answer(
        "📸 Chiqish uchun <b>yuzingiz aniq ko'rinib turgan</b> rasmingizni yuboring:",
        parse_mode="HTML"
    )
    await callback.answer()


# ============================================================
# FOTO QABUL QILISH
# ============================================================

@router.message(StudentCheckState.waiting_for_photo, F.photo)
async def student_photo_received(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("action", "check_in")
    user_id = message.from_user.id

    await message.answer("⏳ Rasm tekshirilmoqda...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    save_dir = os.path.join("files", "student_photos")
    os.makedirs(save_dir, exist_ok=True)
    file_name = f"student_{user_id}_tmp.jpg"
    abs_path = os.path.join(save_dir, file_name)

    await bot.download_file(file.file_path, destination=abs_path)

    has_face = detect_face(abs_path)
    if not has_face:
        try:
            os.remove(abs_path)
        except Exception:
            pass
        await message.answer(
            "❌ <b>Rasm qabul qilinmadi.</b>\n\n"
            "Rasmda yuz aniqlanmadi yoki rasm sifati past.\n"
            "Iltimos, <b>yuzingiz to'liq va aniq ko'ringan holda</b> qayta rasm yuboring:",
            parse_mode="HTML"
        )
        return

    # Davomatni belgilash
    if action == "check_in":
        result = await student_mark_check_in(user_id)
    else:
        result = await student_mark_check_out(user_id)

    await state.clear()

    try:
        os.remove(abs_path)
    except Exception:
        pass

    if not result['ok']:
        error = result.get('error', '')
        if error == 'already_checked_in':
            text = f"⚠️ Siz bugun allaqachon {result['time']} da kirgansiz."
        elif error == 'already_checked_out':
            text = f"⚠️ Siz bugun allaqachon {result['time']} da chiqgansiz."
        elif error == 'not_checked_in':
            text = "⚠️ Avval kirish belgisini qo'ying."
        elif error == 'no_group':
            text = "⚠️ Guruhingiz topilmadi. Administrator bilan bog'laning."
        else:
            text = "❌ Xatolik yuz berdi. Administrator bilan bog'laning."
        await message.answer(text, reply_markup=student_main_keyboard())
        return

    if action == "check_in":
        late_min = result.get('late_minutes', 0)
        exp_start = result.get('expected_start')
        if late_min and late_min > 0:
            text = (
                f"✅ <b>{result['full_name']}</b>, kirish belgilandi!\n"
                f"🕐 Kelgan vaqt: <b>{result['time']}</b>\n"
                f"📅 Dars boshlanishi: {exp_start}\n"
                f"⏰ Kechikish: <b>{late_min} daqiqa</b>"
            )
        else:
            exp_str = f"\n📅 Dars boshlanishi: {exp_start}" if exp_start else ""
            text = (
                f"✅ <b>{result['full_name']}</b>, kirish belgilandi!\n"
                f"🕐 Vaqt: <b>{result['time']}</b>{exp_str}\n"
                f"👍 O'z vaqtida keldingiz!"
            )
    else:
        early_min = result.get('early_leave_minutes', 0)
        exp_end = result.get('expected_end')
        if early_min and early_min > 0:
            text = (
                f"✅ <b>{result['full_name']}</b>, chiqish belgilandi!\n"
                f"🕐 Ketgan vaqt: <b>{result['time']}</b>\n"
                f"📅 Dars tugashi: {exp_end}\n"
                f"⏰ Erta ketish: <b>{early_min} daqiqa</b>"
            )
        else:
            exp_str = f"\n📅 Dars tugashi: {exp_end}" if exp_end else ""
            text = (
                f"✅ <b>{result['full_name']}</b>, chiqish belgilandi!\n"
                f"🕐 Vaqt: <b>{result['time']}</b>{exp_str}"
            )

    await message.answer(text, parse_mode="HTML", reply_markup=student_main_keyboard())


@router.message(StudentCheckState.waiting_for_photo, ~F.photo)
async def student_wrong_input(message: Message):
    await message.answer(
        "❌ Iltimos, faqat <b>rasm</b> yuboring.",
        parse_mode="HTML"
    )


# ============================================================
# ASOSIY MENYUGA QAYTISH
# ============================================================

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("📋 Asosiy menyu:", reply_markup=student_main_keyboard())
    await callback.answer()
