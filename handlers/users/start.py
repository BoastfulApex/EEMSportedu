import os
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, bot
from states.users import EmployeeRegistration, StudentGroupSelect, StudentPhotoUpload, EmployeeNameInput
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
    has_student_photo,
    is_edu_admin_user,
    update_telegram_user_name,
    get_user_roles_info,
)
from utils.face_check import detect_face

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)


# ============================================================
# /start — asosiy kirish nuqtasi
# ============================================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    user = message.from_user
    args = command.args

    # Har qanday holatdan /start ishlashi uchun — eski holatni tozalaymiz
    await state.clear()

    await get_or_create_telegram_user(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
    )

    # ── Foydalanuvchi rollarini bir marta olamiz ───────────────
    info = await get_user_roles_info(user.id)

    # ── Salomlashish matni (ism + rollar) ─────────────────────
    def _build_greeting(info: dict) -> str:
        lines = ["👋 <b>Assalomu alaykum!</b>\n"]
        if info['is_admin']:
            name = info['admin_name'] or user.first_name or ""
            lines.append(f"👤 <b>{name}</b>")
            lines.append(f"🔑 Rol: <b>{info['admin_role_label']}</b>")
        if info['is_employee']:
            emp_name = info['employee_name'] or (info['admin_name'] if info['is_admin'] else user.first_name) or ""
            if not info['is_admin']:
                lines.append(f"👤 <b>{emp_name}</b>")
            lines.append(f"🏢 Rol: <b>Xodim</b>")
        if info['is_student']:
            stu_name = info['student_name'] or user.first_name or ""
            lines.append(f"👤 <b>{stu_name}</b>")
            lines.append(f"🎓 Rol: <b>Tinglovchi</b>")
        lines.append("\nQuyidagi bo'limlardan birini tanlang:")
        return "\n".join(lines)

    # ── 1. Admin ─────────────────────────────────────────────
    if info['is_admin']:
        greeting = _build_greeting(info)

        # Edu admin
        if info['is_edu_admin']:
            from keyboards.inline.main_inline import edu_admin_keyboard, edu_admin_employee_keyboard
            if info['is_employee']:
                if await has_employee_photo(user.id):
                    await message.answer(greeting, parse_mode="HTML",
                                         reply_markup=edu_admin_employee_keyboard())
                else:
                    await state.set_state(EmployeeRegistration.waiting_for_photo)
                    await state.update_data(is_admin=True)
                    await message.answer(
                        greeting + "\n\n📸 <b>Yuz rasmingiz saqlanmagan.</b>\n"
                        "Iltimos, yuzingiz aniq ko'rinib turgan rasmingizni yuboring:",
                        parse_mode="HTML"
                    )
            else:
                await message.answer(greeting, parse_mode="HTML",
                                     reply_markup=edu_admin_keyboard())
            return

        # Oddiy admin
        from keyboards.inline.menu_button import admin_menu_keyboard
        await message.answer(greeting, parse_mode="HTML",
                             reply_markup=await admin_menu_keyboard())
        if info['is_employee']:
            if await has_employee_photo(user.id):
                await message.answer("👇 Xodim sifatida davomat:",
                                     reply_markup=await employee_main_keyboard())
            else:
                await state.set_state(EmployeeRegistration.waiting_for_photo)
                await state.update_data(is_admin=True)
                await message.answer(
                    "📸 <b>Yuz rasmingiz saqlanmagan.</b>\n"
                    "Iltimos, yuzingiz aniq ko'rinib turgan rasmingizni yuboring:",
                    parse_mode="HTML"
                )
        return

    # ── 2. Xodim ─────────────────────────────────────────────
    if info['is_employee']:
        greeting = _build_greeting(info)
        if await has_employee_photo(user.id):
            await message.answer(greeting, parse_mode="HTML",
                                 reply_markup=await employee_main_keyboard())
        else:
            await state.set_state(EmployeeRegistration.waiting_for_photo)
            await message.answer(
                greeting + "\n\n📸 <b>Yuz rasmingiz saqlanmagan.</b>\n"
                "Iltimos, yuzingiz aniq ko'rinib turgan rasmingizni yuboring:",
                parse_mode="HTML"
            )
        return

    # ── 3. Tinglovchi ────────────────────────────────────────
    if info['is_student']:
        greeting = _build_greeting(info)
        if await has_student_photo(user.id):
            await message.answer(greeting, parse_mode="HTML",
                                 reply_markup=student_main_keyboard())
        else:
            await state.set_state(StudentPhotoUpload.waiting_for_photo)
            await message.answer(
                greeting + "\n\n📸 <b>Yuz rasmingiz saqlanmagan.</b>\n"
                "Iltimos, yuzingiz aniq ko'rinib turgan rasmingizni yuboring:",
                parse_mode="HTML"
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

        # Invite ma'lumotlarini state ga saqlab, avval ism-familiya so'raymiz
        await state.set_state(EmployeeNameInput.waiting_for_name)
        await state.update_data(
            org_id=invite['org_id'],
            filial_id=invite['filial_id'],
            org_name=invite['org_name'],
            filial_name=invite['filial_name'],
        )

        await set_telegram_user_organization(user.id, invite['org_id'])

        await message.answer(
            f"👋 Assalomu alaykum!\n\n"
            f"🏢 <b>{invite['org_name']}</b>\n"
            f"🏬 <b>{invite['filial_name']}</b>\n\n"
            f"Iltimos, <b>ism va familiyangizni</b> kiriting:\n"
            f"<i>Masalan: Abdullayev Jasur</i>",
            parse_mode="HTML"
        )
        return

    # ── 5. Noma'lum foydalanuvchi ────────────────────────────
    await message.answer(
        "⚠️ <b>Botdan foydalanish uchun</b> tashkilot administratoridan "
        "maxsus havola oling, yoki login parol orqali ro'yxatdan o'ting.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔐 Login orqali kirish",
                callback_data="student_login_start"
            )]
        ])
    )


