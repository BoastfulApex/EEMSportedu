from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from utils.db_api.database import get_all_addresses

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from data.config import URL

async def start_webapp_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🖥 Saytga kirish",
                    web_app=WebAppInfo(url=URL)
                )
            ]
        ],
        resize_keyboard=True
    )
    return keyboard


async def admin_menu_keyboard():
    admin_menu_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧑‍💼 Xodim qo'shish")],
            [KeyboardButton(text="📊 Hisobotlar")],
            [KeyboardButton(text="📍 Manzillar")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return admin_menu_keyboard


cancel = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔙 Bekor qilish")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


async def addresses_keyboard(addresses):
    keyboard = [[KeyboardButton(text=address)] for address in addresses]

    # Qo‘shimcha tugmalar (eng pastki qatorda 2 ta)
    keyboard.append([
        KeyboardButton(text="✏️ Manzilni yangilash"),
        KeyboardButton(text="🔙 Bekor qilish")
    ])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def address_bottom_keyboard():
    keyboard = [
        [KeyboardButton(text="✏️ Manzilni yangilash")],
        [KeyboardButton(text="🔙 Bekor qilish")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def empty_address_keyboard():
    keyboard = [
        [KeyboardButton(text="➕ Manzil qo‘shish")],
        [KeyboardButton(text="🔙 Bekor qilish")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
