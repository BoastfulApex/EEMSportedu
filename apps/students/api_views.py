"""
Tinglovchi davomat API
=====================
POST /students/api/check/

Request JSON:
  user_id   — Telegram user ID
  type      — "check_in" | "check_out"
  latitude  — GPS kenglik
  longitude — GPS uzunlik
  image     — base64 kamera rasmi

Tekshiruv tartibi:
  1. Student topish (telegram_id bo'yicha)
  2. Yuz tekshirish — DeepFace (student.face_image bilan solishtirish)
  3. Lokatsiya tekshirish — GroupLesson.location yoki Building koordinatlari
  4. Davomat yozish — kechikish/erta ketish Smena asosida
"""

import os
import io
import base64
import tempfile
from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import serializers, generics
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import AllowAny
from PIL import Image

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

PARA_DURATION_MINUTES = 80


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

def base64_to_pil(base64_str):
    if "," in base64_str:
        _, data = base64_str.split(",", 1)
    else:
        data = base64_str
    return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")


def get_distance_meters(lat1, lon1, lat2, lon2):
    from geopy.distance import geodesic
    return geodesic((lat1, lon1), (lat2, lon2)).meters


def verify_student_face(student, base64_image):
    """
    Tinglovchi yuzini saqlangan rasm bilan face_recognition orqali solishtiradi.
    face_image yo'q bo'lsa → o'tkazib yuboradi.
    """
    if not student.face_image:
        return True

    if not FACE_RECOGNITION_AVAILABLE:
        return True

    try:
        import numpy as np
        unknown_pil = base64_to_pil(base64_image)
        unknown_arr = np.array(unknown_pil)

        known_arr = face_recognition.load_image_file(student.face_image.path)
        known_encodings = face_recognition.face_encodings(known_arr)
        if not known_encodings:
            return True  # Bazadagi rasmda yuz topilmadi

        unknown_encodings = face_recognition.face_encodings(unknown_arr)
        if not unknown_encodings:
            return False, "Rasmda yuz aniqlanmadi"

        match = face_recognition.compare_faces(
            [known_encodings[0]], unknown_encodings[0], tolerance=0.5
        )
        if match[0]:
            return True
        distance = round(face_recognition.face_distance([known_encodings[0]], unknown_encodings[0])[0], 2)
        return False, f"Yuz mos kelmadi (masofa: {distance})"

    except Exception:
        return True  # Xato bo'lsa — o'tkazib yuborish


def find_student_location(student, latitude, longitude, today):
    """
    Tinglovchi guruhining BUGUNGI sanaga belgilangan lokatsiyasini topadi
    va GPS koordinatlarini FAQAT shu lokatsiyaga nisbatan tekshiradi.

    Tekshiruv tartibi:
      1. GroupLesson (muayyan kun uchun alohida belgilangan) → lesson.location
      2. GroupSchedule (haftalik jadval) → building — bugungi hafta kuni va sana oralig'iga mos

    Agar bugun uchun lokatsiya topilmasa → (None, False, group, None, None) + sabab
    Agar topilsa lekin student 150m dan uzoqda → (loc_name, False, group, lesson, dist)
    Agar topilsa va yaqin → (loc_name, True, group, lesson, dist)

    Qaytaradi: (location_name, ok: bool, group, lesson, distance_meters)
    """
    from apps.students.models import GroupLesson, GroupSchedule
    from django.db.models import Q

    # Tinglovchining guruhini aniqlash
    group = student.groups.first()
    if not group:
        return None, False, None, None, None

    # ── 1. GroupLesson — bugungi kun uchun maxsus belgilangan ──
    lesson = GroupLesson.objects.filter(
        group=group, date=today
    ).select_related('location', 'smena').first()

    if lesson and lesson.location:
        loc = lesson.location
        loc_name = loc.name or "Dars lokatsiyasi"
        if loc.latitude and loc.longitude:
            dist = get_distance_meters(latitude, longitude, loc.latitude, loc.longitude)
            ok = dist < 150
            return loc_name, ok, group, lesson, int(dist)
        else:
            # Koordinatlar kiritilmagan — lokatsiya tekshiruvini o'tkazib yuborish
            return loc_name, True, group, lesson, None

    # ── 2. GroupSchedule — haftalik jadval bo'yicha bino ──────
    uz_weekdays = {
        0: 'Dushanba', 1: 'Seshanba', 2: 'Chorshanba',
        3: 'Payshanba', 4: 'Juma', 5: 'Shanba', 6: 'Yakshanba',
    }
    weekday_name = uz_weekdays.get(today.weekday())
    schedule = GroupSchedule.objects.filter(
        group=group,
        is_active=True,
        weekdays__name=weekday_name,
    ).filter(
        Q(date_from__isnull=True) | Q(date_from__lte=today),
        Q(date_to__isnull=True)   | Q(date_to__gte=today),
    ).select_related('building').first()

    if schedule and schedule.building:
        b = schedule.building
        loc_name = b.name or "Dars binosi"
        if b.latitude and b.longitude:
            dist = get_distance_meters(latitude, longitude, b.latitude, b.longitude)
            ok = dist < 150
            return loc_name, ok, group, None, int(dist)
        else:
            # Koordinatlar kiritilmagan — o'tkazib yuborish
            return loc_name, True, group, None, None

    # Bugun uchun lokatsiya belgilanmagan
    return None, False, group, None, None


