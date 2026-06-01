# from aiogram import Bot, Dispatcher, types
# from data import config
# from aiogram.fsm.storage.memory import MemoryStorage


# bot = Bot(token=config.BOT_TOKEN, parse_mode=types.ParseMode.HTML)
# storage = MemoryStorage()
# dp = Dispatcher(bot, storage=storage)

from aiogram import Bot, Dispatcher, types, enums
from data import config
from aiogram.fsm.storage.memory import MemoryStorage
# from send_keyboard import customer

bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

