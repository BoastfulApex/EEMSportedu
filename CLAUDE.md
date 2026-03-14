# KpiProject — Claude Code uchun loyiha konteksti

## Texnologiyalar
- **Backend:** Django 5.2.4, Django REST Framework
- **Bot:** Aiogram 3.21 (async)
- **DB:** PostgreSQL (production) / SQLite (local)
- **Yuz aniqlash:** mediapipe 0.10.32 + Pillow
- **Boshqa:** openpyxl, geopy, Redis (bot FSM uchun)
- **OS:** Windows (local), Linux (production)

---

## Loyiha tuzilmasi
```
KpiProject-master/
├── core/               ← settings.py, urls.py
├── apps/
│   ├── main/           ← asosiy modellar, API, formlar
│   ├── home/           ← admin panel views, hisobot
│   ├── superadmin/     ← tashkilot boshqaruvi, rol tizimi
│   └── authentication/ ← login/logout
├── handlers/           ← Telegram bot handlerlar
│   └── users/
│       ├── start.py    ← /start handler
│       └── stats.py    ← xodim statistika handler (YANGI)
├── keyboards/
│   └── inline/
│       ├── main_inline.py   ← bot klaviaturalari
│       └── menu_button.py
├── utils/db_api/
│   └── database.py     ← DB async funksiyalar
├── states/users.py     ← FSM states
└── run.py              ← bot ishga tushirish
```

---

## Modellar arxitekturasi

### `apps/superadmin/models.py`
```python
Organization  →  Filial  →  Building
Administrator (rol tizimi bilan)
Weekday
```

**Administrator rollari:**
| role | Vakolat |
|------|---------|
| `org_admin` | Hammasi (superadmin) |
| `hr_admin` | Xodimlarni boshqarish |
| `edu_admin` | Guruh, tinglovchi, jadval |
| `monitoring` | Faqat hisobotlarni ko'rish |

Properties: `is_org_admin`, `is_hr_admin`, `is_edu_admin`, `is_monitoring`

### `apps/main/models.py`
```python
TelegramUser
Location  (organization FK)
Employee  (employee_type: employee/teacher, image field)
WorkSchedule  (employee, weekday M2M, location FK, start, end)
ExtraSchedule (employee, weekday M2M, location FK, start, end)  ← qo'shimcha lokatsiya
Attendance    (employee, date, check_in, check_out, location FK, check_number)
SalaryConfig  (employee OneToOne, monthly_hours, monthly_salary) ← YANGI
```

