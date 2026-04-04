"""
Xodim hisobot handlerlari.

Menyular:
  my_reports          → haftalik + oylik overview + menyu
  rep_daily_months    → kunlik hisobot uchun oy tanlash
  rep_daily_{y}_{m}   → tanlangan oy kunlik jadvali
  rep_late_months     → kechikkan kunlar uchun oy tanlash
  rep_late_{y}_{m}    → tanlangan oy kechikkan kunlar
  rep_daterange       → sana bo'yicha hisobot (FSM)
"""

import calendar as cal_mod
from datetime import datetime, date

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp
from states.users import ReportDateRange
from keyboards.inline.main_inline import (
    employee_main_keyboard,
    reports_menu_keyboard,
    report_months_keyboard,
)
from utils.db_api.database import (
    get_emp_weekly_monthly_stats,
    get_emp_daily_report_month,
    get_emp_late_days_month,
    get_emp_stats_period,
    get_report_months_for_employee,
)

router = Router()
dp.include_router(router)

_UZ_MONTHS = {
    1:'Yanvar', 2:'Fevral', 3:'Mart', 4:'Aprel', 5:'May', 6:'Iyun',
    7:'Iyul', 8:'Avgust', 9:'Sentabr', 10:'Oktabr', 11:'Noyabr', 12:'Dekabr',
}


# ─────────────────────────────────────────────────────────────
# Yordamchi: progress bar matni
# ─────────────────────────────────────────────────────────────
def _progress_bar(pct: float) -> str:
    filled = min(10, int(pct / 10))
    bar = "🟩" * filled + "⬜" * (10 - filled)
    return f"{bar} {pct}%"


def _fmt_time(minutes: int) -> str:
    if minutes == 0:
        return "—"
    h, m = divmod(minutes, 60)
    if h:
        return f"{h}s {m}d" if m else f"{h}s"
    return f"{m}d"


def _stats_block(s: dict) -> str:
    """Bitta statistika bloki matni (haftalik yoki oylik card uchun)."""
    lines = [
        f"  📋 Kerakli: <b>{s['required_h']}s</b>  |  Ishlagan: <b>{s['worked_h']}s</b>",
        f"  {_progress_bar(s['progress'])}",
        f"  ⏰ Kechikish: <b>{_fmt_time(s['late_total'])}</b>"
        f"  |  ✅ Ortiqcha: <b>{_fmt_time(s['overtime_total'])}</b>",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# OVERVIEW — haftalik + oylik bitta xabarda
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_reports", StateFilter(None))
async def show_reports_overview(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Student bo'lsa student hisobotiga yo'naltir
    from utils.db_api.database import is_user_student, get_student_report_months
    if await is_user_student(user_id):
        months = await get_student_report_months(user_id)
        if not months:
            await callback.message.edit_text(
                "📭 Hozircha davomat ma'lumotlari topilmadi.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
                ])
            )
            await callback.answer()
            return
        buttons = [
            [InlineKeyboardButton(text=m['label'], callback_data=f"srep_{m['year']}_{m['month']}")]
            for m in months
        ]
        buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")])
        await callback.message.edit_text(
            "📊 <b>Davomat hisoboti</b>\nQaysi oyni ko'rmoqchisiz?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer()
        return

    data = await get_emp_weekly_monthly_stats(user_id)

    if not data:
        await callback.message.edit_text(
            "❌ Xodim ma'lumoti topilmadi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
        return

    w = data['weekly']
    m = data['monthly']
    ws = data['week_start']
    td = data['today']

    text = (
        f"📊 <b>Hisobotlaringiz</b>\n"
        f"{'─' * 30}\n\n"

        f"📆 <b>Haftalik</b>  "
        f"<i>{ws.strftime('%d-%b')} – {td.strftime('%d-%b')}</i>\n"
        f"{_stats_block(w)}\n\n"

        f"📅 <b>Oylik</b>  "
        f"<i>{data['month_label']} · {data['month_start'].strftime('%d-%b')} – {td.strftime('%d-%b')}</i>\n"
        f"{_stats_block(m)}"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=reports_menu_keyboard()
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# KUNLIK HISOBOT — oy tanlash
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "rep_daily_months", StateFilter(None))
async def show_daily_months(callback: CallbackQuery):
    months = await get_report_months_for_employee(callback.from_user.id)
    if not months:
        await callback.message.edit_text(
            "📭 Davomat ma'lumotlari topilmadi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Hisobotlar", callback_data="my_reports")]
            ])
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📋 <b>Kunlik hisobot</b>\nQaysi oyni ko'rmoqchisiz?",
        parse_mode="HTML",
        reply_markup=report_months_keyboard(months, "rep_daily")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_daily_"), StateFilter(None))
