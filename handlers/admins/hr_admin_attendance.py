"""
HR Admin — Xodim davomati qayd qilish.

Flow:
  1. "👤 Xodim davomati" → filialdagi xodimlar ro'yxati
  2. Xodim tanlandi → ism + WebApp kirish/chiqish tugmalari
"""
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
)

from loader import dp
from data.config import BASE_URL
from utils.db_api.database import get_employees_for_hr_admin

router = Router()
dp.include_router(router)

logger = logging.getLogger(__name__)

_HR_WEB_APP_URL = BASE_URL.rstrip('/') + '/web_app/hr-admin/web-app/'

_BACK_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Xodimlar", callback_data="hr_attend_list")]
])


@router.message(F.text == "👤 Xodim davomati", StateFilter(None))
async def hr_show_employees(message: Message):
    await _send_employee_list(message.from_user.id, message.answer)


@router.callback_query(F.data == "hr_attend_list")
async def hr_attend_list_cb(callback: CallbackQuery):
    await _send_employee_list(callback.from_user.id, callback.message.edit_text)
    await callback.answer()


async def _send_employee_list(admin_id: int, send_fn):
    employees = await get_employees_for_hr_admin(admin_id)

    if not employees:
        await send_fn(
            "📭 <b>Filialda xodimlar topilmadi.</b>",
            parse_mode="HTML",
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"👤 {e['name']}",
            callback_data=f"hr_attend_emp:{e['telegram_user_id']}"
        )]
        for e in employees
    ]

    await send_fn(
        f"👥 <b>Xodimni tanlang</b>\n\nJami: {len(employees)} ta xodim",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("hr_attend_emp:"))
async def hr_attend_employee(callback: CallbackQuery):
    telegram_user_id = int(callback.data.split(":")[1])

    from utils.db_api.database import get_employee_by_telegram_id
    emp = await get_employee_by_telegram_id(telegram_user_id)
    if not emp:
        await callback.message.edit_text("❌ Xodim topilmadi.")
        await callback.answer()
        return

    url_in  = f"{_HR_WEB_APP_URL}?employee_telegram_id={telegram_user_id}&action=check_in"
    url_out = f"{_HR_WEB_APP_URL}?employee_telegram_id={telegram_user_id}&action=check_out"

    await callback.message.edit_text(
        f"👤 <b>{emp['name']}</b>\n\nDavomat qayd qiling:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔓 Kirish",  web_app=WebAppInfo(url=url_in)),
                InlineKeyboardButton(text="🔒 Chiqish", web_app=WebAppInfo(url=url_out)),
            ],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="hr_attend_list")],
        ]),
    )
    await callback.answer()
