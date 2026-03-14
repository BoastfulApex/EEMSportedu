import re
import logging
from datetime import datetime

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile

from loader import dp, bot
from data import config
from keyboards.inline.menu_button import (
    admin_menu_keyboard,
    cancel,
    address_bottom_keyboard,
    empty_address_keyboard,
)
from keyboards.inline.main_inline import (
    generate_weekday_keyboard,
    generate_approve_weekday_keyboard,
    get_filial_keyboard_for_employee,
    get_more_schedule_keyboard,
    employee_main_keyboard,
)
from utils.db_api.database import (
    add_employee,
    get_telegram_user,
    delete_employee_by_user_id,
    save_work_schedule,
    get_employee_schedule_text,
    get_filial_location,
    get_location_name,
    save_location,
    generate_attendance_excel_file,
    get_hr_admins_by_org,
    get_filials_by_org_objects,
    create_employee_with_filial,
    save_work_schedule_by_weekday_names,
)
from states.admin import (
    EmployeeForm,
    AddLocation,
    ApproveEmployee,
    SetEmployeeForm,
    ChartsForm,
)

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)
channel_id = config.CHANNEL_ID


# ============================================================
# ADMIN MENYU NAVIGATSIYA
# ============================================================

@router.message(StateFilter(None), F.text == "🔙 Bekor qilish")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=await admin_menu_keyboard())


@router.message(StateFilter(None), F.text == "🧑‍💼 Xodim qo'shish")
async def start_add_employee(message: Message, state: FSMContext):
    await message.answer("Xodimning Telegram user_id sini kiriting:", reply_markup=cancel)
    await state.set_state(EmployeeForm.get_id)


@router.message(F.text, EmployeeForm.get_id)
async def process_user_id(message: Message, state: FSMContext):
    await state.update_data(user_id=message.text)
    await message.answer("Xodimning to'liq ismini kiriting:", reply_markup=cancel)
    await state.set_state(EmployeeForm.get_name)


@router.message(F.text, EmployeeForm.get_name)
async def process_full_name(message: Message, state: FSMContext):
    data = await state.get_data()
    await add_employee(
        admin_id=message.from_user.id,
        user_id=data["user_id"],
        full_name=message.text
    )
    await state.clear()
    await message.answer("✅ Xodim qo'shildi!", reply_markup=await admin_menu_keyboard())


# ============================================================
# HISOBOT
# ============================================================

@router.message(StateFilter(None), F.text == "📊 Hisobotlar")
async def start_report(message: Message, state: FSMContext):
    await message.answer(
        "🕐 Sana oralig'ini kiriting (masalan: `01.01.2025 - 31.05.2025`):",
        reply_markup=cancel
    )
    await state.set_state(ChartsForm.get_date)


@router.message(ChartsForm.get_date)
async def process_date_range(message: Message, state: FSMContext):
    date_text = message.text.strip()
    pattern = r"^(\d{2})\.(\d{2})\.(\d{4})\s*-\s*(\d{2})\.(\d{2})\.(\d{4})$"
    match = re.match(pattern, date_text)
    if not match:
        await message.answer("❌ Noto'g'ri format! Masalan: `01.01.2025 - 31.05.2025`")
        return
    try:
        start_date = datetime.strptime(
            f"{match.group(1)}.{match.group(2)}.{match.group(3)}", "%d.%m.%Y"
        )
        end_date = datetime.strptime(
            f"{match.group(4)}.{match.group(5)}.{match.group(6)}", "%d.%m.%Y"
        )
    except ValueError:
        await message.answer("❌ Sana mavjud emas. Iltimos, haqiqiy sanalarni kiriting.")
        return
    if start_date > end_date:
        await message.answer("❌ Boshlanish sanasi tugash sanasidan oldin bo'lishi kerak.")
        return

    file_path = await generate_attendance_excel_file(
        start_date=start_date,
        end_date=end_date,
        user_id=message.from_user.id
    )
    file = FSInputFile(file_path, filename="hisobot.xlsx")
    await message.answer_document(file, caption="📊 Hisobot tayyor!")
    await message.answer(
        f"✅ {start_date.date()} — {end_date.date()}",
        reply_markup=await admin_menu_keyboard()
    )
    await state.clear()