async def show_daily_for_month(callback: CallbackQuery):
    _, _, year_s, month_s = callback.data.split("_")
    year, month = int(year_s), int(month_s)
    user_id = callback.from_user.id

    rows = await get_emp_daily_report_month(user_id, year, month)
    month_name = f"{_UZ_MONTHS[month]} {year}"

    if not rows:
        await callback.message.edit_text(
            f"📭 <b>{month_name}</b> uchun ma'lumot topilmadi.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Hisobotlar", callback_data="my_reports")]
            ])
        )
        await callback.answer()
        return

    lines = [f"📋 <b>{month_name} — Kunlik davomat</b>\n{'─'*28}"]
    for r in rows:
        d_str = r['date'].strftime('%d-%b')
        day   = r['day_uz']

        if r['status'] == 'Kelgan':
            ci = r['check_in'].strftime('%H:%M')  if r['check_in']  else '—'
            co = r['check_out'].strftime('%H:%M') if r['check_out'] else '—'
            worked = f"{r['worked_h']}s {r['worked_m']}d" if r['worked_h'] or r['worked_m'] else '—'

            late_txt = ""
            if r['late_min'] > 0:
                late_txt = f" | ⏰ <b>{r['late_min']}d</b> kechikdi"

            lines.append(
                f"\n📅 <b>{d_str}</b> ({day}) ✅\n"
                f"   🕐 {ci} → {co}  |  ⌛ {worked}{late_txt}"
            )
        else:
            lines.append(f"\n📅 <b>{d_str}</b> ({day}) ❌ Kelmagan")

    # Telegram xabar limiti: 4096 belgi. Uzun bo'lsa bo'laklarga ajrat.
    full_text = "\n".join(lines)
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Hisobotlar", callback_data="my_reports")]
    ])

    if len(full_text) <= 4000:
        await callback.message.edit_text(full_text, parse_mode="HTML", reply_markup=back_kb)
    else:
        # Uzun bo'lsa — qismlarga bo'lib yuboramiz
        await callback.message.edit_text(
            f"📋 <b>{month_name} — Kunlik davomat</b>\n"
            f"(Jami {len(rows)} yozuv — bo'linib yuboriladi)",
            parse_mode="HTML"
        )
        chunk, chunk_lines = "", []
        for line in lines[1:]:
            if len(chunk) + len(line) > 3800:
                await callback.message.answer(chunk, parse_mode="HTML")
                chunk = ""
            chunk += line + "\n"
        if chunk:
            await callback.message.answer(chunk, parse_mode="HTML", reply_markup=back_kb)

    await callback.answer()


# ─────────────────────────────────────────────────────────────
# KECHIKKAN KUNLARIM — oy tanlash
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "rep_late_months", StateFilter(None))
async def show_late_months(callback: CallbackQuery):
    months = await get_report_months_for_employee(callback.from_user.id)
    if not months:
        await callback.message.edit_text(
            "📭 Davomat ma'lumotlari topilmadi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Hisobotlar", callback_data="my_reports")]
            ])
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "⏰ <b>Kechikkan kunlarim</b>\n"
        "<i>(15 daqiqagacha kechiriladi)</i>\n\n"
        "Qaysi oyni ko'rmoqchisiz?",
        parse_mode="HTML",
        reply_markup=report_months_keyboard(months, "rep_late")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_late_"), StateFilter(None))
async def show_late_for_month(callback: CallbackQuery):
    _, _, year_s, month_s = callback.data.split("_")
    year, month = int(year_s), int(month_s)
    user_id = callback.from_user.id

    late_days = await get_emp_late_days_month(user_id, year, month)
    month_name = f"{_UZ_MONTHS[month]} {year}"

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Hisobotlar", callback_data="my_reports")]
    ])

    if not late_days:
        await callback.message.edit_text(
            f"✅ <b>{month_name}</b>\n\n"
            "Bu oyda kechikkan kunlar topilmadi.\n"
            "<i>(15 daqiqagacha kechiriladi)</i>",
            parse_mode="HTML",
            reply_markup=back_kb
        )
        await callback.answer()
        return

    total_min = sum(d['late_min'] for d in late_days)
    lines = [
        f"⏰ <b>{month_name} — Kechikkan kunlar</b>\n"
        f"<i>15 daqiqagacha kechiriladi</i>\n{'─'*28}"
    ]

    for d in late_days:
        d_str = d['date'].strftime('%d-%b')
        day   = d['day_uz']
        t     = f"{d['late_h']}s {d['late_m']}d" if d['late_h'] else f"{d['late_m']}d"
        lines.append(f"📅 <b>{d_str}</b> ({day}) — ⏰ {t} kechikdi")

    total_str = f"{total_min // 60}s {total_min % 60}d" if total_min >= 60 else f"{total_min}d"
    lines.append(f"\n{'─'*28}\n📌 Jami: <b>{len(late_days)} kun</b>, <b>{total_str}</b>")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_kb
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# SANA BO'YICHA HISOBOT (FSM)
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "rep_daterange", StateFilter(None))
async def start_date_range(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ReportDateRange.waiting_start)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="rep_cancel")]
    ])
    await callback.message.edit_text(
        "🗓 <b>Sana bo'yicha hisobot</b>\n\n"
        "Boshlanish sanasini kiriting:\n"
        "<code>YYYY-MM-DD</code>  (masalan: <code>2026-03-01</code>)",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await callback.answer()


@router.message(ReportDateRange.waiting_start, F.text)
async def receive_start_date(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        start = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format. Iltimos qayta kiriting:\n"
            "<code>YYYY-MM-DD</code>  (masalan: <code>2026-03-01</code>)",
            parse_mode="HTML"
        )
        return

    await state.update_data(start_date=str(start))
    await state.set_state(ReportDateRange.waiting_end)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="rep_cancel")]
    ])
    await message.answer(
        f"✅ Boshlanish: <b>{start}</b>\n\n"
        "Tugash sanasini kiriting:\n"
        "<code>YYYY-MM-DD</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )


@router.message(ReportDateRange.waiting_end, F.text)
async def receive_end_date(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        end = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format. Iltimos qayta kiriting:\n"
            "<code>YYYY-MM-DD</code>",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    start = datetime.strptime(data['start_date'], "%Y-%m-%d").date()

    if end < start:
        await message.answer(
            "❌ Tugash sanasi boshlanish sanasidan oldin bo'lmasligi kerak.\n"
            "Tugash sanasini qayta kiriting:"
        )
        return

    await state.clear()

    stats = await get_emp_stats_period(message.from_user.id, start, end)

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Hisobotlar", callback_data="my_reports")]
    ])

    if not stats:
        await message.answer("❌ Ma'lumot topilmadi.", reply_markup=back_kb)
        return

    s = stats
    text = (
        f"🗓 <b>Sana bo'yicha hisobot</b>\n"
        f"<i>{start} – {end}</i>\n"
        f"{'─' * 28}\n"
        f"📋 Kerakli: <b>{s['required_h']}s</b>  |  Ishlagan: <b>{s['worked_h']}s</b>\n"
        f"{_progress_bar(s['progress'])}\n"
        f"⏰ Kechikish: <b>{_fmt_time(s['late_total'])}</b>\n"
        f"✅ Ortiqcha: <b>{_fmt_time(s['overtime_total'])}</b>"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=back_kb)


