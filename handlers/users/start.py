import os
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, bot
from states.users import EmployeeRegistration, StudentGroupSelect
from keyboards.inline.main_inline import (
    employee_main_keyboard,
    student_main_keyboard,
    get_user_approval_keyboard,
    get_organization_selection_keyboard,
    get_filial_selection_keyboard_by_org,
)
from utils.db_api.database import (
    get_telegram_user,
    get_or_create_telegram_user,
    is_user_employee,
    is_user_admin,
    is_user_student,
    has_employee_photo,
    save_employee_photo,
    get_hr_admins_by_filial,
    get_invite_token,
    set_telegram_user_organization,
    get_group_by_invite_token,
    get_students_by_group,
    link_student_telegram,
)
from utils.face_check import detect_face

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)


# ============================================================
# /start — asosiy kirish nuqtasi
# ============================================================

@router.message(CommandStart(), StateFilter(None))
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    user = message.from_user
    args = command.args

    await get_or_create_telegram_user(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
    )

    # ── 1. Admin ─────────────────────────────────────────────
    if await is_user_admin(user.id):
        from keyboards.inline.menu_button import admin_menu_keyboard
        await message.answer(
            "👋 Assalomu alaykum, Hurmatli Administrator!\n\n"
            "Quyidagi bo'limlardan birini tanlang:",
            reply_markup=await admin_menu_keyboard()
        )
        return

    # ── 2. Allaqachon xodim ───────────────────────────────────
    if await is_user_employee(user.id):
        if await has_employee_photo(user.id):
            await message.answer(
                "✅ Xush kelibsiz!",
                reply_markup=await employee_main_keyboard()
            )
        else:
            await state.set_state(EmployeeRegistration.waiting_for_photo)
            await message.answer(
                "📸 Yuz rasmingiz saqlanmagan.\n\n"
                "Iltimos, <b>yuzingiz aniq ko'rinib turgan</b> rasmingizni yuboring:",
                parse_mode="HTML"
            )
        return

    # ── 3. Allaqachon tinglovchi ──────────────────────────────
    if await is_user_student(user.id):
        await message.answer(
            "✅ Xush kelibsiz!",
            reply_markup=student_main_keyboard()
        )
        return

    # ── 4. Yangi foydalanuvchi — havolaga qarab yo'naltirish ──

    # 4a. Guruh taklif havolasi: grp_<uuid>
    if args and args.startswith('grp_'):
        token = args[4:]
        group = await get_group_by_invite_token(token)
        if not group:
            await message.answer(
                "⚠️ Noto'g'ri yoki eskirgan guruh havolasi.\n"
                "Administrator bilan bog'laning."
            )
            return

        students = await get_students_by_group(group['id'])
        if not students:
            await message.answer(
                f"⚠️ <b>{group['name']}</b> guruhida hali tinglovchilar yo'q.\n"
                "Administrator bilan bog'laning.",
                parse_mode="HTML"
            )
            return

        buttons = [
            [InlineKeyboardButton(
                text=s['full_name'],
                callback_data=f"student_select:{s['id']}:{group['id']}"
            )]
            for s in students
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        await state.set_state(StudentGroupSelect.selecting)
        await state.update_data(group_id=group['id'])

        await message.answer(
            f"📋 <b>{group['name']}</b> guruhi ro'yxati\n"
            f"🏢 {group['filial_name']}  |  📅 {group['year']} — {group['month']}\n\n"
            f"Quyidagi ro'yxatdan <b>o'z ismingizni</b> tanlang:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    # 4b. Filial taklif havolasi (xodim uchun)
    if args:
        invite = await get_invite_token(args)
        if not invite:
            await message.answer(
                "⚠️ Noto'g'ri yoki eskirgan havola.\n"
                "Administrator bilan bog'laning."
            )
            return

        org_id    = invite['org_id']
        filial_id = invite['filial_id']

        await set_telegram_user_organization(user.id, org_id)

        hr_admins = await get_hr_admins_by_filial(filial_id)
        if not hr_admins:
            await message.answer(
                f"⚠️ <b>{invite['filial_name']}</b> filialida HR admin topilmadi.\n"
                "Administrator bilan bog'laning.",
                parse_mode="HTML"
            )
            return

        full_name      = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Ism ko'rsatilmagan"
        username_text  = f"@{user.username}" if user.username else "username yo'q"
        notification_text = (
            f"🔔 <b>Yangi xodim so'rovi!</b>\n\n"
            f"👤 Ism: {full_name}\n"
            f"📱 Username: {username_text}\n"
            f"🆔 Telegram ID: <code>{user.id}</code>\n"
            f"🏢 Tashkilot: {invite['org_name']}\n"
            f"🏬 Filial: {invite['filial_name']}\n\n"
            f"Ushbu xodimni tasdiqlaysizmi?"
        )
        approval_keyboard = get_user_approval_keyboard(user.id, org_id, filial_id)

        sent_count = 0
        for admin in hr_admins:
            if not admin.telegram_id:
                continue
            try:
                await bot.send_message(
                    chat_id=admin.telegram_id,
                    text=notification_text,
                    reply_markup=approval_keyboard,
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Admin {admin.telegram_id} ga xabar yuborishda xato: {e}")

        if sent_count > 0:
            await message.answer(
                f"✅ So'rovingiz <b>{invite['filial_name']}</b> filialining "
                f"HR adminlariga yuborildi.\n\n"
                "⏳ Tasdiqlangandan so'ng sizga xabar keladi.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "⚠️ Adminlarga xabar yuborishda muammo yuz berdi. "
                "Iltimos, keyinroq urinib ko'ring."
            )
        return

    # ── 5. Oddiy /start (hech qanday havola yo'q) ────────────
    await message.answer(
        "⚠️ Botdan foydalanish uchun tashkilot administratoridan "
        "<b>maxsus havola</b> oling.",
        parse_mode="HTML"
    )


# ============================================================
# RASM QABUL QILISH (xodim rasmi yo'q bo'lsa)
# ============================================================

@router.message(EmployeeRegistration.waiting_for_photo, F.photo)
async def receive_employee_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id

    await message.answer("⏳ Rasm tekshirilmoqda...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    save_dir = os.path.join("files", "employee_photos")
    os.makedirs(save_dir, exist_ok=True)
    file_name = f"emp_{user_id}.jpg"
    abs_path = os.path.join(save_dir, file_name)

    await bot.download_file(file.file_path, destination=abs_path)

    # Yuz aniqlash
    has_face = detect_face(abs_path)

    if not has_face:
        # Rasmni o'chirib tashlaymiz
        try:
            os.remove(abs_path)
        except Exception:
            pass
        await message.answer(
            "❌ <b>Rasm qabul qilinmadi.</b>\n\n"
            "Rasmda yuz aniqlanmadi yoki rasm sifati past.\n"
            "Iltimos, <b>yuzingiz to'liq va aniq ko'ringan holda</b> "
            "qayta rasm yuboring:",
            parse_mode="HTML"
        )
        return  # Holatni saqlaymiz — qayta rasm kutiladi

    # Rasmni bazaga saqlaymiz
    relative_path = os.path.join("employee_photos", file_name)
    saved = await save_employee_photo(user_id=user_id, photo_path=relative_path)

    if saved:
        await state.clear()
        await message.answer(
            "✅ <b>Rasm qabul qilindi!</b>\n\n"
            "Ro'yxatdan o'tish yakunlandi. Kirish uchun quyidagi tugmani bosing:",
            parse_mode="HTML",
            reply_markup=await employee_main_keyboard()
        )
    else:
        await message.answer(
            "❌ Rasm saqlanishda xatolik yuz berdi.\n"
            "Iltimos, qayta urinib ko'ring."
        )


@router.message(EmployeeRegistration.waiting_for_photo, ~F.photo)
async def receive_wrong_input_photo(message: Message):
    await message.answer(
        "❌ Iltimos, faqat <b>rasm</b> yuboring.\n\n"
        "📌 Eslatma: Faylni hujjat sifatida emas, oddiy rasm sifatida yuboring.",
        parse_mode="HTML"
    )


# ============================================================
# TINGLOVCHI O'Z ISMINI TANLASHI
# ============================================================

@router.callback_query(
    StudentGroupSelect.selecting,
    F.data.startswith("student_select:")
)
async def student_selected(callback: CallbackQuery, state: FSMContext):
    _, student_id, group_id = callback.data.split(":")

    result = await link_student_telegram(
        student_id=int(student_id),
        telegram_id=callback.from_user.id,
    )

    await state.clear()

    if not result:
        await callback.message.edit_text(
            "❌ Xatolik yuz berdi. Administrator bilan bog'laning."
        )
        return

    text = (
        f"✅ Ro'yxatdan o'tdingiz!\n\n"
        f"👤 Ism: <b>{result['full_name']}</b>\n\n"
        f"🔑 Login: <code>{result['login']}</code>\n"
        f"🔒 Parol: <code>{result['password']}</code>\n\n"
        f"⚠️ Login va parolni eslab qoling!"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.message.answer(
        "📋 Asosiy menyu:",
        reply_markup=student_main_keyboard()
    )