# ============================================================
# MANZILLAR
# ============================================================

@router.message(StateFilter(None), F.text == "📍 Manzillar")
async def show_latest_location(message: Message):
    location = await get_filial_location(message.from_user.id)
    if location:
        await message.answer(
            f"📍 So'nggi manzil: {location.name or 'Noma\'lum'}",
            reply_markup=address_bottom_keyboard()
        )
        if location.latitude and location.longitude:
            await message.answer_location(
                latitude=location.latitude,
                longitude=location.longitude
            )
    else:
        await message.answer("❌ Hozircha manzillar mavjud emas.", reply_markup=empty_address_keyboard())


@router.message(StateFilter(None), F.text.in_(["➕ Manzil qo'shish", "✏️ Manzilni yangilash"]))
async def ask_for_location(message: Message, state: FSMContext):
    await message.answer("📍 Yangi manzil lokatsiyasini yuboring (Telegram joylashuv).")
    await state.set_state(AddLocation.waiting_for_location)


@router.message(AddLocation.waiting_for_location, F.location)
async def save_user_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    name = await get_location_name(lat, lon)
    await save_location(name=name, lat=lat, lon=lon, user_id=message.from_user.id)
    await state.clear()
    await message.answer(f"✅ Manzil qo'shildi:\n📍 {name}", reply_markup=await admin_menu_keyboard())


# ============================================================
# XODIMNI TASDIQLASH — YANGI FLOW
# ============================================================

@router.callback_query(lambda c: c.data.startswith("approve_emp:"))
async def approve_emp_callback(callback: CallbackQuery, state: FSMContext):
    """
    Format: approve_emp:{emp_user_id}:{org_id}
    Admin filial tanlashga o'tadi.
    """
    parts = callback.data.split(":")
    emp_user_id = int(parts[1])
    org_id = int(parts[2])

    # Admin FSM ga ma'lumot saqlaymiz
    tg_user = await get_telegram_user(emp_user_id)
    full_name = ""
    if tg_user:
        full_name = f"{tg_user.first_name or ''} {tg_user.last_name or ''}".strip()

    await state.update_data(
        emp_user_id=emp_user_id,
        emp_name=full_name,
        org_id=org_id,
        filial_id=None,
        selected_weekdays=[],
        schedules=[],
    )

    # Org filiallarini olamiz
    filials = await get_filials_by_org_objects(org_id)
    if not filials:
        await callback.message.edit_text("❌ Bu tashkilotda filial topilmadi.")
        await callback.answer()
        return

    keyboard = get_filial_keyboard_for_employee(filials, emp_user_id)
    await state.set_state(ApproveEmployee.selecting_filial)
    await callback.message.edit_text(
        f"👤 Xodim: <b>{full_name}</b>\n\n"
        "📍 Xodim qaysi filialda ishlaydi?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("emp_filial:"), StateFilter(ApproveEmployee.selecting_filial))
async def select_filial_for_employee(callback: CallbackQuery, state: FSMContext):
    """
    Format: emp_filial:{filial_id}:{emp_user_id}
    Filial tanlangandan so'ng hafta kunlari tanlanadi.
    """
    parts = callback.data.split(":")
    filial_id = int(parts[1])

    await state.update_data(filial_id=filial_id, selected_weekdays=[])
    await state.set_state(ApproveEmployee.selecting_weekdays)

    keyboard = generate_approve_weekday_keyboard(set())
    await callback.message.edit_text(
        "📆 Hafta kunlarini tanlang (bir nechta tanlash mumkin):",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("awday:"), StateFilter(ApproveEmployee.selecting_weekdays))
async def toggle_approve_weekday(callback: CallbackQuery, state: FSMContext):
    """Hafta kunini tanlash/bekor qilish"""
    weekday_name = callback.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("selected_weekdays", []))

    if weekday_name in selected:
        selected.remove(weekday_name)
    else:
        selected.add(weekday_name)

    await state.update_data(selected_weekdays=list(selected))
    keyboard = generate_approve_weekday_keyboard(selected)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "awday_done", StateFilter(ApproveEmployee.selecting_weekdays))
