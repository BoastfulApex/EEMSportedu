"""
Tinglovchi login va parol orqali Telegram ga bog'lanishi.

Flow:
  1. /start → noma'lum foydalanuvchi → "Login orqali kirish" tugmasi
  2. "student_login_start" callback → login so'raladi
  3. Login kiritildi → parol so'raladi
  4. Login+parol tekshiriladi → Student topiladi
  5. Telegram ID saqlanadi → foto so'raladi yoki asosiy menyu
"""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from loader import dp
from states.users import StudentLoginAuth, StudentPhotoUpload
from keyboards.inline.main_inline import student_main_keyboard
from utils.db_api.database import find_student_by_credentials, attach_telegram_to_student

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)

_CANCEL_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="student_login_cancel")]
])


# ─────────────────────────────────────────────────────────────
# BOSHLASH
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "student_login_start")
async def student_login_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(StudentLoginAuth.waiting_for_login)
    await callback.message.edit_text(
        "🔐 <b>Login orqali kirish</b>\n\n"
        "Iltimos, <b>login</b> ingizni kiriting:\n"
        "<i>(O'quv bo'limi tomonidan berilgan)</i>",
        parse_mode="HTML",
        reply_markup=_CANCEL_KB
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# LOGIN QABUL
# ─────────────────────────────────────────────────────────────

@router.message(StudentLoginAuth.waiting_for_login, F.text)
async def student_login_receive_login(message: Message, state: FSMContext):
    login = message.text.strip()
    if len(login) < 2:
        await message.answer(
            "❌ Login juda qisqa. Iltimos, qayta kiriting:",
            reply_markup=_CANCEL_KB
        )
        return

    await state.update_data(login=login)
    await state.set_state(StudentLoginAuth.waiting_for_password)
    await message.answer(
        f"✅ Login: <code>{login}</code>\n\n"
        f"Endi <b>parol</b> ingizni kiriting:",
        parse_mode="HTML",
        reply_markup=_CANCEL_KB
    )


@router.message(StudentLoginAuth.waiting_for_login, ~F.text)
async def student_login_wrong_login(message: Message):
    await message.answer(
        "❌ Iltimos, faqat matn ko'rinishida login kiriting:",
        reply_markup=_CANCEL_KB
    )


# ─────────────────────────────────────────────────────────────
# PAROL QABUL
# ─────────────────────────────────────────────────────────────

@router.message(StudentLoginAuth.waiting_for_password, F.text)
async def student_login_receive_password(message: Message, state: FSMContext):
    password = message.text.strip()
    data     = await state.get_data()
    login    = data.get('login', '')

    student = await find_student_by_credentials(login, password)

    if not student:
        await message.answer(
            "❌ <b>Login yoki parol noto'g'ri.</b>\n\n"
            "Iltimos, qayta urinib ko'ring yoki admin bilan bog'laning.\n\n"
            "Loginni qayta kiriting:",
            parse_mode="HTML",
            reply_markup=_CANCEL_KB
        )
        await state.set_state(StudentLoginAuth.waiting_for_login)
        return

    # Telegram ID saqlaymiz
    ok = await attach_telegram_to_student(student['id'], message.from_user.id)
    await state.clear()

    if not ok:
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔐 Qayta urinish", callback_data="student_login_start")]
            ])
        )
        return

    if student['has_face']:
        # Rasm bor — darhol asosiy menyuga
        await message.answer(
            f"✅ <b>Xush kelibsiz, {student['full_name']}!</b>\n\n"
            f"Siz muvaffaqiyatli tizimga kirdiniz.",
            parse_mode="HTML",
            reply_markup=student_main_keyboard()
        )
    else:
        # Rasm yo'q — foto so'rab olamiz
        await state.set_state(StudentPhotoUpload.waiting_for_photo)
        await message.answer(
            f"✅ <b>Xush kelibsiz, {student['full_name']}!</b>\n\n"
            f"📸 Tizimga kirish uchun <b>yuz rasmingiz</b> kerak.\n\n"
            f"Iltimos, <b>yuzingiz aniq ko'rinib turgan</b> rasmingizni yuboring:",
            parse_mode="HTML"
        )


@router.message(StudentLoginAuth.waiting_for_password, ~F.text)
async def student_login_wrong_password(message: Message):
    await message.answer(
        "❌ Iltimos, faqat matn ko'rinishida parol kiriting:",
        reply_markup=_CANCEL_KB
    )


# ─────────────────────────────────────────────────────────────
# BEKOR QILISH
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "student_login_cancel")
async def student_login_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "⚠️ <b>Botdan foydalanish uchun</b> tashkilot administratoridan "
        "maxsus havola oling, yoki login parol orqali ro'yxatdan o'ting.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔐 Login orqali kirish", callback_data="student_login_start")]
        ])
    )
    await callback.answer()
