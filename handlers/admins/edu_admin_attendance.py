"""
Edu Admin — Tinglovchi davomati qayd qilish (yuz tanish orqali).

Flow:
  1. /start → edu_admin keyboard
  2. "📸 Tinglovchini qayd qilish" → fotosurat so'raladi (orqa kamera bilan)
  3. Admin rasm yuboradi → yuz tanish ishlaydi:
       a) Topildi (yuqori ishonch) → tasdiqlash tugmasi
       b) Bir nechta nomzod   → 3 ta tugma ko'rsatiladi
       c) Topilmadi           → qo'lda qidirish taklif qilinadi
  4. "🔍 Tinglovchini qidirish" → ism bo'yicha qidirish (FSM)
  5. Tasdiqlash → check_in yoki check_out qayd qilinadi
"""
import logging
import os
import tempfile

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from loader import dp, bot
from states.users import EduAdminAttendance
from keyboards.inline.main_inline import edu_admin_keyboard
from utils.db_api.database import (
    get_students_with_face_images,
    get_all_students_for_admin,
    admin_mark_student_attendance,
)

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)

_BACK_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")]
])


# ─────────────────────────────────────────────────────────────
# ASOSIY MENYU
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "edu_back_main")
async def edu_back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "📋 <b>O'quv bo'limi — Asosiy menyu</b>",
        parse_mode="HTML",
        reply_markup=edu_admin_keyboard()
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# 📸 RASM ORQALI QAYD QILISH
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "edu_mark_attendance", StateFilter(None))
async def edu_start_attendance(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EduAdminAttendance.waiting_for_photo)
    await callback.message.edit_text(
        "📸 <b>Tinglovchini qayd qilish</b>\n\n"
        "Tinglovchining <b>yuzini</b> surating:\n\n"
        "📱 <i>Telefon orqa kamerasini ishlating — rasm aniq bo'lishi kerak</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="edu_back_main")]
        ])
    )
    await callback.answer()


