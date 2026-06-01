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
    import filters

    filters.setup(dp)
    logging.info("Bot ishga tushdi.")

    # Broadcast background task sifatida — polling ni bloklamaydi
    asyncio.create_task(_broadcast_restart(bot))


async def _broadcast_restart(bot: Bot):
    """
    Bot ishga tushganda barcha ro'yxatdan o'tgan foydalanuvchilarga
    qayta /start bosishni so'rash xabari yuboradi.
    Telegram flood limit: sekundiga 30 ta xabar → har xabardan keyin kichik tanaffus.
    """
    from utils.db_api.database import get_all_telegram_user_ids
    from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

    user_ids = await get_all_telegram_user_ids()
    logging.info(f"Broadcast boshlandi: {len(user_ids)} ta foydalanuvchi")

    sent = 0
    failed = 0

    for uid in user_ids:
        try:
            await bot.send_message(
                chat_id=uid,
                text=(
                    "🔄 <b>Bot yangilandi!</b>\n\n"
                    "Yangi menyu va funksiyalar faollashtirish uchun\n"
                    "👇 <b>/start</b> tugmasini bosing."
                ),
                parse_mode="HTML",
            )
            sent += 1
            await asyncio.sleep(0.05)   # 20 msg/sek — flood limitdan past
        except TelegramForbiddenError:
            # User botni bloklagan — o'tkazib yuboramiz
            failed += 1
        except TelegramBadRequest:
            failed += 1
        except Exception as e:
            logging.warning(f"Broadcast xato (uid={uid}): {e}")
            failed += 1

    logging.info(f"Broadcast tugadi: {sent} yuborildi, {failed} xato.")


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