**SalaryConfig logikasi:**
- `monthly_hours` — oyda ishlashi kerak bo'lgan soat (masalan 168)
- `monthly_salary` — oylik oklad (so'm)
- `hourly_rate` — property, avtomatik: `monthly_salary / monthly_hours`

---

## Ko'p lokatsiya arxitekturasi

O'qituvchilar bir kunda bir nechta joylashuvda ishlashi mumkin.

**Kirish/chiqish tekshiruv tartibi (`api_views.py`):**
1. `ExtraSchedule` — hozirgi vaqtga mos qo'shimcha jadval bormi? → shu lokatsiyani tekshir
2. `WorkSchedule` — asosiy jadvalning lokatsiyasini tekshir
3. Fallback — tashkilotning barcha lokatsiyalari

---

## Rol asosida kirish nazorati

### Dekoratorlar (`apps/superadmin/decorators.py`)
```python
@org_admin_required    # faqat org_admin
@hr_admin_required     # org_admin + hr_admin
@edu_admin_required    # org_admin + edu_admin
@monitoring_required   # org_admin + monitoring
@any_admin_required    # istalgan administrator
```

Har bir dekorator `request.admin_user` ni o'rnatadi.

### Context processors (`apps/superadmin/context_processors.py`)
Barcha template larga avtomatik uzatiladi:
- `is_org_admin`, `is_hr_admin`, `is_edu_admin`, `is_monitoring`
- `admin_role`, `admin_user`

---

## Hisobot tizimi (`apps/home/views.py`)

### `build_report(start_date, end_date, filial_id=None)`
- ExtraSchedule ni hisobga oladi
- Har bir xodimning asosiy + qo'shimcha jadval qatorlari alohida
- Har qatorda: `schedule_type` (Asosiy/Qo'shimcha), `location`, `worked` (jami soat), `employee_type`

### `build_report_for_employee(employee_id, start_date, end_date)`
- Bitta xodim bo'yicha, xuddi shu mantiq

### Excel eksport ustunlari:
`T/r, Sana, Hafta kuni, Xodim, Turi, Holati, Jadval turi, Lokatsiya, Jadval boshlanish, Jadval tugash, Kirish, Chiqish, Jami ish vaqti, Kechikdi, Erta ketdi`

---

## Bot arxitekturasi

### Xodim `/start` oqimi:
```
/start
  ├── Admin → admin menyusi
  ├── Xodim (rasmi bor) → employee_main_keyboard()
  │     ├── 🖥 Kirish (web app)
  │     └── 📊 Mening statistikam → oylar ro'yxati → oy statistikasi
  ├── Xodim (rasmi YO'Q) → rasm so'rash (EmployeeRegistration.waiting_for_photo state)
  └── Notanish → Administratorga murojaat
```

### Xodim statistika (`handlers/users/stats.py`):
- `my_stats` callback → `get_available_months()` → oylar klaviaturasi
- `stats_{year}_{month}` callback → `get_employee_monthly_stats()` → ko'rsatish
- Ko'rsatiladigan ma'lumotlar: kelgan kunlar / ish kunlari, ishlagan soat, kerakli soat, progress bar (%)
- **Maosh ko'rinmaydi** — faqat soat va kun statistikasi

### DB funksiyalar (`utils/db_api/database.py`):
- `get_available_months(user_id)` — oxirgi 6 oy + joriy oy
- `get_employee_monthly_stats(user_id, year, month)` — oy statistikasi

---

## Admin panel navigatsiya

### Navbar (o'ng yuqori — Admin bosganda):
- Tashkilotga tegishli **filiallar ro'yxati** (bosganda shu filialga o'tadi)
- Chiqish tugmasi
- "Super Admin" yo'q

### Sidebar (chap menyu):
- **Dashboard** — hammaga
- **Xodimlar** (hr_admin + org_admin, filial tanlanganda):
  - Xodimlar ro'yxati
  - Ish jadvallari
- **Hisobot** (filial tanlanganda)
- **Boshqaruv** (faqat org_admin, super_admin rejimida):
  - Filiallar
  - Lokatsiyalar
  - **Administratorlar** (accordion):
    - Ro'yxat
    - 👥 Xodimlar bo'limi admini yaratish (`?role=hr_admin`)
    - 📚 O'quv bo'limi admini yaratish (`?role=edu_admin`)
    - 📊 Monitoring admini yaratish (`?role=monitoring`)

---

## Muhim texnik qarorlar
- `cv2` va `face_recognition` o'rnatilmagan → `mediapipe` ishlatiladi
- `mediapipe` bo'lmasa → `detect_face()` `True` qaytaradi (fallback)
- Rasm `files/employee_photos/emp_{id}.jpg` ga saqlanadi
- `STATICFILES_DIRS = [os.path.join(BASE_DIR, 'apps/static/')]`
- `STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles/')`
- urls.py da: `static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])`

---

## Migration holati (oxirgi)
```
apps/main:       0010_location_organization (+ ExtraSchedule, SalaryConfig — yangi)
apps/superadmin: 0005_organization_... (+ Administrator.role — yangi)
```

Serverda bajarish:
```bash
python manage.py makemigrations main superadmin
python manage.py migrate
```

---

## Pending (bajarilmagan)
- Tinglovchilar moduli (`apps.students`) — keyinroq
- Hisobotda jami ish vaqti summasi (footer)
- Bot: `/jadval` buyrug'i — xodimga bugungi jadvalini ko'rsatish
- Jarima/ustama tizimi (SalaryConfig da `penalty_rate`, `bonus_rate` — hozir 0)
