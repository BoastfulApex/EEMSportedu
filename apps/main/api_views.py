from rest_framework.response import Response
from rest_framework import serializers, generics
from rest_framework.renderers import JSONRenderer
from rest_framework.permissions import AllowAny
from .models import Location, Attendance, Employee, WorkSchedule, ExtraSchedule, Schedule, ScheduleDay, TelegramUser
from django.utils import timezone
from apps.superadmin.models import Administrator
from datetime import datetime
from data import config
import requests
import base64, io, os, tempfile
import numpy as np
from PIL import Image

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================



def base64_to_pil(base64_image):
    if "," in base64_image:
        _, data = base64_image.split(",", 1)
    else:
        data = base64_image
    return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")


def verify_face(employee, base64_image):
    if not employee.image:
        return False, "Xodim rasmi topilmadi"

    try:
        unknown_pil = base64_to_pil(base64_image)
    except Exception as e:
        return False, f"Yuklangan rasm o'qilmadi: {e}"

    if not DEEPFACE_AVAILABLE:
        # DeepFace yo'q bo'lsa — o'tkazib yuborish
        return True

    try:
        # Vaqtincha fayl sifatida saqlash (DeepFace fayl yo'li talab qiladi)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            unknown_pil.save(tmp.name, format='JPEG')
            tmp_path = tmp.name

        result = DeepFace.verify(
            img1_path=employee.image.path,
            img2_path=tmp_path,
            model_name="Facenet",
            enforce_detection=False,
            silent=True,
        )
        os.unlink(tmp_path)

        if result["verified"]:
            return True
        else:
            distance = round(result.get("distance", 0), 2)
            return False, f"Yuz mos kelmadi (masofa: {distance})"

    except Exception as e:
        # Xato bo'lsa — o'tkazib yuborish
        return True


def get_distance_meters(lat1, lon1, lat2, lon2):
    from geopy.distance import geodesic
    return geodesic((lat1, lon1), (lat2, lon2)).meters


def get_time_difference(sch_time, now_time):
    sch_dt = datetime.combine(timezone.localdate(), sch_time)
    now_dt = datetime.combine(timezone.localdate(), now_time)
    return int((now_dt - sch_dt).total_seconds())


def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=5)
    except Exception:
        pass


def find_matching_location(employee, latitude, longitude, weekday_id, now_time):
    """
    Xodimning hozirgi vaqt va joylashuviga mos lokatsiyani topadi.

    Tekshiruv tartibi:
    1. Employee.schedules (yangi) — bugungi kunga mos jadvallarni tekshir
    2. Tashkilotning barcha lokatsiyalari — umumiy fallback

    Qaytaradi: (location, schedule, schedule_type) yoki (None, None, None)
    """
    # 1. Yangi ScheduleDay — xodimning bugungi kunga mos jadval kunlari
    schedule_days = ScheduleDay.objects.filter(
        schedule__employees=employee,
        weekday__id=weekday_id,
        schedule__location__isnull=False
    ).select_related('schedule__location')

    matched_day = None
    for sd in schedule_days:
        loc = sd.schedule.location
        if loc.latitude and loc.longitude:
            dist = get_distance_meters(latitude, longitude, loc.latitude, loc.longitude)
            if dist < 150:
                return loc, sd, 'main'
        if matched_day is None:
            matched_day = sd

    # 2. Tashkilotning barcha lokatsiyalari (fallback)
    if employee.filial and employee.filial.organization:
        all_locations = Location.objects.filter(
            organization=employee.filial.organization,
            latitude__isnull=False,
            longitude__isnull=False
        )
        for loc in all_locations:
            dist = get_distance_meters(latitude, longitude, loc.latitude, loc.longitude)
            if dist < 150:
                return loc, matched_day, 'fallback'

    return None, None, None


# ============================================================
# API SERIALIZER
# ============================================================

class CheckRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=['check_in', 'check_out'])
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    image = serializers.CharField()

    def validate(self, attrs):
        if not attrs.get("image"):
            raise serializers.ValidationError("Image majburiy.")
        return attrs