# ============================================================
# XODIM ISM-FAMILIYASI KIRITILISHI
# ============================================================

@router.message(EmployeeNameInput.waiting_for_name, F.text)
async def receive_employee_name(message: Message, state: FSMContext):
    full_name = message.text.strip()

    # Juda qisqa ism tekshiruvi
    if len(full_name) < 3:
        await message.answer(
            "❌ Ism juda qisqa. Iltimos, <b>to'liq ism va familiyangizni</b> kiriting:\n"
            "<i>Masalan: Abdullayev Jasur</i>",
            parse_mode="HTML"
        )
        return

    data      = await state.get_data()
    org_id    = data['org_id']
    filial_id = data['filial_id']
    org_name  = data['org_name']
    filial_name = data['filial_name']

    await state.clear()

    user = message.from_user

    # Kiritilgan ismni TelegramUser ga saqlaymiz —
    # approve_emp_callback shu yozuvdan o'qiydi
    await update_telegram_user_name(user.id, full_name)
    username_text  = f"@{user.username}" if user.username else "username yo'q"

    hr_admins = await get_hr_admins_by_filial(filial_id)
    if not hr_admins:
        await message.answer(
            f"⚠️ <b>{filial_name}</b> filialida HR admin topilmadi.\n"
            "Administrator bilan bog'laning.",
            parse_mode="HTML"
        )
        return

    notification_text = (
        f"🔔 <b>Yangi xodim so'rovi!</b>\n\n"
        f"👤 Ism: <b>{full_name}</b>\n"
        f"📱 Username: {username_text}\n"
        f"🆔 Telegram ID: <code>{user.id}</code>\n"
        f"🏢 Tashkilot: {org_name}\n"
        f"🏬 Filial: {filial_name}\n\n"
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
            f"✅ So'rovingiz <b>{filial_name}</b> filialining HR adminlariga yuborildi.\n\n"
            "⏳ Tasdiqlangandan so'ng sizga xabar keladi.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "⚠️ Adminlarga xabar yuborishda muammo yuz berdi. "
            "Iltimos, keyinroq urinib ko'ring."
        )


@router.message(EmployeeNameInput.waiting_for_name, ~F.text)
async def receive_employee_name_wrong(message: Message):
    await message.answer(
        "❌ Iltimos, faqat <b>matn</b> ko'rinishida ism-familiyangizni yozing.",
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

    from django.conf import settings
    save_dir = os.path.join(settings.MEDIA_ROOT, "employee_photos")
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
        data = await state.get_data()
        is_admin_flag = data.get('is_admin', False)
        await state.clear()

        # Admin ham xodim bo'lsa — rol ga mos keyboard ko'rsatamiz
        if is_admin_flag and await is_edu_admin_user(user_id):
            from keyboards.inline.main_inline import edu_admin_employee_keyboard
            reply_markup = edu_admin_employee_keyboard()
        else:
            reply_markup = await employee_main_keyboard()

        await message.answer(
            "✅ <b>Rasm qabul qilindi!</b>\n\n"
            "Ro'yxatdan o'tish yakunlandi. Kirish uchun quyidagi tugmani bosing:",
            parse_mode="HTML",
            reply_markup=reply_markup
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

    # Ro'yxatdan o'tgandan so'ng darhol yuz rasmini so'rash
    await state.set_state(StudentPhotoUpload.waiting_for_photo)
    await callback.message.answer(
        "📸 Tizimga kirish uchun <b>yuz rasmingiz</b> kerak.\n\n"
        "Iltimos, <b>yuzingiz aniq ko'rinib turgan</b> rasmingizni yuboring:",
        parse_mode="HTML"
    )