@router.callback_query(F.data == "rep_cancel")
async def cancel_date_range(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Bekor qilindi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Hisobotlar", callback_data="my_reports")]
        ])
    )
    await callback.answer()


# back_to_main callback stats.py da qayta ishlanadi — bu yerda ikkilanishdan saqlanish uchun yo'q.


# ─────────────────────────────────────────────────────────────
# TINGLOVCHI HISOBOTI — oy tanlanganda
# ─────────────────────────────────────────────────────────────

_PARA_STATUS_ICON = {'present': '✅', 'late': '🟡', 'absent': '❌'}

@router.callback_query(F.data.startswith("srep_"), StateFilter(None))
async def show_student_month_report(callback: CallbackQuery):
    _, year_s, month_s = callback.data.split("_")
    year, month = int(year_s), int(month_s)
    user_id = callback.from_user.id

    from utils.db_api.database import get_student_monthly_report
    report = await get_student_monthly_report(user_id, year, month)

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Hisobotlar", callback_data="my_reports")]
    ])

    if not report or not report['rows']:
        await callback.message.edit_text(
            "📭 Bu oy uchun dars ma'lumotlari topilmadi.",
            reply_markup=back_kb
        )
        await callback.answer()
        return

    month_name = f"{_UZ_MONTHS[month]} {year}"
    lines = [
        f"📊 <b>{month_name} — Davomat hisoboti</b>\n{'─'*28}"
    ]

    for row in report['rows']:
        d_str = row['date'].strftime('%d-%b')
        ci = row['check_in'].strftime('%H:%M') if row['check_in'] else '—'
        lines.append(f"\n📅 <b>{d_str}</b> ({row['day_uz']})  ⏰ {ci}")

        if row['paras']:
            for p in row['paras']:
                icon = _PARA_STATUS_ICON.get(p['status'], '—')
                if p['status'] == 'late':
                    lines.append(f"   {icon} {p['num']}-para: kechikdi ({p['late_min']} daqiqa)")
                elif p['status'] == 'absent':
                    lines.append(f"   {icon} {p['num']}-para: qatnashmadi")
                else:
                    lines.append(f"   {icon} {p['num']}-para: o'z vaqtida")
        else:
            lines.append("   — Smena ma'lumoti yo'q")

    lines.append(
        f"\n{'─'*28}\n"
        f"📌 Jami paralar: <b>{report['total_paras']}</b>\n"
        f"🟡 Kechikkan: <b>{report['late_paras']}</b> para\n"
        f"❌ Qatnashmagan: <b>{report['absent_paras']}</b> para"
    )

    full_text = "\n".join(lines)

    if len(full_text) <= 4000:
        await callback.message.edit_text(full_text, parse_mode="HTML", reply_markup=back_kb)
    else:
        await callback.message.edit_text(
            f"📊 <b>{month_name}</b> hisoboti (bo'linib yuboriladi)",
            parse_mode="HTML"
        )
        chunk = ""
        for line in lines[1:]:
            if len(chunk) + len(line) > 3800:
                await callback.message.answer(chunk, parse_mode="HTML")
                chunk = ""
            chunk += line + "\n"
        if chunk:
            await callback.message.answer(chunk, parse_mode="HTML", reply_markup=back_kb)

    await callback.answer()