# ============================================================
# API VIEW
# ============================================================

class SimpleCheckAPIView(generics.ListCreateAPIView):
    serializer_class       = CheckRequestSerializer
    renderer_classes       = [JSONRenderer]
    authentication_classes = []
    permission_classes     = [AllowAny]

    def get_queryset(self):
        return []

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_id      = data['user_id']
        check_type   = data['type']
        latitude     = data['latitude']
        longitude    = data['longitude']
        image_base64 = data['image']

        # Xodimni topish
        try:
            employee = Employee.objects.get(telegram_user_id=user_id)
        except Employee.DoesNotExist:
            return Response({"status": "FAIL", "reason": "Foydalanuvchi topilmadi"}, status=404)

        # Hozirgi vaqt va hafta kuni
        today      = timezone.localdate()
        now_time   = timezone.localtime().time()
        weekday_id = today.weekday() + 1  # 1=Dushanba ... 7=Yakshanba

        # Lokatsiya topish
        location, schedule, schedule_type = find_matching_location(
            employee, latitude, longitude, weekday_id, now_time
        )

        if location is None:
            return Response({
                "status": "FAIL",
                "reason": "Siz hech qaysi ish lokatsiyasiga yaqin emassiz."
            }, status=403)

        # Davomat
        attendance, _ = Attendance.objects.get_or_create(employee=employee, date=today)

        if check_type == 'check_in':
            # Yuz tekshirish — faqat kirish uchun
            if employee.image:
                face_result = verify_face(employee, image_base64)
                if face_result is not True:
                    reason = face_result[1] if isinstance(face_result, tuple) else "FaceID mos kelmadi"
                    return Response({"status": "FAIL", "reason": reason}, status=403)

            attendance.check_number = (attendance.check_number or 0) + 1
            attendance.check_in = attendance.check_in or now_time

        elif check_type == 'check_out':
            attendance.check_out = now_time
            if attendance.check_in:
                worked = datetime.combine(today, attendance.check_out) - \
                         datetime.combine(today, attendance.check_in)
                hours, rem = divmod(int(worked.total_seconds()), 3600)
                minutes, _ = divmod(rem, 60)
                msg = (
                    f"👤 Xodim: {employee.name}\n"
                    f"📅 Sana: {today}\n"
                    f"📍 Lokatsiya: {location.name or '-'}\n"
                    f"⏰ Kirish: {attendance.check_in.strftime('%H:%M')}\n"
                    f"🚪 Chiqish: {attendance.check_out.strftime('%H:%M')}\n"
                    f"⌛ Ish vaqti: {hours:02d}:{minutes:02d}"
                )
                send_telegram_message(employee.telegram_user_id, msg)

        attendance.save()

        # Adminlarga xabar
        admins = Administrator.objects.filter(filial=employee.filial)
        for admin in admins:
            if not admin.telegram_id:
                continue

            # Jadval bilan solishtiruv
            status_text = ""
            if schedule:
                expected = schedule.start if check_type == 'check_in' else schedule.end
                delta_sec = get_time_difference(expected, now_time)
                min_diff = abs(delta_sec) // 60
                if delta_sec == 0:
                    status_text = "🟢 O'z vaqtida"
                elif check_type == 'check_in':
                    status_text = f"🔴 Kechikdi: {min_diff} daqiqa" if delta_sec > 0 \
                                  else f"🟡 Erta keldi: {min_diff} daqiqa"
                else:
                    status_text = f"🟡 Erta ketdi: {min_diff} daqiqa" if delta_sec < 0 \
                                  else f"🔵 Kech ketdi: {min_diff} daqiqa"

            loc_label = f"\n📍 {location.name}" if location.name else ""
            msg_lines = [
                f"👤 {employee.name}",
                f"{'✅ Keldi' if check_type == 'check_in' else '🚪 Ketdi'}: {now_time.strftime('%H:%M')}",
                f"📅 {today.strftime('%Y-%m-%d')}{loc_label}",
            ]
            if status_text:
                msg_lines.append(status_text)

            if check_type == 'check_in' and attendance.check_number == 1:
                send_telegram_message(admin.telegram_id, "\n".join(msg_lines))
            elif check_type == 'check_out':
                send_telegram_message(admin.telegram_id, "\n".join(msg_lines))

        return Response({
            "status": "SUCCESS",
            "type": check_type,
            "time": now_time.strftime('%H:%M:%S'),
            "location": location.name or "Noma'lum lokatsiya"
        }, status=200)


