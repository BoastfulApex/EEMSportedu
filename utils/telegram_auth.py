"""
Telegram WebApp `initData` imzosini tekshirish.

Nega kerak: WebApp'dagi `tg.initDataUnsafe` — nomidan ko'rinib turibdiki,
TEKSHIRILMAGAN ma'lumot. Mijoz uni o'zgartirib, boshqa foydalanuvchi
nomidan so'rov yuborishi mumkin. `initData` esa Telegram tomonidan bot
tokeni bilan imzolangan — imzoni faqat tokenni biladigan server tekshira
oladi, mijoz uni qalbakilashtira olmaydi.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from django.conf import settings


class InitDataError(Exception):
    pass


def verify_init_data(init_data: str, max_age_seconds: int = 3600) -> dict:
    """
    `initData` ni tekshiradi va ichidagi ma'lumotni qaytaradi.
    Xato bo'lsa `InitDataError` ko'taradi.

    Qaytadi: {'user': {...}, 'auth_date': '...', ...}
    """
    token = getattr(settings, 'BOT_TOKEN', '') or ''
    if not token:
        # Sozlanmagan bo'lsa — YOPIQ. Hech qachon "o'tkazib yuborish" qilmang.
        raise InitDataError("BOT_TOKEN sozlanmagan")
    if not init_data:
        raise InitDataError("initData yuborilmagan")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop('hash', None)
    if not received_hash:
        raise InitDataError("initData da hash yo'q")

    check_string = '\n'.join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("initData imzosi mos kelmadi")

    # Eskirgan initData — takroriy (replay) hujumning oldini oladi
    try:
        auth_date = int(pairs.get('auth_date', 0))
    except (TypeError, ValueError):
        raise InitDataError("auth_date noto'g'ri")
    if max_age_seconds and (time.time() - auth_date) > max_age_seconds:
        raise InitDataError("initData eskirgan, WebApp'ni qayta oching")

    user_raw = pairs.get('user')
    try:
        pairs['user'] = json.loads(user_raw) if user_raw else None
    except ValueError:
        raise InitDataError("initData dagi user ma'lumoti buzilgan")
    return pairs


def get_telegram_user_id(init_data: str) -> int:
    """Tekshirilgan initData dan `user.id` ni qaytaradi."""
    data = verify_init_data(init_data)
    user = data.get('user') or {}
    uid = user.get('id')
    if not uid:
        raise InitDataError("initData da foydalanuvchi ma'lumoti yo'q")
    return int(uid)