async def approve_weekday_done(callback: CallbackQuery, state: FSMContext):
    """Kunlar tanlandi — vaqt kiritishga o'tadi"""
    data = await state.get_data()
    selected = data.get("selected_weekdays", [])

    if not selected:
        await callback.answer("⛔ Hech qanday kun tanlanmagan.", show_alert=True)
        return

    await state.set_state(ApproveEmployee.waiting_for_time_range)
    await callback.message.edit_text(
        f"✅ Tanlangan kunlar: <b>{', '.join(selected)}</b>\n\n"
        "🕐 Ish vaqtini kiriting (masalan: <code>09:00 - 18:00</code>):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ApproveEmployee.waiting_for_time_range, F.text)
async def approve_receive_time_range(message: Message, state: FSMContext):
    """Vaqt qabul qilinadi, jadval ro'yxatga qo'shiladi"""
    text = message.text.strip()
    try:
        start_str, end_str = map(str.strip, text.split("-"))
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        if start_time >= end_time:
            raise ValueError("Boshlanish vaqti tugash vaqtidan katta bo'lmasligi kerak.")
    except Exception as e:
        await message.answer(
            f"⛔ Noto'g'ri format: {e}\n"
            "Iltimos, <code>09:00 - 18:00</code> shaklida yozing.",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    selected_weekdays = data.get("selected_weekdays", [])
    schedules = data.get("schedules", [])

    schedules.append({
        "weekdays": selected_weekdays,
        "start": start_str.strip(),
        "end": end_str.strip(),
    })
    await state.update_data(schedules=schedules, selected_weekdays=[])

    # Qo'shilgan jadvallar ro'yxati
    schedule_text = "\n".join(
        f"  • {', '.join(s['weekdays'])} | {s['start']} - {s['end']}"
        for s in schedules
    )

    await state.set_state(ApproveEmployee.confirm_more_schedules)
    await message.answer(
        f"✅ Jadval qo'shildi:\n{schedule_text}\n\n"
        "Yana jadval qo'shmoqchimisiz?",
        reply_markup=get_more_schedule_keyboard()
    )


@router.callback_query(lambda c: c.data == "more_sched", StateFilter(ApproveEmployee.confirm_more_schedules))
async def add_more_schedule(callback: CallbackQuery, state: FSMContext):
    """Yana bir jadval qo'shish — hafta kunlariga qaytadi"""
    await state.update_data(selected_weekdays=[])
    await state.set_state(ApproveEmployee.selecting_weekdays)

    keyboard = generate_approve_weekday_keyboard(set())
    await callback.message.edit_text(
        "📆 Keyingi jadval uchun hafta kunlarini tanlang:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "finish_sched", StateFilter(ApproveEmployee.confirm_more_schedules))
async def finish_schedule_assignment(callback: CallbackQuery, state: FSMContext):
    """
    Jadval tayinlash tugadi.
    1. Xodim yaratiladi.
    2. Barcha jadvallar saqlanadi.
    3. Xodimga rasm so'rash xabari yuboriladi.
    """
    data = await state.get_data()
    emp_user_id = data["emp_user_id"]
    emp_name = data["emp_name"]
    filial_id = data["filial_id"]
    schedules = data.get("schedules", [])
    admin_id = callback.from_user.id

    # 1. Xodim yaratish
    employee = await create_employee_with_filial(
        user_id=emp_user_id,
        full_name=emp_name,
        filial_id=filial_id,
    )
    if not employee:
        await callback.message.edit_text("❌ Xodim yaratishda xatolik yuz berdi.")
        await state.clear()
        await callback.answer()
        return

    # 2. Jadvallarni saqlash
    for sched in schedules:
        start_t = datetime.strptime(sched["start"], "%H:%M").time()
        end_t = datetime.strptime(sched["end"], "%H:%M").time()
        await save_work_schedule_by_weekday_names(
            employee_user_id=emp_user_id,
            weekday_names=sched["weekdays"],
            start_time=start_t,
            end_time=end_t,
            admin_telegram_id=admin_id,
        )

    # Jadval matni
    jadval_text = await get_employee_schedule_text(emp_user_id)

    # 3. Xodimga xabar: tasdiqlandingiz + rasm so'rash
    from states.users import EmployeeRegistration
    from aiogram.fsm.context import FSMContext as _FSMContext
    from loader import dp as _dp

    try:
        await bot.send_message(
            chat_id=emp_user_id,
            text=(
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"Siz <b>xodim</b> sifatida tasdiqlandi.\n\n"
                f"{jadval_text}\n\n"
                f"📸 Endi <b>yuzingiz aniq ko'rinib turgan</b> rasmingizni yuboring.\n"
                f"Bu rasm davomat tizimi uchun kerak."
            ),
            parse_mode="HTML"
        )
        # Xodim FSM holatini waiting_for_photo ga o'rnatamiz
        # (xodim tomonida state o'rnatish uchun storage ga to'g'ridan-to'g'ri yozamiz)
        from aiogram.fsm.storage.base import StorageKey
        storage = _dp.storage
        key = StorageKey(
            bot_id=bot.id,
            chat_id=emp_user_id,
            user_id=emp_user_id
        )
        await storage.set_state(key=key, state=EmployeeRegistration.waiting_for_photo)

    except Exception as e:
        logger.error(f"Xodimga xabar yuborishda xato (user_id={emp_user_id}): {e}")

    # Admin uchun tasdiqlash tugadi
    schedule_summary = "\n".join(
        f"  • {', '.join(s['weekdays'])} | {s['start']} - {s['end']}"
        for s in schedules
    )
    await callback.message.edit_text(
        f"✅ <b>Xodim tasdiqlandi!</b>\n\n"
        f"👤 {emp_name}\n\n"
        f"📅 Jadvallar:\n{schedule_summary}\n\n"
        f"Xodimdan rasm kutilmoqda...",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()


# ============================================================
# XODIMNI RAD ETISH
# ============================================================

@router.callback_query(lambda c: c.data.startswith("reject_emp:"))
async def reject_emp_callback(callback: CallbackQuery, state: FSMContext):
    """Format: reject_emp:{emp_user_id}"""
    emp_user_id = int(callback.data.split(":")[1])

    try:
        await bot.send_message(
            chat_id=emp_user_id,
            text="❌ Administrator sizning so'rovingizni rad etdi.\n\n"
                 "Boshqa ma'lumot uchun tashkilot administratori bilan bog'laning."
        )
    except Exception as e:
        logger.error(f"Rad xabari yuborishda xato (user_id={emp_user_id}): {e}")

    await delete_employee_by_user_id(emp_user_id)
    await state.clear()
    await callback.message.edit_text("🔴 Xodim so'rovi rad etildi.")
    await callback.answer("Rad javobi yuborildi.")


# ============================================================
# ESKI FLOW — manuel jadval tayinlash (SetEmployeeForm)
# ============================================================

@router.callback_query(lambda c: c.data.startswith("approve_user:"))
async def approve_user_callback_legacy(callback: CallbackQuery, state: FSMContext):
    """Eski approve_user format — orqaga moslik uchun"""
    user_id = int(callback.data.split(":")[1])
    user = await callback.bot.get_chat(user_id)
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    await add_employee(
        user_id=user_id,
        full_name=full_name,
        admin_id=callback.from_user.id
    )
    await callback.message.edit_text("🟢 Foydalanuvchi tasdiqlandi.")
    await state.update_data(selected_weekdays=set(), employee_id=user_id)

    keyboard = generate_weekday_keyboard(set())
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text="📆 Hafta kunlarini tanlang:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("reject_user:"))
async def reject_user_callback_legacy(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    try:
        await callback.bot.send_message(
            chat_id=user_id,
            text="❌ Administrator sizning so'rovingizni rad etdi."
        )
    except Exception:
        pass
    await delete_employee_by_user_id(user_id)
    await callback.message.edit_text("🔴 Foydalanuvchi rad etildi.")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("select_weekday:"))
async def select_weekday_callback(callback: CallbackQuery, state: FSMContext):
    weekday_name = callback.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("selected_weekdays", set()))
    if weekday_name in selected:
        selected.remove(weekday_name)
    else:
        selected.add(weekday_name)
    await state.update_data(selected_weekdays=selected)
    keyboard = generate_weekday_keyboard(selected)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "continue_schedule")
async def continue_to_time(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_weekdays", set())
    if not selected:
        await callback.answer("⛔ Hech qanday kun tanlanmagan.", show_alert=True)
        return
    await callback.message.edit_text(
        "🕐 Ish vaqtini kiriting (masalan: <code>09:00 - 18:00</code>):",
        parse_mode="HTML"
    )
    await state.set_state(SetEmployeeForm.waiting_for_time_range)
    await callback.answer()


@router.message(SetEmployeeForm.waiting_for_time_range, F.text)
async def receive_time_range(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        start_str, end_str = map(str.strip, text.split("-"))
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        if start_time >= end_time:
            raise ValueError("Boshlanish vaqti tugash vaqtidan katta bo'lmasligi kerak.")

        await state.update_data(start=start_time, end=end_time)
        data = await state.get_data()
        await save_work_schedule(message.from_user.id, data)

        jadval_text = await get_employee_schedule_text(data["employee_id"])
        try:
            await bot.send_message(
                chat_id=data["employee_id"],
                text=f"✅ Administrator sizni tasdiqladi.\n\n{jadval_text}"
            )
        except Exception as e:
            logger.error(f"Jadval xabari yuborishda xato: {e}")

        await state.clear()
        await message.answer("✅ Ish jadvali saqlandi!", reply_markup=await admin_menu_keyboard())

    except Exception as e:
        await message.answer(
            f"⛔ Noto'g'ri format: {e}\n"
            "Iltimos, <code>09:00 - 18:00</code> shaklida yozing.",
            parse_mode="HTML"
        )


@router.callback_query(lambda c: c.data == "back_to_start")
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("employee_id")
    user = await get_telegram_user(user_id)
    if not user:
        await callback.message.edit_text("❌ Foydalanuvchi topilmadi.")
        return
    from keyboards.inline.main_inline import get_user_approval_keyboard
    # Eski format (approve_user) uchun moslik
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_user:{user_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_user:{user_id}"),
    ]])
    await callback.message.edit_text(
        f"👤 {user.first_name} {user.last_name or ''}\n"
        f"🆔 {user.user_id}\n\nTasdiqlaysizmi?",
        reply_markup=keyboard
    )
    await callback.answer()


# ============================================================
# KANAL HISOBOTI
# ============================================================

@router.channel_post(F.text.in_(["SendPostNotification"]))
async def send_report(message: types.Message):
    from apps.superadmin.models import Filial, Administrator
    from utils.db_api.database import get_daily_report

    filials = Filial.objects.all()
    for filial in filials:
        report = await get_daily_report(filial)
        admins = Administrator.objects.filter(filial=filial).all()
        for admin in admins:
            if admin.telegram_id:
                try:
                    await bot.send_message(
                        chat_id=admin.telegram_id,
                        text=f"📊 {filial.filial_name} uchun kunlik hisobot:\n\n{report}"
                    )
                except Exception:
                    pass