@router.message(EduAdminAttendance.waiting_for_photo, F.photo)
async def edu_receive_photo(message: Message, state: FSMContext):
    """Admin yuborgan rasm → yuz tanish → natija"""
    admin_id = message.from_user.id

    # ── Rasmni vaqtinchalik saqlash ───────────────────────────
    photo    = message.photo[-1]   # eng katta o'lcham
    file     = await bot.get_file(photo.file_id)
    tmp_path = os.path.join(tempfile.gettempdir(), f"edu_admin_{admin_id}_query.jpg")
    await bot.download_file(file.file_path, destination=tmp_path)

    processing_msg = await message.answer("⏳ <b>Rasm tahlil qilinmoqda...</b>", parse_mode="HTML")

    # ── Bazadan tinglovchilarni olish ─────────────────────────
    students = await get_students_with_face_images(admin_id)

    if not students:
        await processing_msg.edit_text(
            "⚠️ <b>Tizimda yuz rasmi yuklangan tinglovchi topilmadi.</b>\n\n"
            "Tinglovchilarni qo'lda qidirish uchun:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Qo'lda qidirish", callback_data="edu_search_student")],
                [InlineKeyboardButton(text="🔙 Asosiy menyu",    callback_data="edu_back_main")],
            ])
        )
        await state.clear()
        _cleanup(tmp_path)
        return

    # ── Yuz tanish ────────────────────────────────────────────
    from utils.face_recognition_util import recognize_student

    result = await _run_recognition(tmp_path, students)
    _cleanup(tmp_path)

    method     = result.get('method')
    found      = result.get('found', False)
    best       = result.get('best_match')
    candidates = result.get('candidates', [])

    method_label = {
        'face_recognition': '🔬 face_recognition',
        'mediapipe':        '📐 mediapipe',
        None:               '⚙️ noma\'lum',
    }.get(method, method)

    await processing_msg.delete()
    await state.clear()

    # ── Natija: yuz topilmadi ─────────────────────────────────
    if not candidates:
        await message.answer(
            "❌ <b>Rasmda yuz aniqlanmadi.</b>\n\n"
            "Rasm aniq va yoritilgan bo'lishi kerak.\n"
            "Qayta urinib ko'ring yoki qo'lda qidiring:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Qayta rasm",      callback_data="edu_mark_attendance")],
                [InlineKeyboardButton(text="🔍 Qo'lda qidirish", callback_data="edu_search_student")],
                [InlineKeyboardButton(text="🔙 Asosiy menyu",    callback_data="edu_back_main")],
            ])
        )
        return

    # ── Natija: yuqori ishonch — bitta aniq mos ───────────────
    if found and best:
        score_txt = f"{best['score']:.0f}%" if method == 'face_recognition' else ""
        text = (
            f"✅ <b>Tinglovchi aniqlandi</b>  <i>{method_label}</i>\n"
            f"{'─' * 28}\n"
            f"👤 <b>{best['full_name']}</b>\n"
            f"📞 {best['phone'] or '—'}\n"
            + (f"🎯 Ishonch: <b>{score_txt}</b>\n" if score_txt else "")
            + f"\nKirish yoki chiqishini qayd qilamizmi?"
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"✅ Ha, qayd qilish",
                    callback_data=f"edu_confirm:{best['id']}"
                )],
                [InlineKeyboardButton(text="🔍 Boshqa tinglovchi", callback_data="edu_search_student")],
                [InlineKeyboardButton(text="🔙 Asosiy menyu",      callback_data="edu_back_main")],
            ])
        )
        return

    # ── Natija: bir nechta nomzod (past ishonch) ──────────────
    buttons = []
    for c in candidates:
        score_txt = f" ({c['score']:.0f}%)" if method == 'face_recognition' else ""
        buttons.append([InlineKeyboardButton(
            text=f"👤 {c['full_name']}{score_txt}",
            callback_data=f"edu_confirm:{c['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔍 Boshqa tinglovchi", callback_data="edu_search_student")])
    buttons.append([InlineKeyboardButton(text="🔙 Asosiy menyu",      callback_data="edu_back_main")])

    await message.answer(
        f"🔍 <b>Mumkin bo'lgan nomzodlar</b>  <i>{method_label}</i>\n"
        f"{'─' * 28}\n"
        f"Quyidagilardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.message(EduAdminAttendance.waiting_for_photo, ~F.photo)
async def edu_wrong_input(message: Message):
    await message.answer(
        "❌ Iltimos, faqat <b>rasm</b> yuboring.\n"
        "<i>Faylni hujjat sifatida emas, oddiy rasm sifatida yuboring.</i>",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────
# 🔍 QO'LDA QIDIRISH
# ─────────────────────────────────────────────────────────────

from aiogram.fsm.state import State, StatesGroup

class EduStudentSearch(StatesGroup):
    waiting_for_name = State()


@router.callback_query(F.data == "edu_search_student")
async def edu_start_search(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(EduStudentSearch.waiting_for_name)
    await callback.message.edit_text(
        "🔍 <b>Tinglovchini qidirish</b>\n\n"
        "Tinglovchining <b>ismini</b> yozing (qisman ham bo'ladi):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="edu_back_main")]
        ])
    )
    await callback.answer()


@router.message(EduStudentSearch.waiting_for_name, F.text)
async def edu_search_results(message: Message, state: FSMContext):
    query   = message.text.strip()
    admin_id = message.from_user.id

    students = await get_all_students_for_admin(admin_id, search=query)
    await state.clear()

    if not students:
        await message.answer(
            f"❌ <b>«{query}»</b> bo'yicha tinglovchi topilmadi.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Qayta qidirish", callback_data="edu_search_student")],
                [InlineKeyboardButton(text="🔙 Asosiy menyu",   callback_data="edu_back_main")],
            ])
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"{'✅' if s['has_face'] else '❓'} {s['full_name']}",
            callback_data=f"edu_confirm:{s['id']}"
        )]
        for s in students
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="edu_back_main")])

    await message.answer(
        f"🔍 <b>Natijalar:</b> {len(students)} ta\n"
        f"<i>✅ — yuz rasmi bor | ❓ — yuz rasmi yo'q</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# ─────────────────────────────────────────────────────────────
# ✅ TASDIQLASH → DAVOMAT QAYD QILISH
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edu_confirm:"), StateFilter(None))
async def edu_confirm_mark(callback: CallbackQuery):
    student_id = int(callback.data.split(":")[1])
    admin_id   = callback.from_user.id

    result = await admin_mark_student_attendance(student_id, admin_id)

    if not result['ok']:
        error = result.get('error', '')

        if error == 'already_complete':
            text = (
                f"ℹ️ <b>{result['student_name']}</b> uchun bugungi davomat allaqachon to'liq.\n\n"
                f"🔓 Kirdi: <b>{result['check_in']}</b>\n"
                f"🔒 Chiqdi: <b>{result['check_out']}</b>"
            )
        elif error == 'no_group':
            text = (
                f"⚠️ <b>{result.get('student_name', 'Tinglovchi')}</b> "
                f"hech qanday guruhga biriktirilmagan."
            )
        elif error == 'student_not_found':
            text = "❌ Tinglovchi topilmadi."
        else:
            text = f"❌ Xatolik: {error}"

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Yangi qayd",    callback_data="edu_mark_attendance")],
                [InlineKeyboardButton(text="🔙 Asosiy menyu",  callback_data="edu_back_main")],
            ])
        )
        await callback.answer()
        return

    # Muvaffaqiyatli qayd
    action = result['action']

    if action == 'check_in':
        late_txt = ""
        if result.get('late_minutes', 0) > 0:
            m = result['late_minutes']
            late_txt = f"\n⏰ Kechikish: <b>{m} daqiqa</b>"
        text = (
            f"✅ <b>Kirish qayd qilindi!</b>\n"
            f"{'─' * 24}\n"
            f"👤 {result['student_name']}\n"
            f"📚 {result['group_name']}\n"
            f"🕐 Kirdi: <b>{result['time']}</b>"
            f"{late_txt}"
        )
    else:  # check_out
        text = (
            f"✅ <b>Chiqish qayd qilindi!</b>\n"
            f"{'─' * 24}\n"
            f"👤 {result['student_name']}\n"
            f"📚 {result['group_name']}\n"
            f"🔓 Kirdi:  <b>{result['check_in']}</b>\n"
            f"🔒 Chiqdi: <b>{result['time']}</b>"
        )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Yana bir qayd",  callback_data="edu_mark_attendance")],
            [InlineKeyboardButton(text="🔙 Asosiy menyu",   callback_data="edu_back_main")],
        ])
    )
    await callback.answer("✅ Qayd qilindi!")


# ─────────────────────────────────────────────────────────────
# YORDAMCHI FUNKSIYALAR
# ─────────────────────────────────────────────────────────────

async def _run_recognition(query_path: str, students: list) -> dict:
    """Face recognition'ni async wrapper orqali ishga tushirish"""
    import asyncio
    from utils.face_recognition_util import recognize_student

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        recognize_student,
        query_path,
        students,
        3,  # top_n
    )
    return result


def _cleanup(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
