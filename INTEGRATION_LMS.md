# LMS (SportEdu Jadval) ↔ KPI (EEMSportedu) integratsiyasi — KPI tomoni uchun topshiriq

> Bu hujjat **KPI loyihasida ishlaydigan agent** uchun. Unda ish nima uchun kerakligi,
> nima qilinishi va qanday tekshirilishi to'liq yozilgan. LMS tomoni alohida agent
> tomonidan qilinadi — bu yerda faqat **KPI nima qilishi** va **LMS bilan kelishilgan
> shartnoma (API contract)** bayon etilgan.

---

## 1. KONTEKST — ikkita loyiha nima qiladi

### LMS — "SportEdu Jadval"
- Repo: `Intelligent-SaaS-Education-ERP-Scheduling-System` (Django 6 + DRF, React frontend)
- Vazifasi: **o'quv jarayonini rejalashtirish** — o'quv reja, taqsimot, o'qituvchi
  biriktirish va OR-Tools CP-SAT solver bilan **dars jadvali generatsiyasi**.
- Unda bor: `Group` (guruh), `Subject` (fan), `Teacher`, `Para` (dars vaqti),
  `ScheduleEntry` (bitta aniq dars: sana + para + guruh + fan + o'qituvchi),
  `LessonJournal` (o'qituvchi to'ldiradigan dars jurnali — o'tilgan mavzu).
- Rollari: `super_admin` > `org_admin` > `edu_admin` / `dept_manager` > `teacher`.

### KPI — "EEMSportedu" (bu loyiha)
- Vazifasi: **tinglovchilar va xodimlarning face-ID + GPS orqali davomati**.
- Telegram bot orqali tinglovchi yuz rasmi va GPS koordinatasini yuboradi
  (`apps/students/api_views.py::StudentCheckAPIView`), tizim yuzni tekshiradi va
  lokatsiyadan **150 metr** ichida ekanini tasdiqlaydi → `StudentAttendance` yoziladi.
- Unda bor: `Student` (`face_encoding`, `face_verified`, `telegram_id`),
  `Group` (`students` M2M, `year`/`month`, `invite_token`),
  `StudentAttendance` (**kunlik** — `unique_together = (student, group, date)`).

### Muammо va integratsiyaning maqsadi

Hozir bu ikki tizim **bir-birini bilmaydi**:
- LMS'da o'qituvchi jurnalda "dars o'tdim, mavzu bu edi" deb yozadi, lekin
  **kim darsda bor edi** — bilmaydi.
- KPI'da tinglovchi hududga kelib face-ID'dan o'tdi degan aniq ma'lumot bor,
  lekin u **qaysi darsga** tegishli ekani bog'lanmagan.

Integratsiyadan keyin:
1. O'qituvchi LMS jurnalida yo'qlama qiladi.
2. Yo'qlamada **faqat bugun hududga kelib face-ID'dan o'tgan** tinglovchilarni
   "darsda bor" deb belgilay oladi. Kelmagan odamni "bor" deb yozib bo'lmaydi —
   soxta yo'qlamaning oldi olinadi.
3. Dars "o'tildi" deb hisoblanishi yo'qlamaga ham bog'liq bo'ladi.

### Kim nimaning "haqiqat manbai" (source of truth)

| Ma'lumot | Egasi | Ikkinchi tomon nima qiladi |
|---|---|---|
| Guruhlar, jadval, para, fan, o'qituvchi | **LMS** | KPI **import qiladi** (nusxa oladi) |
| Tinglovchilar, face-ID check-in | **KPI** | LMS **o'qiydi** (snapshot oladi) |

**Qat'iy qoida**: hech bir tizim ikkinchisining bazasiga to'g'ridan-to'g'ri
ulanmaydi (bitta `DATABASES` sozlamasida ikkinchi baza bo'lmaydi). Faqat HTTP API.

**Nega**: ikki loyiha alohida serverlarda, alohida deploy siklida, alohida
migratsiya tarixi bilan yashaydi. To'g'ridan-to'g'ri DB ulanishi (a) bir tomon
migratsiya qilganda ikkinchisini jimgina sindiradi, (b) DB parolini ikkinchi
loyihaga berish — xavfsizlik jihatidan qabul qilib bo'lmas, (c) ORM modellari
nusxalanib, ikki joyda ikki xil haqiqat paydo bo'ladi.

---

## 2. ⚠️ BIRINCHI VA ENG MUHIM VAZIFA — mavjud API'larni yopish

**Buni integratsiyadan OLDIN qiling.** Boshqa hech narsa bundan oldin qilinmasin.

`apps/students/api_views.py` da uchta view topilgan:

```python
class StudentCheckAPIView(generics.ListCreateAPIView):
    authentication_classes = []   # CSRF tekshiruvi o'chiriladi
    permission_classes     = [AllowAny]

class EduAdminStudentsAPIView(generics.GenericAPIView):
    permission_classes     = [AllowAny]

class EduAdminCheckAPIView(generics.CreateAPIView):
    permission_classes     = [AllowAny]
```

### Bu endpointlarni KIM chaqiradi — avval shuni aniqlang

Tekshirildi: bu API'larni **bot Python kodi CHAQIRMAYDI**. Ular Telegram
WebApp ichidagi JavaScript'dan, ya'ni **foydalanuvchining o'z qurilmasidan**
chaqiriladi:

| Fayl | Qator | Chaqiruv |
|---|---|---|
| `apps/templates/students/web_app_page.html` | 489 | `fetch("/students/api/check/")` |
| `apps/templates/students/edu_admin_web_app.html` | 453 | `fetch("/students/edu-admin/api/check/")` |
| `apps/templates/main/web_app_page.html` | 395 | `fetch("/web_app/api/check/")` |
| `apps/templates/main/hr_admin_web_app.html` | 453 | `fetch("/web_app/hr-admin/api/check/")` |

**Shuning uchun `X-Bot-Secret` kabi "umumiy maxfiy kalit" bu yerda ISHLAMAYDI** —
JavaScript kodidagi kalitni istalgan foydalanuvchi brauzer devtools orqali
o'qiy oladi. U himoya emas, himoya illyuziyasi.

**Botga hech qanday o'zgartirish kerak emas** — u bu API'larga umuman
murojaat qilmaydi.

### Haqiqiy muammo — `initDataUnsafe`

`apps/templates/students/web_app_page.html:183`:
```js
const user_id = tg.initDataUnsafe?.user?.id || null;
```

so'ng shu `user_id` so'rov tanasida yuboriladi va server unga to'liq ishonadi:
```python
student = Student.objects.get(telegram_id=user_id)
```

`initDataUnsafe` — Telegram hujjatida ataylab shunday nomlangan: bu
**imzosi tekshirilmagan** ma'lumot. Mijoz uni bemalol o'zgartirishi mumkin.

Hozirgi holatda mumkin bo'lgan hujumlar:
- Boshqa tinglovchining `user_id` sini yozib, **uning nomidan** davomat qo'yish
- GPS koordinatani qalbakilashtirib, istalgan joydan "keldim" deb yozdirish
- Yuz rasmini umuman yubormaslik (`image` — `required=False, default=''`)
- `EduAdminStudentsAPIView` orqali tinglovchilar ro'yxatini (F.I.Sh, telefon)
  hech qanday autentifikatsiyasiz o'qib olish

Butun integratsiyaning ma'nosi — "faqat haqiqatan kelganlar darsda bor deb
belgilanadi". Bu teshik ochiq qolsa, LMS **ishonchsiz manbadan** ma'lumot olib
kelgan bo'ladi va mexanizm ma'nosini yo'qotadi.

### Nima qilish kerak — Telegram initData imzosini tekshirish

Telegram WebApp ochilganda `initData` satrini **bot tokeni bilan HMAC-SHA256
imzolaydi**. Server o'sha imzoni qayta hisoblab tekshiradi va `user.id` ni
**imzolangan ma'lumotdan** oladi — mijoz yuborgan `body` dan emas.

Bu Telegram'ning rasmiy va yagona to'g'ri usuli:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

**2.1.** `core/settings.py` ga (loyihada `python-dotenv` + `os.getenv` naqshi
ishlatiladi, `django-environ` **yo'q** — mavjud naqshni takrorlang):
```python
BOT_TOKEN = os.getenv('BOT_TOKEN', '')   # allaqachon bor bo'lishi mumkin —
                                          # `data/config.py` ni tekshiring
```

**2.2.** Yangi fayl `apps/students/telegram_auth.py`:

```python
"""
Telegram WebApp `initData` imzosini tekshirish.

Nega kerak: WebApp'dagi `tg.initDataUnsafe` — nomidan ko'rinib turibdiki,
TEKSHIRILMAGAN ma'lumot. Mijoz uni o'zgartirib, boshqa foydalanuvchi
nomidan so'rov yuborishi mumkin. `initData` esa Telegram tomonidan bot
tokeni bilan imzolangan — imzoni faqat tokenni biladigan server tekshira
oladi, mijoz uni qalbakilashtira olmaydi.
"""
import hashlib
import hmac
import time
from urllib.parse import parse_qsl

from django.conf import settings


class InitDataError(Exception):
    pass


def verify_init_data(init_data: str, max_age_seconds: int = 3600) -> dict:
    """
    `initData` ni tekshiradi va ichidagi ma'lumotni qaytaradi.
    Xato bo'lsa `InitDataError` ko'taradi.

    Qaytadi: {'user': {...}, 'auth_date': int, ...}
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

    # Telegram algoritmi: kalitlarni alifbo bo'yicha tartiblab, \n bilan birlashtirish
    check_string = '\n'.join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("initData imzosi mos kelmadi")

    # Eskirgan initData — takroriy hujumning (replay) oldini oladi
    try:
        auth_date = int(pairs.get('auth_date', 0))
    except ValueError:
        raise InitDataError("auth_date noto'g'ri")
    if max_age_seconds and (time.time() - auth_date) > max_age_seconds:
        raise InitDataError("initData eskirgan, WebApp'ni qayta oching")

    import json
    user_raw = pairs.get('user')
    pairs['user'] = json.loads(user_raw) if user_raw else None
    return pairs


def get_telegram_user_id(init_data: str) -> int:
    """Tekshirilgan initData dan `user.id` ni qaytaradi."""
    data = verify_init_data(init_data)
    user = data.get('user') or {}
    uid = user.get('id')
    if not uid:
        raise InitDataError("initData da foydalanuvchi ma'lumoti yo'q")
    return int(uid)
```

**2.3.** View'larda `user_id` ni **body'dan emas, initData'dan** oling:

```python
# serializer'ga qo'shing
init_data = serializers.CharField()      # majburiy

# view.create() boshida — `user_id` ni body'dan O'QIMANG
try:
    user_id = get_telegram_user_id(data['init_data'])
except InitDataError as e:
    return Response({"status": "FAIL", "reason": str(e)}, status=401)
```

> Eski `user_id` maydonini serializer'dan **butunlay olib tashlang**. Agar u
> qolsa, kimdir keyinchalik yana o'shanga tayanib qolishi mumkin — ikkita
> "haqiqat manbai" xavfli.

**2.4.** WebApp shablonlarida (4 ta fayl, yuqoridagi jadval) `fetch` tanasiga
`init_data` qo'shing — bu **yagona** frontend o'zgarishi:

```js
body: JSON.stringify({
  init_data: tg.initData,          // ← QO'SHILADI (imzolangan satr)
  type: actionType, latitude, longitude, image: photo
  // user_id — OLIB TASHLANADI, server uni initData'dan oladi
})
```

**2.5.** `EduAdminStudentsAPIView` (`GET`, `?admin_id=` bilan) — u ham xuddi
shu usulda himoyalansin: `admin_id` query-param'ga ishonmang, `init_data`
orqali tekshiring. Qo'shimcha ravishda o'sha Telegram foydalanuvchi haqiqatan
`Administrator` (`is_edu_admin`) ekanini tekshiring.

**2.6.** Throttling (`core/settings.py`):
```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.ScopedRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {
        'webapp': '120/min',
        'integration': '60/min',
    },
}
```
va view'larda `throttle_scope = 'webapp'`.

### Tekshiruv

```bash
# 1. initData'siz — 401 kutiladi
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  http://localhost:8000/students/api/check/ \
  -H "Content-Type: application/json" \
  -d '{"type":"check_in","latitude":41.0,"longitude":69.0}'

# 2. Soxta initData bilan — 401 kutiladi
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  http://localhost:8000/students/api/check/ \
  -H "Content-Type: application/json" \
  -d '{"init_data":"user=%7B%22id%22%3A123%7D&hash=aaaa","type":"check_in","latitude":41.0,"longitude":69.0}'
```

Haqiqiy initData bilan tekshirish faqat Telegram orqali WebApp ochilganda
mumkin — bu **qo'lda, telefonda** sinaladi. Shuning uchun `verify_init_data`
uchun alohida unit-test yozing: bot tokeni bilan qo'lda to'g'ri imzo hosil
qilib, funksiya uni qabul qilishini va bitta belgi o'zgartirilganda rad
etishini tasdiqlang.

> **Deploy eslatmasi**: bu o'zgarish server va WebApp shablonlarini **birga**
> yangilashni talab qiladi. Server yangilanib, shablon eski qolsa —
> tinglovchilar face-ID qila olmay qoladi (401). Ikkalasi bitta deploy'da
> chiqsin.

---

## 3. `IntegrationClient` — mashina-mashina autentifikatsiya

### Nima uchun foydalanuvchi login/paroli yoki JWT emas

- LMS'ning KPI'ga kirishi — bu **odam emas, server**. Unga foydalanuvchi hisobi
  ochish noto'g'ri: u rol tizimiga aralashib ketadi, parol muddati/almashtirish
  oqimi mos kelmaydi, va audit loglarida "kim qildi" degan savol chalkashadi.
- JWT muddatli — server-to-server chaqiruvda uni yangilab turish ortiqcha
  murakkablik va yana bir nosozlik nuqtasi.
- Alohida kalit **scope** (nimaga ruxsat) va **IP cheklovi** bilan beriladi va
  kerak bo'lsa bir tugmada bekor qilinadi — foydalanuvchi hisobiga tegmasdan.

### Model — `apps/superadmin/models.py` ga qo'shing

```python
import hashlib
import secrets

class IntegrationClient(models.Model):
    """
    Tashqi tizim (LMS) bilan server-to-server aloqa uchun API kalit.

    Kalit formati:  <prefix>.<secret>     masalan  "a1b2c3d4.xYz...48belgi"
      - prefix — bazada OCHIQ saqlanadi, kalitni TOPISH uchun (indekslangan)
      - secret — bazada FAQAT SHA-256 hash ko'rinishida saqlanadi

    Nega to'liq kalit saqlanmaydi: agar baza dumpi sizib chiqsa (backup,
    xatolik logi, o'g'irlangan dump), hujumchi kalitlarni o'qiy olmasligi kerak.
    Hash'dan asl kalitni tiklab bo'lmaydi.
    """
    SCOPE_CHOICES = [
        ('attendance:read', 'Davomatni o\'qish'),
        ('students:read',   'Tinglovchilarni o\'qish'),
    ]

    name        = models.CharField(max_length=100, verbose_name="Nomi")
    key_prefix  = models.CharField(max_length=12, unique=True, db_index=True)
    key_hash    = models.CharField(max_length=64)
    scopes      = models.JSONField(default=list, blank=True)
    allowed_ips = models.JSONField(
        default=list, blank=True,
        help_text="Bo'sh bo'lsa — IP cheklovi yo'q. Masalan: [\"195.158.30.179\"]"
    )
    is_active   = models.BooleanField(default=True)
    last_used   = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Integratsiya kaliti"
        verbose_name_plural = "Integratsiya kalitlari"

    def __str__(self):
        return f"{self.name} ({self.key_prefix}…)"

    @classmethod
    def generate(cls, name, scopes, allowed_ips=None):
        """
        Yangi kalit yaratadi va (obyekt, TO'LIQ_KALIT) qaytaradi.
        TO'LIQ KALIT FAQAT SHU YERDA, BIR MARTA ko'rinadi — keyin hech qachon.
        """
        prefix = secrets.token_hex(4)          # 8 belgi
        raw    = secrets.token_urlsafe(36)
        obj = cls.objects.create(
            name=name,
            key_prefix=prefix,
            key_hash=hashlib.sha256(raw.encode()).hexdigest(),
            scopes=scopes,
            allowed_ips=allowed_ips or [],
        )
        return obj, f"{prefix}.{raw}"
```

Migratsiya: `python manage.py makemigrations superadmin && python manage.py migrate`

### Permission klass — `apps/students/permissions.py` ga qo'shing

```python
import hashlib
import secrets
from django.utils import timezone
from rest_framework.permissions import BasePermission


class HasIntegrationScope(BasePermission):
    """
    `Authorization: Api-Key <prefix>.<secret>` sarlavhasini tekshiradi.

    View'da kerakli scope shunday belgilanadi:
        required_scope = 'attendance:read'
    """
    message = "Integratsiya kaliti yaroqsiz."

    def has_permission(self, request, view):
        from apps.superadmin.models import IntegrationClient

        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Api-Key '):
            return False
        token = auth[len('Api-Key '):].strip()
        if '.' not in token:
            return False
        prefix, raw = token.split('.', 1)

        try:
            client = IntegrationClient.objects.get(key_prefix=prefix, is_active=True)
        except IntegrationClient.DoesNotExist:
            return False

        expected = client.key_hash
        actual   = hashlib.sha256(raw.encode()).hexdigest()
        if not secrets.compare_digest(expected, actual):
            return False

        # IP cheklovi (ro'yxat bo'sh bo'lsa — tekshirilmaydi)
        if client.allowed_ips:
            ip = self._client_ip(request)
            if ip not in client.allowed_ips:
                return False

        # Scope
        required = getattr(view, 'required_scope', None)
        if required and required not in (client.scopes or []):
            return False

        client.last_used = timezone.now()
        client.save(update_fields=['last_used'])
        request.integration_client = client
        return True

    @staticmethod
    def _client_ip(request):
        # Nginx orqasida ishlaydi — X-Forwarded-For ning BIRINCHI qiymati
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
```

> **Diqqat**: `X-Forwarded-For` faqat ishonchli proksi (nginx) orqasida
> ma'noga ega. Nginx konfiguratsiyasida `proxy_set_header X-Forwarded-For
> $proxy_add_x_forwarded_for;` borligiga ishonch hosil qiling. Nginx'siz
> to'g'ridan-to'g'ri ochiq bo'lsa, bu sarlavhani mijoz o'zi qalbakilashtira
> oladi — u holda `allowed_ips` ni ishlatmang, faqat kalitga tayaning.

### Kalit yaratish uchun management command

`apps/superadmin/management/commands/create_integration_key.py`:
```python
from django.core.management.base import BaseCommand
from apps.superadmin.models import IntegrationClient


class Command(BaseCommand):
    help = "Yangi integratsiya API kaliti yaratadi"

    def add_arguments(self, parser):
        parser.add_argument('name')
        parser.add_argument('--scopes', nargs='+', default=['attendance:read'])
        parser.add_argument('--ips', nargs='*', default=[])

    def handle(self, *args, **o):
        obj, key = IntegrationClient.generate(o['name'], o['scopes'], o['ips'])
        self.stdout.write(self.style.SUCCESS(f"Kalit yaratildi: {obj.name}"))
        self.stdout.write(self.style.WARNING(
            f"\n  {key}\n\n"
            "  ⚠️ BU KALIT BOSHQA HECH QACHON KO'RSATILMAYDI. Hoziroq nusxalang."
        ))
```

Ishlatish:
```bash
python manage.py create_integration_key "LMS (SportEdu Jadval)" \
    --scopes attendance:read --ips 195.158.30.179
```

---

## 4. `Group.lms_group_code` — ikki tizimni bog'lovchi kalit

`apps/students/models.py` → `Group` modeliga:

```python
lms_group_code = models.UUIDField(
    null=True, blank=True, unique=True, db_index=True,
    verbose_name="LMS guruh kodi",
    help_text="LMS (SportEdu Jadval) dagi Group.external_code — import orqali to'ladi"
)
lms_synced_at = models.DateTimeField(null=True, blank=True, verbose_name="Oxirgi import")
```

Migratsiya yarating.

### Nega UUID, LMS'dagi butun son `id` emas

1. **Sanab chiqishning oldini oladi.** Integer bo'lsa, kalitni qo'lga kiritgan
   yoki endpointni topgan kishi `?group=1,2,3…` bilan barcha guruhlarni ketma-ket
   so'rab chiqadi. UUID'ni taxmin qilib bo'lmaydi.
2. **Ichki hajmni oshkor qilmaydi.** `id=1847` — tizimda qancha guruh borligini
   aytib qo'yadi.
3. **Baza qayta tiklansa xato bog'lanish bo'lmaydi.** LMS bazasi dump'dan
   tiklansa yoki test ma'lumoti tozalansa, integer ID'lar siljiydi va KPI
   **jimgina** boshqa guruhga bog'lanib qoladi — bu turdagi xatoni sezish juda
   qiyin. UUID unikal va barqaror.

### `invite_token` bilan chalkashtirmang

`Group.invite_token` — KPI'ning **o'z** tokeni (tinglovchini guruhga taklif qilish
uchun). `lms_group_code` — **LMS'dan kelgan** kod. Ular butunlay boshqa maqsadga
xizmat qiladi, birini ikkinchisining o'rniga ishlatmang.

---

## 5. VAZIFA A — LMS'dan guruhlarni import qilish (KPI = mijoz)

### LMS taqdim etadigan endpoint (shartnoma — LMS agenti buni yozadi)

```
GET  {LMS_BASE_URL}/api/v1/integration/groups/?year=2026&month=9
Headers:
    Authorization: Api-Key <LMS bergan kalit>

200 OK
{
  "count": 19,
  "results": [
    {
      "code": "3f2a9c14-8b7e-4d51-9a02-1c6e5b8d7a33",
      "name": "Sport turlari bo'yicha yo'riqchi-uslubchilar-1",
      "year": 2026,
      "month": 9,
      "major": "Trener",
      "start_date": "2026-09-07",
      "end_date": "2026-09-26",
      "delivery_mode": "offline",
      "student_count": 25
    }
  ]
}
```

Xato javoblari: `401` (kalit yo'q/noto'g'ri), `403` (scope yetmaydi),
`429` (throttle).

### Filtr — nima uchun aynan `year` + `month`

LMS'dagi `academic.Group` da `month` va `year` maydonlari bor va real bazada
**barcha guruhlarda to'ldirilgan** (tekshirilgan: 30/30). `start_date`/`end_date`
esa **hammasida ham emas** (30 tadan 19 tasida) — shuning uchun sana oralig'i
bo'yicha filtrlash ishonchsiz.

Real ma'lumotda uchala usul solishtirildi (sentabr 2026):

| Filtr | Natija |
|---|---|
| `month=9, year=2026` | 19 ta guruh |
| `start_date`/`end_date` oralig'i | 19 ta guruh |
| O'sha oyda haqiqiy dars kuni bor guruhlar | 19 ta |

Uchalasi bir xil — demak `month`/`year` to'g'ri va yetarli.

KPI'dagi `Group` da ham `year` + `month` bor (`MONTH_CHOICES`, 1–12) — ya'ni
maydon nomlari va qiymat diapazoni **to'g'ridan-to'g'ri mos keladi**, hech qanday
konvertatsiya kerak emas.

### ⚠️ ONLAYN GURUHLAR IMPORT QILINMAYDI

Javobdagi `delivery_mode` ikki qiymat oladi: `offline` / `online`. Real bazada
sentabr oyida 19 guruhdan **1 tasi onlayn** (Zoom orqali).

**Onlayn guruhni import qilmang** — `delivery_mode == 'online'` bo'lganini
o'tkazib yuboring.

Nima uchun: onlayn guruh tinglovchilari hududga **umuman kelmaydi**, demak
face-ID + GPS tekshiruvidan hech qachon o'tmaydi. Agar bunday guruh KPI'ga
import qilinsa, LMS'da o'qituvchi yo'qlama qilmoqchi bo'lganda **butun ro'yxat
`checked_in=false`** bo'lib chiqadi, hech kimni "darsda bor" deb belgilay
olmaydi va dars har kuni avtomatik "o'tilmagan" deb yopiladi. Ya'ni to'g'ri
ishlayotgan onlayn guruh statistikada buzuq ko'rinadi.

Kodda:
```python
for row in rows:
    if row.get('delivery_mode') == 'online':
        skipped_online += 1
        continue          # onlayn guruh — face-ID mantiqiga tegishli emas
    ...
```
va foydalanuvchiga xabarda ko'rsating: `"3 ta onlayn guruh o'tkazib yuborildi."`

### KPI tomonda nima qilish kerak

**5.1.** `.env` ga (va `data/config.py` orqali o'qing):
```
LMS_BASE_URL=https://lms.boastful.uz
LMS_API_KEY=<LMS bergan to'liq kalit>
LMS_TIMEOUT=15
```

> Kalitni **hech qachon** kodga yozmang, `settings.py` ga qattiq kodlamang va
> git'ga commit qilmang. `.env` `.gitignore` da ekaniga ishonch hosil qiling.

**5.2.** Yangi fayl `apps/students/lms_client.py`:

```python
"""
LMS (SportEdu Jadval) bilan HTTP aloqa.

Bu yerda FAQAT tashqi so'rov mantiqiy joylashadi — view'lar bevosita
`requests` chaqirmasin. Sabab: timeout/qayta urinish/xato formatlash
bir joyda bo'lsa, keyinchalik o'zgartirish oson va view'lar sodda qoladi.
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class LMSError(Exception):
    """LMS bilan aloqada xato — foydalanuvchiga ko'rsatiladigan xabar bilan."""


def _headers():
    key = getattr(settings, 'LMS_API_KEY', '') or ''
    if not key:
        raise LMSError("LMS_API_KEY sozlanmagan (.env faylini tekshiring).")
    return {'Authorization': f'Api-Key {key}'}


def fetch_groups(year: int, month: int) -> list[dict]:
    """LMS'dan shu oy uchun guruhlar ro'yxatini oladi."""
    base = getattr(settings, 'LMS_BASE_URL', '').rstrip('/')
    if not base:
        raise LMSError("LMS_BASE_URL sozlanmagan.")
    url = f"{base}/api/v1/integration/groups/"
    try:
        r = requests.get(
            url, params={'year': year, 'month': month},
            headers=_headers(),
            timeout=getattr(settings, 'LMS_TIMEOUT', 15),
        )
    except requests.Timeout:
        raise LMSError("LMS javob bermadi (timeout). Keyinroq urinib ko'ring.")
    except requests.RequestException as e:
        logger.exception("LMS bilan aloqa xatosi")
        raise LMSError(f"LMS bilan aloqa o'rnatilmadi: {e}")

    if r.status_code == 401:
        raise LMSError("LMS kaliti qabul qilinmadi (401). Kalitni tekshiring.")
    if r.status_code == 403:
        raise LMSError("LMS kalitida bu amal uchun ruxsat yo'q (403).")
    if r.status_code != 200:
        raise LMSError(f"LMS kutilmagan javob qaytardi: {r.status_code}")

    data = r.json()
    return data.get('results', data if isinstance(data, list) else [])
```

**5.3.** Import view — `apps/students/views.py` ga (edu_admin panelida tugma):

```python
@edu_admin_required
def lms_import_groups(request):
    """
    LMS'dan guruhlarni import qiladi.

    MUHIM: so'rov SERVERDAN yuboriladi, brauzerdan emas — aks holda
    LMS_API_KEY frontend kodida ochiq qolib ketardi.
    """
    if request.method != 'POST':
        return redirect('students:groups')

    year  = int(request.POST.get('year'))
    month = int(request.POST.get('month'))
    # `request.admin_user` — `@edu_admin_required` dekoratori o'rnatadi
    # (`apps/superadmin/decorators.py`). Loyihaning mavjud naqshi shu —
    # boshqa usul bilan Administrator olishga urinmang.
    admin = request.admin_user

    try:
        rows = fetch_groups(year, month)
    except LMSError as e:
        messages.error(request, str(e))
        return redirect('students:groups')

    created = updated = 0
    for row in rows:
        obj, is_new = Group.objects.update_or_create(
            lms_group_code=row['code'],
            defaults={
                'name': row['name'],
                'year': row['year'],
                'month': row['month'],
                'organization': admin.organization,
                'filial': admin.filial,
                'lms_synced_at': timezone.now(),
            },
        )
        created += int(is_new)
        updated += int(not is_new)

    messages.success(
        request,
        f"LMS'dan import: {created} ta yangi guruh, {updated} ta yangilandi."
    )
    return redirect('students:groups')
```

### Muhim nozikliklar

- **`update_or_create` `lms_group_code` bo'yicha** — nom bo'yicha emas. LMS'da
  guruh nomi o'zgarsa, KPI'da **o'sha** guruh yangilanadi, dublikat yaratilmaydi.
- **Tinglovchilar (`students` M2M) import paytida TEGILMAYDI.** LMS tinglovchilarni
  bilmaydi. Import faqat guruh "qobig'ini" yaratadi; ichini edu_admin KPI'ning
  o'z oqimi bilan to'ldiradi (3-talab — bu butunlay KPI ichida qoladi).
- **`is_confirmed` ga tegmang** — bu KPI'ning o'z tasdiqlash oqimi.
- Import **idempotent** bo'lishi kerak: bir necha marta bosilsa ham natija bir xil.

---

## 5-B. VAZIFA A2 — kunlik lokatsiya va smenani import qilish

### Muammo: bir xil ish ikki marta qilinmoqda

Hozir edu_admin **ikkala tizimda alohida** "qaysi guruh, qaysi kuni, qayerda,
qaysi smenada" ma'lumotini kiritadi. Strukturalar deyarli bir xil:

| LMS | KPI | Izoh |
|---|---|---|
| `academic.GroupDayAssignment`<br>(group + date + shift + building) | `students.GroupLesson`<br>(group + date + smena + location) | **aynan bir xil**, ikkalasida ham `unique_together = (group, date)` |
| `academic.Shift` → `academic.Para` | `students.Smena` → `students.SmenaSlot` | para vaqtlari |
| `organizations.Building` | `main.Location` | joylashuv |

Real hajm (sentabr 2026): **414 ta kunlik yozuv**, 19 guruh, 3 bino, 3 smena.
Ya'ni ikki tizimda alohida kiritilsa — oyiga **828 marta** qo'lda kiritish.

Bundan ham xavflisi: ikkalasi bir-biriga mos kelmay qolishi. Agar LMS'da bino
o'zgartirilib KPI'da unutilsa, tinglovchi **to'g'ri joyda turgan bo'lsa ham**
face-ID "lokatsiya mos emas" deb rad etadi (`find_student_location` 150m
tekshiruvi noto'g'ri lokatsiyaga nisbatan bajariladi).

### ⚠️ Muhim assimetriya — yechim aynan shunga qurilgan

| Ma'lumot | LMS'da | KPI'da |
|---|---|---|
| Guruh qaysi kuni qayerda | ✅ **manba** | nusxa olinadi |
| Para vaqtlari | ✅ **manba** | nusxa olinadi |
| **GPS koordinata (`latitude`/`longitude`)** | ❌ **YO'Q** | ✅ **faqat shu yerda** |

LMS'dagi `Building` da faqat `name` va `address` bor — **GPS yo'q**. KPI'dagi
`main.Location` da esa `latitude`/`longitude` bor va aynan shular 150 metrlik
geo-tekshiruvda ishlatiladi. Ustiga-ustak `Location` KPI'da **xodimlar**
(`Employee`) davomati uchun ham ishlatiladi.

Shuning uchun `Location` ni LMS'dan import qilib bo'lmaydi va uni LMS'ga
ko'chirish ham kerak emas. Uch xil munosabat:

#### (1) `Smena` + `SmenaSlot` → TO'LIQ AVTOMATIK import

Sof vaqt ma'lumoti, GPS yo'q → LMS'dagi `Shift` + `Para` dan bir xil nusxa
yaratiladi, qo'lda hech narsa kiritilmaydi.

`Smena` modeliga qo'shing:
```python
lms_shift_code = models.UUIDField(null=True, blank=True, unique=True, db_index=True,
                                   verbose_name="LMS smena kodi")
```

Import mantig'i:
```python
smena, _ = Smena.objects.update_or_create(
    lms_shift_code=row['code'],
    defaults={'name': row['name'],
              'organization': admin.organization,
              'filial': admin.filial},
)
# Paralarni to'liq qayta yozish — LMS manba, KPI nusxa
smena.slots.all().delete()
SmenaSlot.objects.bulk_create([
    SmenaSlot(smena=smena, order=p['order'],
              start=p['start_time'], end=p['end_time'])
    for p in row['paras']
])
```

> `Smena` dagi eski `para1_start`/`para2_start`/`para3_start` maydonlariga
> **tegmang** — ular legacy, `get_slots()` avval `slots` ni tekshiradi va
> ular bo'lsa eski maydonlarni umuman o'qimaydi.

#### (2) `Location` → BIR MARTALIK qo'lda moslashtirish

`Location` modeliga qo'shing:
```python
lms_building_code = models.UUIDField(null=True, blank=True, unique=True,
                                      db_index=True, verbose_name="LMS bino kodi")
```

Edu_admin panelida oddiy sahifa: LMS'dan kelgan binolar ro'yxati (nom bilan)
va har birining yoniga KPI'dagi mavjud `Location` ni tanlaydigan `<select>`.
Saqlanganda tanlangan `Location.lms_building_code` to'ldiriladi.

**Bu bir martalik ish** — real ma'lumotda atigi **3 ta bino** bor
("Institut o'quv binosi", "Akademiya", "Sirdaryo"). Yangi bino qo'shilgandagina
qayta moslashtiriladi.

##### 🚨 QAT'IY VALIDATSIYA: GPS'siz `Location` ni tanlab bo'lmasin

`find_student_location()` ichida (`apps/students/api_views.py`) shunday kod bor:

```python
if loc.latitude and loc.longitude:
    dist = get_distance_meters(latitude, longitude, loc.latitude, loc.longitude)
    ok = dist < 150
else:
    # Koordinatlar kiritilmagan — lokatsiya tekshiruvini o'tkazib yuborish
    return loc_name, True, group, lesson, None      # ← ok=True !
```

Ya'ni `Location` da `latitude`/`longitude` **bo'sh bo'lsa, geo-tekshiruv
butunlay o'chib qoladi** va funksiya `ok=True` qaytaradi. Bunday lokatsiyaga
moslashtirilgan guruh tinglovchisi **dunyoning istalgan nuqtasidan** face-ID
qilib "keldim" deb yozdira oladi.

Buni sezish deyarli imkonsiz: xato chiqmaydi, log yozilmaydi, hammasi
"ishlayotgandek" ko'rinadi — faqat himoya yo'q. Butun integratsiyaning maqsadi
("faqat haqiqatan hududda bo'lganlar darsda bor deb belgilanadi") shu bilan
yo'qoladi.

Shuning uchun moslashtirish sahifasida:

```python
# dropdown uchun QUERYSET — GPS'siz lokatsiyalar umuman ko'rinmasin
locations = Location.objects.filter(
    organization=admin.organization,
    latitude__isnull=False,
    longitude__isnull=False,
)
```

va saqlashda server tomonda ham qayta tekshiring (dropdown chetlab o'tilishi
mumkin):
```python
if loc.latitude is None or loc.longitude is None:
    messages.error(request,
        f"«{loc.name}» lokatsiyasida GPS koordinatasi yo'q — "
        "avval uni kiriting, keyin moslashtiring.")
    return redirect(...)
```

Foydalanuvchiga sabab ko'rsatilsin, jimgina rad etilmasin.

Moslashtirilmagan bino uchun import qatorini **o'tkazib yubormang** —
`GroupLesson` ni `location=None` bilan yarating va foydalanuvchiga aniq
ogohlantirish bering:
> "«Sirdaryo» binosi hali KPI lokatsiyasiga moslashtirilmagan — 24 ta dars
> lokatsiyasiz yaratildi. «Binolarni moslashtirish» sahifasida bog'lang."

Nega o'tkazib yubormaslik kerak: sukut bilan yo'qolgan qator — bu loyihalarda
bir necha marta uchragan eng yomon xato turi (ma'lumot "bor-u lekin yo'q"
bo'lib qoladi va sababi hech qayerda ko'rinmaydi).

#### (3) `GroupLesson` → HAR OY AVTOMATIK import

Moslashtirish bir marta qilingandan keyin 414 ta yozuv bitta tugma bilan.

### Shartnoma — LMS taqdim etadi

```
GET  {LMS_BASE_URL}/api/v1/integration/day-assignments/?year=2026&month=9
Headers: Authorization: Api-Key <kalit>

200 OK
{
  "shifts": [
    {"code": "7c1e…", "name": "Kunduzgi",
     "paras": [
       {"order": 1, "name": "1-para", "start_time": "09:00", "end_time": "10:20"},
       {"order": 2, "name": "2-para", "start_time": "10:30", "end_time": "11:50"},
       {"order": 3, "name": "3-para", "start_time": "12:00", "end_time": "13:20"}
     ]}
  ],
  "buildings": [
    {"code": "b2f4…", "name": "Institut o'quv binosi",
     "address": "…", "is_regional": false}
  ],
  "assignments": [
    {"group_code": "3f2a…", "date": "2026-09-07",
     "shift_code": "7c1e…", "building_code": "b2f4…"}
  ]
}
```

`shift_code`/`building_code` `null` bo'lishi mumkin (LMS'da biriktirilmagan
bo'lsa) — bunda KPI'da ham mos maydon `None` qoladi.

Onlayn guruhlar bu javobda **umuman bo'lmaydi** (LMS tomoni filtrlaydi) —
5-bo'limdagi qoida bilan izchil.

### Import tartibi (qat'iy)

```
1. shifts     → Smena + SmenaSlot   (avtomatik)
2. buildings  → mavjud moslashtirish tekshiriladi (yangi Location YARATILMAYDI)
3. assignments → GroupLesson         (update_or_create(group=…, date=…))
```

`GroupLesson` da ham `unique_together = (group, date)` — LMS bilan bir xil,
shuning uchun `update_or_create` to'g'ri ishlaydi va qayta import dublikat
yaratmaydi.

Guruh `lms_group_code` bo'yicha topilmasa (avval import qilinmagan) — o'sha
qatorni o'tkazib yuboring va sanog'ini xabarda ko'rsating:
> "12 ta biriktiruv o'tkazib yuborildi — guruh KPI'da topilmadi. Avval
> guruhlarni import qiling."

### `GroupSchedule` bilan chalkashmang

KPI'dagi `find_student_location` avval `GroupLesson` ni, topilmasa
`GroupSchedule` (haftalik) ni tekshiradi. **LMS'dan import qilingan guruhlar
uchun `GroupSchedule` yaratmang** — aks holda yana ikkita manba paydo bo'ladi
va ular bir-biriga zid bo'lib qolishi mumkin. Import qilingan guruhlarda
kunlik `GroupLesson` har doim to'liq bo'ladi.

---

## 6. VAZIFA B — davomat endpointi (KPI = server, LMS = mijoz)

Bu integratsiyaning **asosiy qismi**. LMS o'qituvchi jurnal sahifasini ochganda
shu endpointni chaqiradi.

### Shartnoma — KPI shuni taqdim etadi

```
GET /api/integration/attendance/?group_code=<uuid>&date=2026-09-15
Headers:
    Authorization: Api-Key <KPI bergan kalit>

200 OK
{
  "group_code": "3f2a9c14-8b7e-4d51-9a02-1c6e5b8d7a33",
  "group_name": "Sport turlari bo'yicha yo'riqchi-uslubchilar-1",
  "date": "2026-09-15",
  "students": [
    {
      "id": 412,
      "full_name": "Aliyev Vali Salimovich",
      "checked_in": true,
      "check_in_time": "08:42:11",
      "check_out_time": null,
      "verified_by_face": true,
      "status": "present",
      "late_minutes": 0,
      "building": "Sport akademiyasi"
    },
    {
      "id": 413,
      "full_name": "Karimova Nodira",
      "checked_in": false,
      "check_in_time": null,
      "check_out_time": null,
      "verified_by_face": false,
      "status": null,
      "late_minutes": 0,
      "building": null
    }
  ]
}
```

**Guruhdagi BARCHA tinglovchilar qaytariladi** — kelganlari ham, kelmaganlari ham.
Ularni ajratuvchi maydon — `checked_in`. Nega hammasi: o'qituvchi to'liq ro'yxatni
ko'rishi kerak, aks holda "bu odam umuman ro'yxatda yo'qmi yoki kelmadimi?"
degan noaniqlik paydo bo'ladi.

Xato javoblari:
| Holat | Kod | Body |
|---|---|---|
| Kalit yuborilmagan / noto'g'ri | 403 | `{"detail": "...", "code": "invalid_key"}` |
| Mijoz o'chirilgan (`is_active=False`) | 403 | `{"detail": "...", "code": "inactive_client"}` |
| Ruxsat etilmagan IP | 403 | `{"detail": "...", "code": "ip_denied"}` |
| Scope yetmaydi | 403 | `{"detail": "...", "code": "scope_denied"}` |
| `group_code` yoki `date` yo'q | 400 | `{"error": "group_code va date majburiy"}` |
| `group_code` formati UUID emas | 400 | `{"error": "group_code UUID formatida bo'lishi kerak"}` |
| `date` formati noto'g'ri | 400 | `{"error": "date YYYY-MM-DD formatida bo'lishi kerak"}` |
| Bunday `lms_group_code` topilmadi | 404 | `{"error": "Guruh topilmadi. LMS'dan import qilinganmi?"}` |
| `GET` dan boshqa metod | 405 | `{"detail": "Method \"POST\" not allowed."}` |

> **Nima uchun 401 emas, hamma rad etish 403** (hujjatning avvalgi tahririda 401
> yozilgan edi — kod bilan mos kelmagani uchun tuzatildi): view'da
> `authentication_classes = []` turadi, ya'ni DRF'da autentifikatsiya bosqichi
> umuman yo'q va `WWW-Authenticate` sarlavhasi qaytarilmaydi. HTTP standarti
> bo'yicha bunday holatda 401 noto'g'ri bo'lardi, shuning uchun DRF 403 beradi.
> Custom authentication klass yozib 401 chiqarish mumkin edi, lekin bu allaqachon
> sinovdan o'tgan xavfsizlik yo'lini qayta yozishni talab qilardi — foydasi kam,
> chunki mashina-mijoz 401 va 403 ni baribir bir xil ("muvaffaqiyatsiz") qayta
> ishlaydi. **Sababni ajratish uchun `code` maydoni ishlatilsin**, HTTP kodi emas.

### Implementatsiya — `apps/students/api_views.py` ga qo'shing

```python
class IntegrationAttendanceAPIView(generics.GenericAPIView):
    """
    LMS uchun: guruhning berilgan kundagi face-ID davomati.

    LMS bu ma'lumot asosida o'qituvchiga yo'qlama ro'yxatini ko'rsatadi —
    faqat `checked_in=true` bo'lganlarni "darsda bor" deb belgilash mumkin.
    """
    authentication_classes = []
    permission_classes     = [HasIntegrationScope]
    required_scope         = 'attendance:read'
    throttle_scope         = 'integration'

    def get(self, request):
        import uuid as _uuid
        from datetime import date as _date

        group_code = request.query_params.get('group_code')
        date_str   = request.query_params.get('date')
        if not group_code or not date_str:
            return Response({'error': 'group_code va date majburiy'}, status=400)
        try:
            _uuid.UUID(str(group_code))
        except (ValueError, AttributeError, TypeError):
            return Response(
                {'error': 'group_code UUID formatida bo\'lishi kerak'}, status=400)
        try:
            day = _date.fromisoformat(date_str)
        except ValueError:
            return Response({'error': 'date YYYY-MM-DD formatida bo\'lishi kerak'},
                            status=400)

        try:
            group = Group.objects.get(lms_group_code=group_code)
        except Group.DoesNotExist:
            return Response(
                {'error': "Guruh topilmadi. LMS'dan import qilinganmi?"}, status=404)

        students = group.students.all().order_by('full_name')

        # Bitta so'rovda barcha davomat — N+1 ning oldini oladi
        att_map = {
            a.student_id: a
            for a in StudentAttendance.objects
                .filter(group=group, date=day, student__in=students)
                .select_related('building')
        }

        out = []
        for s in students:
            a = att_map.get(s.id)
            # "checked_in" = HAQIQATAN kirish vaqti qayd etilgan.
            # `status` ning o'zi yetarli emas: StudentAttendance da
            # default 'absent' bo'lgani uchun yozuv mavjud bo'lsa ham
            # odam kelmagan bo'lishi mumkin.
            checked_in = bool(a and a.check_in)
            out.append({
                'id': s.id,
                'full_name': s.full_name,
                'checked_in': checked_in,
                'check_in_time': a.check_in.isoformat() if (a and a.check_in) else None,
                'check_out_time': a.check_out.isoformat() if (a and a.check_out) else None,
                'verified_by_face': bool(a and a.verified_by_face),
                'status': a.status if a else None,
                'late_minutes': (a.late_minutes if a else 0),
                'building': (a.building.name if (a and a.building) else None),
            })

        return Response({
            'group_code': str(group.lms_group_code),
            'group_name': group.name,
            'date': day.isoformat(),
            'students': out,
        })
```

URL — **`apps/students/urls.py` ga QO'YILMAYDI**. Sabab: u `core/urls.py` da
`students/` prefiksi bilan ulanadi, ya'ni manzil `/students/api/integration/…`
bo'lib qolardi va yuqoridagi shartnomaga (`/api/integration/attendance/`) mos
kelmasdi. Shuning uchun alohida fayl ochilib, root ga ulanadi:

`apps/students/integration_urls.py`:
```python
from django.urls import path
from .api_views import IntegrationAttendanceAPIView

urlpatterns = [
    path('attendance/', IntegrationAttendanceAPIView.as_view(),
         name='integration-attendance'),
]
```

`core/urls.py`:
```python
path("api/integration/", include("apps.students.integration_urls")),
```

### `checked_in` mantig'i — diqqat qiling

`StudentAttendance.status` ning **default qiymati `'absent'`**. Ya'ni yozuv
mavjudligining o'zi "keldi" degani emas. Shuning uchun `checked_in` **faqat**
`check_in` maydoni to'lganiga qarab aniqlanadi. Buni o'zgartirmang — aks holda
kelmagan odam LMS'da "kelgan" bo'lib ko'rinadi va butun himoya buziladi.

---

## 7. LMS tomoni nima qiladi (KPI agenti bilishi uchun — bu yerda yozilmaydi)

Faqat kontekst uchun, KPI agenti bu qismni **qilmaydi**:

1. `academic.Group` ga `external_code = UUIDField(unique, default=uuid4)` qo'shadi.
2. `GET /api/v1/integration/groups/` endpointini ochadi (5-bo'limdagi shartnoma).
3. O'qituvchi jurnal sahifasida KPI'ning `/api/integration/attendance/` ini
   chaqirib, ro'yxatni ko'rsatadi (`checked_in=false` bo'lganlar `disabled`).
4. O'qituvchi saqlaganda `LessonAttendance` yozuvini **snapshot** bilan yozadi
   (o'sha paytdagi `checked_in` holati nusxalanadi).
5. Kun oxirida cron orqali to'ldirilmagan jurnal yozuvlarini `not_held`
   ("dars o'tilmagan") deb belgilaydi.

**KPI'dan talab qilinadigan yagona narsa** — 6-bo'limdagi endpoint ishlashi va
barqaror bo'lishi. Uning javob formati o'zgarsa, LMS tomoni sinadi — shuning
uchun formatni o'zgartirishdan oldin LMS agenti bilan kelishing.

---

## 8. Xavfsizlik — yakuniy tekshiruv ro'yxati

- [ ] `StudentCheckAPIView`, `EduAdminCheckAPIView`, `EduAdminStudentsAPIView` —
      `AllowAny` OLIB TASHLANGAN, `initData` imzosi tekshiriladi
- [ ] `user_id` / `admin_id` **body yoki query-param'dan O'QILMAYDI** —
      faqat tekshirilgan `initData` ichidan olinadi. Eski maydonlar
      serializer'dan butunlay olib tashlangan
- [ ] `BOT_TOKEN` sozlanmagan bo'lsa `verify_init_data` **xato ko'taradi**
      (ochiq qolmaydi, "o'tkazib yuborish" yo'q)
- [ ] `initData` yoshi tekshiriladi (`auth_date`) — takroriy (replay) hujum
      oldini olish uchun
- [ ] Imzo solishtirishda `hmac.compare_digest` ishlatilgan (`==` emas)
- [ ] 4 ta WebApp shabloni `init_data: tg.initData` yuboradi va server bilan
      **birga deploy qilinadi** (aks holda face-ID 401 bilan ishlamay qoladi)
- [ ] API kalitlar bazada **hash** ko'rinishida, to'liq kalit saqlanmaydi
- [ ] Solishtirishda `secrets.compare_digest` ishlatilgan (`==` emas)
- [ ] `.env` `.gitignore` da; `LMS_API_KEY` va `BOT_TOKEN` git'da yo'q
- [ ] Barcha integratsiya endpointlarida throttling yoqilgan
- [ ] Faqat HTTPS (production nginx'da HTTP → HTTPS redirect)
- [ ] `allowed_ips` LMS serveri IP'si bilan to'ldirilgan (nginx ishlatilsa)
- [ ] Davomat endpointi **faqat o'qish** — hech qanday POST/PATCH yo'q
- [ ] Javobda **ortiqcha shaxsiy ma'lumot yo'q**: `telegram_id`, `phone`,
      `face_encoding`, `plain_password` **hech qachon** qaytarilmasin
      (yuqoridagi kodda ular yo'q — shunday qoldiring)
- [ ] **GPS'siz `Location` ga moslashtirib bo'lmaydi** — dropdown'da
      ko'rinmaydi VA server tomonda ham rad etiladi (5-B, 2-band).
      Aks holda `find_student_location()` geo-tekshiruvni jimgina
      o'tkazib yuboradi va istalgan joydan face-ID qilish mumkin bo'ladi.

---

## 9. Bajarish tartibi

| № | Ish | Bo'lim | Bog'liqlik |
|---|---|---|---|
| 1 | Mavjud `AllowAny` endpointlarni yopish | 2 | — |
| 2 | `IntegrationClient` modeli + migratsiya | 3 | — |
| 3 | `HasIntegrationScope` permission + management command | 3 | 2 |
| 4 | `Group.lms_group_code` + migratsiya | 4 | — |
| 5 | Davomat endpointi (LMS o'qiydi) | 6 | 3, 4 |
| 6 | Guruhlarni import | 5 | 4 |
| 7 | `Smena.lms_shift_code`, `Location.lms_building_code` + migratsiya | 5-B | — |
| 8 | Binolarni moslashtirish sahifasi (bir martalik, qo'lda) | 5-B | 7 |
| 9 | Kunlik biriktiruvlarni import (`GroupLesson`) | 5-B | 6, 8 |

**1-vazifa boshqa hammasidan oldin bajarilishi shart.**

- **5** (davomat endpointi) mustaqil — LMS tayyor bo'lmasa ham `curl` bilan
  to'liq sinaladi. Uni birinchi tugatish ma'qul: LMS tomoni aynan shuni kutadi.
- **6 → 8 → 9** ketma-ket: guruhlar bo'lmasa kunlik biriktiruvni bog'lab
  bo'lmaydi, binolar moslashtirilmasa `GroupLesson.location` bo'sh qoladi.
- **9** eng katta amaliy foyda beradi (oyiga 414 ta qo'lda kiritishni yo'q
  qiladi), lekin u 6 va 8 siz ishlamaydi — tartibni buzmang.

---

## 10. Tekshirish (verification)

Har bir qadamdan keyin bajaring — **taxmin qilmang, o'lchang**:

```bash
# 0. Migratsiyalar
python manage.py makemigrations && python manage.py migrate
python manage.py check

# 1. initData'siz YOPIQ ekanini tasdiqlash (401 kutiladi)
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  http://localhost:8000/students/api/check/ \
  -H "Content-Type: application/json" \
  -d '{"type":"check_in","latitude":41.0,"longitude":69.0}'

# 2. Soxta initData bilan ham YOPIQ ekanini tasdiqlash (401 kutiladi)
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  http://localhost:8000/students/api/check/ \
  -H "Content-Type: application/json" \
  -d '{"init_data":"user=%7B%22id%22%3A123%7D&hash=aaaa","type":"check_in","latitude":41.0,"longitude":69.0}'

# 2b. `user_id` ni body'da yuborib ko'ring — E'TIBORGA OLINMASLIGI kerak
#     (serializer'da bunday maydon umuman qolmagan bo'lishi shart)

# 3. Integratsiya kaliti yaratish
python manage.py create_integration_key "LMS test" --scopes attendance:read

# 4. Davomat endpointi — kalitsiz (403 + code=invalid_key kutiladi)
curl -s -w "\n%{http_code}\n" \
  "http://localhost:8000/api/integration/attendance/?group_code=<uuid>&date=2026-09-15"

# 5. Kalit bilan (200 + JSON kutiladi)
curl -s "http://localhost:8000/api/integration/attendance/?group_code=<uuid>&date=2026-09-15" \
  -H "Authorization: Api-Key <to'liq kalit>" | python -m json.tool

# 6. Noto'g'ri scope'li kalit bilan (403 + code=scope_denied kutiladi)
python manage.py create_integration_key "Scope test" --scopes students:read
curl -s -w "\n%{http_code}\n" \
  "http://localhost:8000/api/integration/attendance/?group_code=<uuid>&date=2026-09-15" \
  -H "Authorization: Api-Key <scope-test kaliti>"

# 7. O'chirilgan mijoz kaliti (403 + code=inactive_client kutiladi)
#    admin panelda yoki shell da: client.is_active = False; client.save()
```

Qo'shimcha, `manage.py shell` da tekshiring:
- Guruhda 3 ta tinglovchi bo'lsa, javobda ham **3 tasi** bo'lishi (kelmaganlari ham)
- `check_in` `null` bo'lgan tinglovchida `checked_in=false` ekani
- `status='absent'` lekin `check_in` to'lgan holatda ham `checked_in=true` ekani
- Javobda `telegram_id`/`phone`/`plain_password` **yo'qligi**

Import uchun (LMS tayyor bo'lgach):
- Import ikki marta bosilsa dublikat yaratilmasligi
- LMS'da guruh nomi o'zgartirilib qayta import qilinsa — **o'sha** guruh
  yangilanishi, yangisi yaratilmasligi
- Import tinglovchilar ro'yxatiga (`students` M2M) **tegmasligi**

---

## 11. Bu loyihaning mavjud qoidalari (eslatma)

`CLAUDE.md` dan — buzilmasin:
- `git push --force` va `git reset --hard` — **taqiqlangan**
- `cv2`, `face_recognition` — o'rnatilmagan, `mediapipe` ishlatiladi
- Model o'zgartirilsa — **migratsiya yaratishni unutmang**
- Async kontekstda ORM — `sync_to_async` orqali
- Stack: Django 5.2.4 + DRF 3.16, PostgreSQL (prod) / SQLite (local)
