# import os
# import django
# from aiogram import Bot, Dispatcher
# import logging


# async def on_startup(dp):
#     from utils.set_bot_commands import set_default_commands
#     import filters
#     import middlewares
#     filters.setup(dp)
#     middlewares.setup(dp)
#     await set_default_commands(dp)


# async def on_shutdown(dp):
#     await dp.storage.close()
#     await dp.storage.wait_closed()


# def setup_django():
#     os.environ.setdefault(
#         "DJANGO_SETTINGS_MODULE",
#         "admin.settings"
#     )
#     os.environ.update({'DJANGO_ALLOW_ASYNC_UNSAFE': "true"})
#     django.setup()


# if __name__ == '__main__':
#     setup_django()

#     from aiogram.utils import executor
#     from handlers import dp

#     executor.start_polling(dp, on_startup=on_startup, skip_updates=True)

import os
import django
from aiogram import Bot, Dispatcher, enums
import logging
from data import config
import asyncio


async def on_startup(bot: Bot, dp: Dispatcher):
    from utils.set_bot_commands import set_default_commands
    import filters

    filters.setup(dp)

    # Qo'shimcha ishlar (masalan, bazani sozlash yoki xabar jo'natish)
    logging.info("Bot ishga tushdi.")


async def on_shutdown(bot: Bot, dp: Dispatcher):
    await bot.session.close()
    logging.info("Bot o'chirildi.")


def setup_django():
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "core.settings"
    )
    os.environ.update({'DJANGO_ALLOW_ASYNC_UNSAFE': "true"})
    django.setup()



async def main():
    setup_django()

    # Bot va Dispatcher obyektlarini yaratish
    bot = Bot(token=config.BOT_TOKEN)

    from handlers import dp


    # Botni ishga tushirish
    await on_startup(bot, dp)
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown(bot, dp)

if __name__ == '__main__':
    asyncio.run(main())

