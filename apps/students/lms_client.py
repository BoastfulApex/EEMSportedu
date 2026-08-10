"""
LMS (SportEdu Jadval) bilan HTTP aloqa.

Bu yerda FAQAT tashqi so'rov mantiqi joylashadi — view'lar bevosita `requests`
chaqirmasin. Sabab: timeout/xato formatlash bir joyda bo'lsa, keyinchalik
o'zgartirish oson va view'lar sodda qoladi.

LMS xato shartnomasi: HAMMA rad etish 403 bilan keladi, sabab javob tanasidagi
`code` da (`invalid_key` / `inactive_client` / `scope_denied`). `detail` matni
o'zbekcha va o'zgarishi mumkin — unga tayanmaymiz, faqat `code` ga.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# LMS `code` → foydalanuvchiga ko'rsatiladigan tushunarli sabab
_CODE_MESSAGES = {
    'invalid_key':     "LMS kaliti qabul qilinmadi. .env dagi LMS_API_KEY ni tekshiring.",
    'inactive_client': "LMS kaliti o'chirilgan. LMS administratoriga murojaat qiling.",
    'scope_denied':    "LMS kalitida bu ma'lumotni o'qish ruxsati yo'q ({scope}).",
    'invalid_params':  "So'rov parametrlari noto'g'ri (yil/oy).",
}


class LMSError(Exception):
    """LMS bilan aloqada xato — foydalanuvchiga ko'rsatiladigan xabar bilan."""


def _headers():
    key = getattr(settings, 'LMS_API_KEY', '') or ''
    if not key:
        raise LMSError("LMS_API_KEY sozlanmagan (.env faylini tekshiring).")
    return {'Authorization': f'Api-Key {key}'}


def _base_url():
    base = (getattr(settings, 'LMS_BASE_URL', '') or '').rstrip('/')
    if not base:
        raise LMSError("LMS_BASE_URL sozlanmagan (.env faylini tekshiring).")
    return base


def _get(path, params, scope_hint=''):
    """LMS ga GET yuboradi va xatolarni tushunarli LMSError ga aylantiradi."""
    url = f"{_base_url()}{path}"
    try:
        r = requests.get(
            url, params=params, headers=_headers(),
            timeout=getattr(settings, 'LMS_TIMEOUT', 15),
        )
    except requests.Timeout:
        raise LMSError("LMS javob bermadi (vaqt tugadi). Keyinroq urinib ko'ring.")
    except requests.ConnectionError:
        raise LMSError("LMS serveriga ulanib bo'lmadi. Tarmoqni tekshiring.")
    except requests.RequestException as e:
        logger.exception("LMS bilan aloqa xatosi")
        raise LMSError(f"LMS bilan aloqa o'rnatilmadi: {e}")

    if r.status_code != 200:
        # Xato tanasidan `code` ni ajratib olishga harakat qilamiz
        code = detail = None
        try:
            body = r.json()
            code   = body.get('code')
            detail = body.get('detail') or body.get('error')
        except ValueError:
            pass

        if code in _CODE_MESSAGES:
            raise LMSError(_CODE_MESSAGES[code].format(scope=scope_hint))
        if r.status_code == 405:
            raise LMSError("LMS bu endpointda GET so'rovini qabul qilmadi (405).")
        if detail:
            raise LMSError(f"LMS xatosi ({r.status_code}): {detail}")
        raise LMSError(f"LMS kutilmagan javob qaytardi: {r.status_code}")

    try:
        return r.json()
    except ValueError:
        raise LMSError("LMS javobini o'qib bo'lmadi (JSON emas).")


def fetch_groups(year: int, month: int) -> list[dict]:
    """
    LMS'dan shu oy uchun guruhlar ro'yxatini oladi.

    Onlayn guruhlar LMS tomonida allaqachon chiqarib tashlangan — bu yerda
    qayta filtrlanmaydi (bir xil mantiq ikki joyda bo'lmasligi uchun).
    """
    data = _get(
        '/api/v1/integration/groups/',
        {'year': year, 'month': month},
        scope_hint='groups:read',
    )
    if isinstance(data, list):
        return data
    return data.get('results', [])


def fetch_buildings() -> list[dict]:
    """
    LMS'dagi BARCHA faol binolarni oladi — oy/yilga bog'liq emas.

    Bino <-> Location moslashtirish bir martalik, kalendar oyidan mustaqil ish
    (INTEGRATION_LMS.md, 5-B bo'lim) — shuning uchun `fetch_day_assignments`
    dagi kabi "shu oy ishlatilganlari" emas, to'liq ro'yxat kerak.
    """
    data = _get(
        '/api/v1/integration/buildings/',
        {},
        scope_hint='schedule:read',
    )
    if isinstance(data, list):
        return data
    return data.get('results', [])


def fetch_day_assignments(year: int, month: int) -> dict:
    """
    LMS'dan shu oy uchun kunlik biriktiruvlarni oladi.

    Qaytadi: {'shifts': [...], 'buildings': [...], 'assignments': [...]}
    `shifts`/`buildings` — faqat o'sha oy haqiqatan ishlatilganlari.
    """
    data = _get(
        '/api/v1/integration/day-assignments/',
        {'year': year, 'month': month},
        scope_hint='schedule:read',
    )
    return {
        'shifts':      data.get('shifts', []),
        'buildings':   data.get('buildings', []),
        'assignments': data.get('assignments', []),
    }