def get_lesson_schedule_times(group, today, lesson=None):
    """
    Bugungi dars boshlanish va tugash vaqtlarini qaytaradi.
    Qaytaradi: (expected_start, expected_end) yoki (None, None)
    """
    from apps.students.models import GroupSchedule

    # Faqat GroupLesson + Smena belgilangan bo'lsa vaqtlarni qaytaradi
    if lesson and lesson.smena:
        smena = lesson.smena
        start = smena.para1_start
        last_para = smena.para3_start or smena.para2_start or smena.para1_start
        end = (datetime.combine(today, last_para) + timedelta(minutes=PARA_DURATION_MINUTES)).time()
        return start, end

    return None, None


# ============================================================
# SERIALIZER
# ============================================================

class StudentCheckSerializer(serializers.Serializer):
    user_id   = serializers.IntegerField()
    type      = serializers.ChoiceField(choices=['check_in', 'check_out'])
    latitude  = serializers.FloatField()
    longitude = serializers.FloatField()
    image     = serializers.CharField(required=False, allow_blank=True, default='')


# ============================================================
# API VIEW
# ============================================================

class StudentCheckAPIView(generics.ListCreateAPIView):
    serializer_class       = StudentCheckSerializer
    renderer_classes       = [JSONRenderer]
    authentication_classes = []   # CSRF tekshiruvi o'chiriladi
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

        # ── 1. Tinglovchini topish ───────────────────────────
        from apps.students.models import Student, StudentAttendance
        try:
            student = Student.objects.select_related('filial__organization').get(
                telegram_id=user_id
            )
        except Student.DoesNotExist:
            return Response({"status": "FAIL", "reason": "Tinglovchi topilmadi"}, status=404)

        # ── 3. Lokatsiya tekshirish ──────────────────────────
        today = timezone.localdate()
        now_time = timezone.localtime().time()

        loc_name, loc_ok, group, lesson, distance_m = find_student_location(
            student, latitude, longitude, today
        )

        if not group:
            return Response({
                "status": "FAIL",
                "reason": "Guruhingiz topilmadi. Administrator bilan bog'laning."
            }, status=403)

        if not loc_ok:
            if loc_name is None:
                reason = "Bugun uchun dars lokatsiyasi belgilanmagan. Administrator bilan bog'laning."
            else:
                dist_txt = f" (siz {distance_m} m uzoqdasiz)" if distance_m is not None else ""
                reason = f"Siz «{loc_name}» lokatsiyasiga yaqin emassiz{dist_txt}."
            return Response({"status": "FAIL", "reason": reason}, status=403)

        # ── 4. Jadval vaqtlarini aniqlash ────────────────────
        expected_start, expected_end = get_lesson_schedule_times(group, today, lesson)

        # ── 5. Davomat yozish ────────────────────────────────
        if check_type == 'check_in':
            # Yuz tekshirish — faqat DeepFace o'rnatilgan va rasm yuborilgan bo'lsa
            if FACE_RECOGNITION_AVAILABLE and image_base64:
                face_result = verify_student_face(student, image_base64)
                if face_result is not True:
                    reason = face_result[1] if isinstance(face_result, tuple) else "FaceID mos kelmadi"
                    return Response({"status": "FAIL", "reason": reason}, status=403)

            existing = StudentAttendance.objects.filter(
                student=student, group=group, date=today, check_in__isnull=False
            ).first()
            if existing:
                return Response({
                    "status": "FAIL",
                    "reason": f"Siz bugun allaqachon {existing.check_in.strftime('%H:%M')} da kirgansiz."
                }, status=400)

            # Kechikishni hisoblash
            late_minutes = 0
            status_val = 'present'
            if expected_start:
                now_dt = datetime.combine(today, now_time)
                exp_dt = datetime.combine(today, expected_start)
                if now_dt > exp_dt:
                    late_minutes = int((now_dt - exp_dt).total_seconds() / 60)
                    status_val = 'late'

            attendance, created = StudentAttendance.objects.get_or_create(
                student=student, group=group, date=today,
                defaults={
                    'check_in': now_time,
                    'status': status_val,
                    'late_minutes': late_minutes,
                    'verified_by_face': True,
                }
            )
            if not created:
                attendance.check_in = now_time
                attendance.status = status_val
                attendance.late_minutes = late_minutes
                attendance.verified_by_face = True
                attendance.save(update_fields=['check_in', 'status', 'late_minutes', 'verified_by_face'])

            result_data = {
                "status": "SUCCESS",
                "type": "check_in",
                "time": now_time.strftime('%H:%M'),
                "location": loc_name,
                "distance_meters": distance_m,
                "late_minutes": late_minutes,
                "expected_start": expected_start.strftime('%H:%M') if expected_start else None,
            }
            return Response(result_data, status=200)

        else:  # check_out
            attendance = StudentAttendance.objects.filter(
                student=student, group=group, date=today, check_in__isnull=False
            ).first()
            if not attendance:
                return Response({
                    "status": "FAIL",
                    "reason": "Avval kirish belgisini qo'ying."
                }, status=400)

            # Erta ketishni hisoblash (oxirgi chiqish vaqti saqlanadi)
            early_leave_minutes = 0
            if expected_end:
                now_dt = datetime.combine(today, now_time)
                exp_end_dt = datetime.combine(today, expected_end)
                if now_dt < exp_end_dt:
                    early_leave_minutes = int((exp_end_dt - now_dt).total_seconds() / 60)

            attendance.check_out = now_time
            attendance.early_leave_minutes = early_leave_minutes
            attendance.save(update_fields=['check_out', 'early_leave_minutes'])

            result_data = {
                "status": "SUCCESS",
                "type": "check_out",
                "time": now_time.strftime('%H:%M'),
                "location": loc_name,
                "distance_meters": distance_m,
                "early_leave_minutes": early_leave_minutes,
                "expected_end": expected_end.strftime('%H:%M') if expected_end else None,
            }
            return Response(result_data, status=200)