# ════════════════════════════════════════════════════════════════
# TEST DATA UPLOAD API
# ════════════════════════════════════════════════════════════════

from rest_framework.views import APIView
from django.contrib.auth.models import User
from apps.superadmin.models import Organization, Filial

class TestDataUploadAPIView(APIView):
    """
    Test datalarini yuklash uchun API.

    POST /api/test-upload/
    {
        "org_id": 1,
        "filial_id": 1,
        "test_data": {...}
    }
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from datetime import datetime as dt
        import json

        org_id = request.data.get('org_id')
        filial_id = request.data.get('filial_id')
        test_data = request.data.get('test_data')

        # test_data dict emas bo'lsa parse qilamiz
        if test_data and not isinstance(test_data, dict):
            try:
                if hasattr(test_data, 'read'):
                    # File object
                    test_data = json.loads(test_data.read().decode('utf-8'))
                else:
                    # String
                    test_data = json.loads(str(test_data))
            except:
                return Response({
                    "status": "FAIL",
                    "reason": "test_data JSON parse xatosi"
                }, status=400)

        if not all([org_id, filial_id, test_data]):
            return Response({
                "status": "FAIL",
                "reason": "org_id, filial_id va test_data majbur"
            }, status=400)

        try:
            org = Organization.objects.get(id=org_id)
            filial = Filial.objects.get(id=filial_id, organization=org)
        except Exception as e:
            return Response({
                "status": "FAIL",
                "reason": f"Organization yoki Filial topilmadi: {str(e)}"
            }, status=404)

        results = {
            "locations_created": 0,
            "employees_created": 0,
            "schedules_created": 0,
            "attendances_created": 0,
            "errors": []
        }

        # Debug
        print(f"DEBUG: org={org}, filial={filial}")
        print(f"DEBUG: test_data keys = {list(test_data.keys())}")
        print(f"DEBUG: locations count = {len(test_data.get('locations', []))}")
        print(f"DEBUG: employees count = {len(test_data.get('employees', []))}")

        # ── Locations ──
        for loc_data in test_data.get('locations', []):
            try:
                loc, created = Location.objects.get_or_create(
                    name=loc_data['name'],
                    organization=org,
                    defaults={
                        'latitude': loc_data['latitude'],
                        'longitude': loc_data['longitude'],
                    }
                )
                if created:
                    results["locations_created"] += 1
            except Exception as e:
                results["errors"].append(f"Location '{loc_data.get('name')}': {str(e)}")

        # ── Employees ──
        print(f"DEBUG: Processing {len(test_data.get('employees', []))} employees")
        for emp_data in test_data.get('employees', []):
            try:
                tg_user, _ = TelegramUser.objects.get_or_create(
                    user_id=emp_data['telegram_user_id']
                )
                emp, created = Employee.objects.get_or_create(
                    telegram_user_id=emp_data['telegram_user_id'],
                    defaults={
                        'name': emp_data['name'],
                        'employee_type': emp_data.get('employee_type', 'employee'),
                        'filial': filial,
                    }
                )
                if created:
                    print(f"  ✓ Created: {emp_data['name']}")
                    results["employees_created"] += 1
                else:
                    print(f"  - Already exists: {emp_data['name']}")
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
                results["errors"].append(f"Employee '{emp_data.get('name')}': {str(e)}")

        # ── Schedules ──
        from apps.superadmin.models import Weekday
        for sch_data in test_data.get('schedules', []):
            try:
                emp = Employee.objects.get(
                    telegram_user_id=sch_data['employee_telegram_id']
                )
                loc = Location.objects.get(
                    name=sch_data['location_name'],
                    organization=org
                )

                sch, _ = Schedule.objects.get_or_create(
                    name=sch_data['name'],
                    employee=emp,
                    location=loc,
                    defaults={'filial': filial}
                )

                # Weekday'larni qo'shish
                weekday_ids = sch_data.get('weekdays', [])
                for wd_id in weekday_ids:
                    try:
                        weekday = Weekday.objects.get(id=wd_id)
                        sch.weekday.add(weekday)
                    except:
                        pass

                # ScheduleDay qo'shish
                start_time = sch_data['start_time']
                end_time = sch_data['end_time']
                for day_num in weekday_ids:
                    ScheduleDay.objects.get_or_create(
                        schedule=sch,
                        day=day_num,
                        defaults={
                            'start_time': start_time,
                            'end_time': end_time,
                        }
                    )

                results["schedules_created"] += 1
            except Exception as e:
                results["errors"].append(f"Schedule: {str(e)}")

        # ── Attendances ──
        for att_data in test_data.get('attendances', []):
            try:
                emp = Employee.objects.get(
                    telegram_user_id=att_data['telegram_user_id']
                )
                loc = Location.objects.get(
                    name=att_data['location_name'],
                    organization=org
                )

                date_obj = dt.strptime(att_data['date'], '%Y-%m-%d').date()
                check_in = dt.strptime(att_data['check_in'], '%H:%M').time()
                check_out = dt.strptime(att_data['check_out'], '%H:%M').time()

                att, created = Attendance.objects.get_or_create(
                    employee=emp,
                    date=date_obj,
                    defaults={
                        'check_in': check_in,
                        'check_out': check_out,
                        'location': loc,
                        'check_number': 1,
                    }
                )
                if created:
                    results["attendances_created"] += 1
            except Exception as e:
                results["errors"].append(f"Attendance: {str(e)}")

        return Response({
            "status": "SUCCESS",
            "message": "Test datalar yuklandi",
            "results": results
        }, status=200)


# ════════════════════════════════════════════════════════════════
# ATTENDANCE GENERATION API  —  oxirgi 45 kun uchun davomat
# ════════════════════════════════════════════════════════════════

class GenerateAttendanceAPIView(APIView):
    """
    Bazadagi mavjud xodimlar uchun oxirgi 45 kunlik
    kirish/chiqish ma'lumotlarini generatsiya qiladi.

    POST /web_app/api/generate-attendance/
    {
        "secret": "dev_only",          # majburiy
        "skip_weekends": true,         # ixtiyoriy, default true
        "absent_probability": 0.1,     # ixtiyoriy, default 0.1 (10%)
        "overwrite": false             # ixtiyoriy, default false
    }

    Javob:
    {
        "status": "SUCCESS",
        "employees_count": 42,
        "days_range": 45,
        "attendances_created": 1512,
        "attendances_skipped": 38,
        "absent_days": 120
    }
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    SECRET = "dev_only"

    def post(self, request):
        import random
        from datetime import date, timedelta, time as dt_time

        # ── Autentifikatsiya ──
        if request.data.get("secret") != self.SECRET:
            return Response({"status": "FAIL", "reason": "Secret noto'g'ri"}, status=403)

        # ── Parametrlar ──
        skip_weekends     = request.data.get("skip_weekends", True)
        absent_prob       = float(request.data.get("absent_probability", 0.10))
        overwrite         = request.data.get("overwrite", False)
        days_range        = int(request.data.get("days", 45))

        # ── Sana oralig'i ──
        today   = date.today()
        start   = today - timedelta(days=days_range - 1)
        dates   = []
        d = start
        while d <= today:
            if skip_weekends and d.weekday() >= 5:   # 5=shanba, 6=yakshanba
                d += timedelta(days=1)
                continue
            dates.append(d)
            d += timedelta(days=1)

        # ── Xodimlar va lokatsiyalar ──
        employees = list(Employee.objects.select_related('filial__organization').all())
        if not employees:
            return Response({"status": "FAIL", "reason": "Bazada xodim yo'q"}, status=404)

        # Har xodim uchun uning filialiga tegishli locationlarni topamiz
        def get_locations_for_employee(emp):
            if emp.filial and emp.filial.organization:
                locs = list(Location.objects.filter(
                    organization=emp.filial.organization,
                    latitude__isnull=False,
                    longitude__isnull=False
                ))
                if locs:
                    return locs
            # fallback — barcha locationlar
            return list(Location.objects.filter(
                latitude__isnull=False,
                longitude__isnull=False
            ))

        # ── Vaqt generatsiyasi ──
        # Har xodimga o'ziga xos ish vaqti (turlilik uchun)
        SHIFT_PROFILES = [
            {"base_in": (8, 0),  "base_out": (17, 0)},
            {"base_in": (9, 0),  "base_out": (18, 0)},
            {"base_in": (8, 30), "base_out": (17, 30)},
        ]

        def random_time_near(hour, minute, variance_min=20):
            """Berilgan vaqt atrofida ±variance_min daqiqa ichida random vaqt"""
            base_minutes = hour * 60 + minute
            delta = random.randint(-variance_min, variance_min)
            total = max(0, min(23 * 60 + 59, base_minutes + delta))
            return dt_time(total // 60, total % 60)

        # ── Generatsiya ──
        created_count  = 0
        skipped_count  = 0
        absent_count   = 0

        for emp in employees:
            profile = random.choice(SHIFT_PROFILES)
            locations = get_locations_for_employee(emp)
            location  = random.choice(locations) if locations else None

            for day in dates:
                # Yo'qlik holati
                if random.random() < absent_prob:
                    absent_count += 1
                    continue

                check_in  = random_time_near(*profile["base_in"])
                check_out = random_time_near(*profile["base_out"])

                # check_out har doim check_in dan keyin bo'lsin
                in_min  = check_in.hour  * 60 + check_in.minute
                out_min = check_out.hour * 60 + check_out.minute
                if out_min <= in_min:
                    out_min = in_min + random.randint(420, 540)  # 7-9 soat
                    out_min = min(out_min, 23 * 60 + 59)
                    check_out = dt_time(out_min // 60, out_min % 60)

                if overwrite:
                    att, created = Attendance.objects.update_or_create(
                        employee=emp,
                        date=day,
                        location=location,
                        defaults={
                            "check_in":      check_in,
                            "check_out":     check_out,
                            "check_number":  1,
                        }
                    )
                    if created:
                        created_count += 1
                    else:
                        skipped_count += 1
                else:
                    att, created = Attendance.objects.get_or_create(
                        employee=emp,
                        date=day,
                        location=location,
                        defaults={
                            "check_in":      check_in,
                            "check_out":     check_out,
                            "check_number":  1,
                        }
                    )
                    if created:
                        created_count += 1
                    else:
                        skipped_count += 1

        return Response({
            "status":              "SUCCESS",
            "employees_count":     len(employees),
            "days_range":          days_range,
            "working_days":        len(dates),
            "attendances_created": created_count,
            "attendances_skipped": skipped_count,
            "absent_days":         absent_count,
        }, status=200)


# ════════════════════════════════════════════════════════════════
# RESET & SEED API  —  tozalab, yangi ma'lumot yuklash
# ════════════════════════════════════════════════════════════════

class ResetAndSeedAPIView(APIView):
    """
    Barcha eski ma'lumotlarni o'chirib, JSON dan yangisini yuklaydi.

    POST /web_app/api/reset-and-seed/
    {
        "secret": "dev_only",
        "clear_existing": true,
        "date_from": "2026-03-01",
        "date_to": "2026-04-04",
        "work_days": [1,2,3,4,5,6],       // 1=Dushanba...7=Yakshanba
        "absent_probability": 0.08,
        "locations": [
            {"name": "...", "latitude": ..., "longitude": ..., "filial_id": 1}
        ],
        "employees": [
            {"name": "...", "telegram_id": 100000001, "type": "employee",
             "schedule_name": "Standart jadval", "location_name": "..."}
        ],
        "schedules": [
            {"name": "Standart jadval", "start": "08:00", "end": "17:00",
             "filial_id": 1, "location_name": "..."}
        ]
    }
    """
    permission_classes    = [AllowAny]
    authentication_classes = []
    SECRET                = "dev_only"

    WEEKDAY_NAMES = {
        1: ("Dushanba",   "Monday"),
        2: ("Seshanba",   "Tuesday"),
        3: ("Chorshanba", "Wednesday"),
        4: ("Payshanba",  "Thursday"),
        5: ("Juma",       "Friday"),
        6: ("Shanba",     "Saturday"),
        7: ("Yakshanba",  "Sunday"),
    }

    def post(self, request):
        import random
        from datetime import date, timedelta, time as dt_time
        from apps.superadmin.models import Weekday, Filial

        if request.data.get("secret") != self.SECRET:
            return Response({"status": "FAIL", "reason": "Secret noto'g'ri"}, status=403)

        data             = request.data
        clear_existing   = data.get("clear_existing", True)
        date_from_str    = data.get("date_from", "2026-03-01")
        date_to_str      = data.get("date_to",   "2026-04-04")
        work_days        = data.get("work_days",  [1, 2, 3, 4, 5, 6])
        absent_prob      = float(data.get("absent_probability", 0.08))
        locations_data   = data.get("locations",  [])
        employees_data   = data.get("employees",  [])
        schedules_data   = data.get("schedules",  [])

        results = {
            "cleared":             {},
            "locations_created":   0,
            "employees_created":   0,
            "schedules_created":   0,
            "attendances_created": 0,
            "absent_days":         0,
            "errors":              [],
        }

        # ── 1. O'chirish ──────────────────────────────────────────
        if clear_existing:
            from .models import (
                Attendance, Schedule, ScheduleDay,
                WorkSchedule, ExtraSchedule, Employee, TelegramUser
            )
            results["cleared"]["attendances"]    = Attendance.objects.count()
            results["cleared"]["schedules"]      = Schedule.objects.count()
            results["cleared"]["work_schedules"] = WorkSchedule.objects.count()
            results["cleared"]["extra_schedules"]= ExtraSchedule.objects.count()
            results["cleared"]["employees"]      = Employee.objects.count()
            results["cleared"]["telegram_users"] = TelegramUser.objects.count()

            Attendance.objects.all().delete()
            ScheduleDay.objects.all().delete()
            Schedule.objects.all().delete()
            WorkSchedule.objects.all().delete()
            ExtraSchedule.objects.all().delete()
            Employee.objects.all().delete()
            TelegramUser.objects.all().delete()

        # ── 2. Weekday obyektlarini tayyorlash ────────────────────
        weekday_map = {}   # {1: Weekday, 2: Weekday, ...}
        for num, (uz_name, en_name) in self.WEEKDAY_NAMES.items():
            wd, _ = Weekday.objects.get_or_create(
                name=uz_name,
                defaults={"name_en": en_name}
            )
            weekday_map[num] = wd

        # ── 3. Locationlar ────────────────────────────────────────
        location_map = {}  # {name: Location}
        for loc_d in locations_data:
            try:
                filial = Filial.objects.get(id=loc_d["filial_id"]) if loc_d.get("filial_id") else None
                org    = filial.organization if filial else None
                loc, created = Location.objects.get_or_create(
                    name=loc_d["name"],
                    defaults={
                        "latitude":     loc_d.get("latitude"),
                        "longitude":    loc_d.get("longitude"),
                        "address":      loc_d.get("address", ""),
                        "filial":       filial,
                        "organization": org,
                    }
                )
                location_map[loc.name] = loc
                if created:
                    results["locations_created"] += 1
            except Exception as e:
                results["errors"].append(f"Location '{loc_d.get('name')}': {e}")

        # ── 4. Jadvallar (Schedule + ScheduleDay) ─────────────────
        schedule_map = {}  # {name: Schedule}
        for sch_d in schedules_data:
            try:
                filial   = Filial.objects.get(id=sch_d["filial_id"]) if sch_d.get("filial_id") else None
                loc_name = sch_d.get("location_name", "")
                loc      = location_map.get(loc_name)

                sch = Schedule.objects.create(
                    name=sch_d["name"],
                    filial=filial,
                    location=loc,
                )

                # Har ish kuni uchun ScheduleDay yaratamiz
                start_t = dt_time(*map(int, sch_d["start"].split(":")))
                end_t   = dt_time(*map(int, sch_d["end"].split(":")))
                for day_num in work_days:
                    wd = weekday_map.get(day_num)
                    if wd:
                        ScheduleDay.objects.create(
                            schedule=sch,
                            weekday=wd,
                            start=start_t,
                            end=end_t,
                        )

                schedule_map[sch.name] = sch
                results["schedules_created"] += 1
            except Exception as e:
                results["errors"].append(f"Schedule '{sch_d.get('name')}': {e}")

        # ── 5. Xodimlar ───────────────────────────────────────────
        employee_list = []
        for emp_d in employees_data:
            try:
                tg, _ = TelegramUser.objects.get_or_create(
                    user_id=emp_d["telegram_id"]
                )
                emp = Employee.objects.create(
                    name=emp_d["name"],
                    telegram_user_id=emp_d["telegram_id"],
                    employee_type=emp_d.get("type", "employee"),
                    filial=Filial.objects.get(id=emp_d["filial_id"]) if emp_d.get("filial_id") else None,
                )
                # Jadval biriktirish
                sch_name = emp_d.get("schedule_name")
                if sch_name and sch_name in schedule_map:
                    emp.schedules.add(schedule_map[sch_name])

                employee_list.append((emp, emp_d.get("location_name", "")))
                results["employees_created"] += 1
            except Exception as e:
                results["errors"].append(f"Employee '{emp_d.get('name')}': {e}")

        # ── 6. Sana oralig'ini hisoblash ──────────────────────────
        date_from = date.fromisoformat(date_from_str)
        date_to   = date.fromisoformat(date_to_str)
        work_days_set = set(work_days)   # python weekday: Mon=0...Sun=6
        # work_days bizda 1=Mon...7=Sun → python da 0=Mon...6=Sun
        python_work_days = {wd - 1 for wd in work_days_set}

        working_dates = []
        d = date_from
        while d <= date_to:
            if d.weekday() in python_work_days:
                working_dates.append(d)
            d += timedelta(days=1)

        # ── 7. Attendancelar ──────────────────────────────────────
        def random_time_near(base_hour, base_minute, variance=20):
            total = base_hour * 60 + base_minute + random.randint(-variance, variance)
            total = max(0, min(23 * 60 + 59, total))
            return dt_time(total // 60, total % 60)

        PROFILES = [
            (8, 0,  17, 0),
            (9, 0,  18, 0),
            (8, 30, 17, 30),
        ]

        for emp, loc_name in employee_list:
            loc = location_map.get(loc_name)
            if not loc:
                # xodim jadvalidagi locationni ishlatamiz
                sch = emp.schedules.first()
                loc = sch.location if sch else None
            if not loc:
                results["errors"].append(f"Location topilmadi: {emp.name}")
                continue

            in_h, in_m, out_h, out_m = random.choice(PROFILES)

            for day in working_dates:
                if random.random() < absent_prob:
                    results["absent_days"] += 1
                    continue

                check_in  = random_time_near(in_h, in_m)
                check_out = random_time_near(out_h, out_m)

                # check_out >= check_in + 7 soat
                ci_min = check_in.hour  * 60 + check_in.minute
                co_min = check_out.hour * 60 + check_out.minute
                if co_min < ci_min + 420:
                    co_min = ci_min + random.randint(420, 540)
                    co_min = min(co_min, 23 * 60 + 59)
                    check_out = dt_time(co_min // 60, co_min % 60)

                try:
                    Attendance.objects.create(
                        employee=emp,
                        date=day,
                        location=loc,
                        check_in=check_in,
                        check_out=check_out,
                        check_number=1,
                    )
                    results["attendances_created"] += 1
                except Exception as e:
                    results["errors"].append(f"Attendance {emp.name} {day}: {e}")

        results["working_days"] = len(working_dates)
        return Response({"status": "SUCCESS", **results}, status=200)