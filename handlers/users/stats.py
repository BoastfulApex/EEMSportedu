"""
Xodim statistika handleri.
Xodim o'z ish soatlari va kun statistikasini ko'radi.
"""
import calendar as cal_mod
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery

from loader import dp
from keyboards.inline.main_inline import months_keyboard, employee_main_keyboard
from utils.db_api.database import get_available_months, get_employee_monthly_stats

router = Router()
dp.include_router(router)


# ============================================================
# "Mening statistikam" tugmasi bosildi
# ============================================================

@router.callback_query(F.data == "my_stats", StateFilter(None))
async def show_months(callback: CallbackQuery):
    user_id = callback.from_user.id
    months = await get_available_months(user_id)

    if not months:
        await callback.message.edit_text(
            "📭 Hozircha davomat ma'lumotlari topilmadi.\n"
            "Kirish/chiqish qayd etilgandan so'ng statistika paydo bo'ladi."
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📅 Qaysi oyni ko'rmoqchisiz?",
        reply_markup=months_keyboard(months)
    )
    await callback.answer()


# ============================================================
# Oy tanlandi
# ============================================================

@router.callback_query(F.data.startswith("stats_"), StateFilter(None))
async def show_month_stats(callback: CallbackQuery):
    _, year, month = callback.data.split("_")
    year, month = int(year), int(month)
    user_id = callback.from_user.id

    stats = await get_employee_monthly_stats(user_id, year, month)

    if not stats:
        await callback.message.edit_text("❌ Ma'lumot topilmadi.")
        await callback.answer()
        return

    # Foiz progress bar
    percent = stats.get('percent')
    if percent is not None:
        filled = int(percent / 10)
        bar = "🟩" * filled + "⬜" * (10 - filled)
        percent_line = f"\n{bar} {percent}%"
        needed_line  = f"\n📋 Kerakli soat: <b>{stats['monthly_hours']} soat</b>"
    else:
        percent_line = ""
        needed_line  = "\n📋 Kerakli soat: <i>kiritilmagan</i>"

    # Joriy oy belgisi
    from datetime import date
    today = date.today()
    is_current = (year == today.year and month == today.month)
    current_badge = " <i>(joriy oy)</i>" if is_current else ""

    text = (
        f"📅 <b>{cal_mod.month_name[month]} {year}</b>{current_badge}\n"
        f"{'─' * 28}\n"
        f"✅ Kelgan kunlar: <b>{stats['came_days']}</b> / {stats['work_days_in_month']}\n"
        f"⏱ Ishlagan soat: <b>{stats['total_hours']} soat</b>"
        f"{needed_line}"
        f"{percent_line}"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Oylar ro'yxatiga", callback_data="my_stats")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb)
    await callback.answer()


# ============================================================
# Orqaga — asosiy menyuga
# ============================================================

@router.callback_query(F.data == "back_to_main", StateFilter(None))
async def back_to_main(callback: CallbackQuery):
    keyboard = await employee_main_keyboard()
    await callback.message.edit_text(
        "Asosiy menyu:",
        reply_markup=keyboard
    )
    await callback.answer()
