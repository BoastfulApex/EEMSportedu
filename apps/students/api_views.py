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


def save_event_photo(image_base64, filename_prefix):
    """base64 rasmni ContentFile ga aylantiradi — ImageField.save() bilan ishlatish uchun."""
    if not image_base64:
        return None
    try:
        from django.core.files.base import ContentFile
        import uuid as _uuid
        raw = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
        img_bytes = base64.b64decode(raw)
        filename = f"{filename_prefix}_{_uuid.uuid4().hex[:10]}.jpg"
        return ContentFile(img_bytes, name=filename)
    except Exception:
        return None


def save_event_photo_from_bytes(img_bytes, filename_prefix):
    """Allaqachon decode qilingan baytlardan ContentFile yaratadi (qayta decode qilmasdan)."""
    if not img_bytes:
        return None
    from django.core.files.base import ContentFile
    import uuid as _uuid
    filename = f"{filename_prefix}_{_uuid.uuid4().hex[:10]}.jpg"
    return ContentFile(img_bytes, name=filename)


def get_distance_meters(lat1, lon1, lat2, lon2):
    from geopy.distance import geodesic
    return geodesic((lat1, lon1), (lat2, lon2)).meters


def verify_student_face(student, base64_image):
    """
    Tinglovchi yuzini saqlangan rasm/encoding bilan face_recognition orqali solishtiradi.
    face_image yo'q bo'lsa → o'tkazib yuboradi.

    Tezlashtirish: student.face_encoding mavjud bo'lsa — diskdan rasm o'qilmaydi (~5ms).
    Fallback: face_encoding yo'q bo'lsa — diskdan rasm o'qib encoding hisoblanadi (~3s).
    """
    if not student.face_image:
        return True

    if not FACE_RECOGNITION_AVAILABLE:
        return True

    try:
        import json
        import numpy as np
        unknown_pil = base64_to_pil(base64_image)
        unknown_arr = np.array(unknown_pil)

        unknown_encodings = face_recognition.face_encodings(unknown_arr)
        if not unknown_encodings:
            return False, "Rasmda yuz aniqlanmadi"

        # ── Cached encoding — diskdan o'qmasdan (tez) ─────────
        known_enc = None
        if student.face_encoding:
            try:
                known_enc = np.array(json.loads(student.face_encoding), dtype=np.float64)
            except Exception:
                known_enc = None  # buzilgan bo'lsa → fallback

        # ── Fallback: diskdan o'qish (encoding yo'q yoki buzilgan) ─
        if known_enc is None:
            known_arr = face_recognition.load_image_file(student.face_image.path)
            known_encodings = face_recognition.face_encodings(known_arr)
            if not known_encodings:
                return True  # Bazadagi rasmda yuz topilmadi
            known_enc = known_encodings[0]

        # tolerance=0.65 — 1:1 tasdiq uchun yumshoqroq
        match = face_recognition.compare_faces(
            [known_enc], unknown_encodings[0], tolerance=0.65
        )
        if match[0]:
            return True
        distance = round(face_recognition.face_distance([known_enc], unknown_encodings[0])[0], 2)
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
        slots = smena.get_slots()
        if not slots:
            return None, None
        start = slots[0].start
        last_slot = slots[-1]
        # Tugash vaqti: slot.end bo'lsa ishlatamiz, bo'lmasa start + PARA_DURATION
        if last_slot.end:
            end = last_slot.end
        else:
            end = (datetime.combine(today, last_slot.start) + timedelta(minutes=PARA_DURATION_MINUTES)).time()
        return start, end

    return None, None


def _compute_student_late(check_in_time, today, lesson, expected_start):
    """Berilgan kirish vaqti uchun kechikish (daqiqa) va status ni qaytaradi."""
    late_minutes = 0
    status_val   = 'present'
    now_dt = datetime.combine(today, check_in_time)
    if lesson and lesson.smena:
        slots = lesson.smena.get_slots()
        target_slot = None
        for slot in slots:
            slot_start = datetime.combine(today, slot.start)
            slot_end = (
                datetime.combine(today, slot.end) if slot.end
                else slot_start + timedelta(minutes=PARA_DURATION_MINUTES)
            )
            if now_dt <= slot_end:
                target_slot = slot
                break
        if target_slot is None and slots:
            target_slot = slots[-1]
        if target_slot:
            exp_dt = datetime.combine(today, target_slot.start)
            if now_dt > exp_dt:
                late_minutes = int((now_dt - exp_dt).total_seconds() / 60)
                status_val   = 'late'
    elif expected_start:
        exp_dt = datetime.combine(today, expected_start)
        if now_dt > exp_dt:
            late_minutes = int((now_dt - exp_dt).total_seconds() / 60)
            status_val   = 'late'
    return late_minutes, status_val


def _compute_student_early_leave(check_out_time, today, lesson, expected_end):
    """Berilgan chiqish vaqti uchun erta ketish (daqiqa) ni qaytaradi."""
    early = 0
    now_dt = datetime.combine(today, check_out_time)
    if lesson and lesson.smena:
        slots = lesson.smena.get_slots()
        if slots:
            last = slots[-1]
            last_end = (
                datetime.combine(today, last.end) if last.end
                else datetime.combine(today, last.start) + timedelta(minutes=PARA_DURATION_MINUTES)
            )
            if now_dt < last_end:
                early = int((last_end - now_dt).total_seconds() / 60)
    elif expected_end:
        exp_end_dt = datetime.combine(today, expected_end)
        if now_dt < exp_end_dt:
            early = int((exp_end_dt - now_dt).total_seconds() / 60)
    return early


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

            # Kunga bitta xulosa qatori — takror kirish bloklanmaydi.
            # Eng ERTA kirish saqlanadi, kechikish shu vaqtdan qayta hisoblanadi.
            attendance, created = StudentAttendance.objects.get_or_create(
                student=student, group=group, date=today,
                defaults={'check_in': now_time, 'verified_by_face': True},
            )
            if attendance.check_in is None or now_time < attendance.check_in:
                attendance.check_in = now_time
            late_minutes, status_val = _compute_student_late(
                attendance.check_in, today, lesson, expected_start
            )
            attendance.status = status_val
            attendance.late_minutes = late_minutes
            attendance.verified_by_face = True
            attendance.save(update_fields=['check_in', 'status', 'late_minutes', 'verified_by_face'])

            # Face ID muvaffaqiyatli o'tdi → is_registered = True
            if not student.is_registered:
                student.is_registered = True
                student.save(update_fields=['is_registered'])

            # Alohida hodisa yozuvi — rasm va lokatsiya bilan
            from apps.main.models import AttendanceEvent
            event = AttendanceEvent.objects.create(
                person_type='student', student=student, student_attendance=attendance,
                event_type='check_in', date=today, time=now_time,
                location_name=loc_name, latitude=latitude, longitude=longitude,
                distance_meters=distance_m, verified_by='self',
            )
            photo_file = save_event_photo(image_base64, f"stu{student.id}_in")
            if photo_file:
                event.photo.save(photo_file.name, photo_file, save=True)

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
            # Kirishsiz ham chiqish qayd qilinadi. Eng KECH chiqish saqlanadi,
            # erta ketish shu vaqtdan qayta hisoblanadi.
            attendance, _ = StudentAttendance.objects.get_or_create(
                student=student, group=group, date=today,
            )
            if attendance.check_out is None or now_time > attendance.check_out:
                attendance.check_out = now_time
            early_leave_minutes = _compute_student_early_leave(
                attendance.check_out, today, lesson, expected_end
            )
            attendance.early_leave_minutes = early_leave_minutes
            attendance.save(update_fields=['check_out', 'early_leave_minutes'])

            # Alohida hodisa yozuvi — rasm va lokatsiya bilan
            from apps.main.models import AttendanceEvent
            event = AttendanceEvent.objects.create(
                person_type='student', student=student, student_attendance=attendance,
                event_type='check_out', date=today, time=now_time,
                location_name=loc_name, latitude=latitude, longitude=longitude,
                distance_meters=distance_m, verified_by='self',
            )
            photo_file = save_event_photo(image_base64, f"stu{student.id}_out")
            if photo_file:
                event.photo.save(photo_file.name, photo_file, save=True)

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


# ============================================================
# EDU ADMIN — TINGLOVCHI QIDIRISH
# ============================================================

class EduAdminStudentsAPIView(generics.GenericAPIView):
    """
    GET /students/edu-admin/api/students/?q=<query>&admin_id=<telegram_id>

    O'quv admin uchun tinglovchilarni qidirish.
    Bugungi davomat holati ham qaytariladi.
    """
    renderer_classes       = [JSONRenderer]
    authentication_classes = []
    permission_classes     = [AllowAny]

    def get(self, request):
        from apps.superadmin.models import Administrator
        from apps.students.models import Student, StudentAttendance
        from django.db.models import Q

        # Admin ID tekshirish
        try:
            admin_telegram_id = int(request.GET.get('admin_id', ''))
        except (ValueError, TypeError):
            return Response({"error": "admin_id kerak"}, status=400)

        q = request.GET.get('q', '').strip()
        if not q:
            return Response({"students": []})

        # Admin mavjudligini va rolini tekshirish
        try:
            admin = Administrator.objects.select_related('filial').get(
                telegram_id=admin_telegram_id,
                role__in=['edu_admin', 'org_admin', 'filial_admin']
            )
        except Administrator.DoesNotExist:
            return Response({"error": "Admin topilmadi yoki ruxsat yo'q"}, status=403)

        # Tinglovchilarni qidirish
        qs = Student.objects.all()
        if admin.filial:
            qs = qs.filter(filial=admin.filial)

        try:
            sid = int(q)
            qs = qs.filter(Q(full_name__icontains=q) | Q(id=sid))
        except ValueError:
            qs = qs.filter(full_name__icontains=q)

        qs = qs[:30]

        # Bugungi davomat
        today = timezone.localdate()
        att_map = {
            att.student_id: att
            for att in StudentAttendance.objects.filter(
                student__in=qs, date=today
            )
        }

        students_data = []
        for s in qs:
            att = att_map.get(s.id)
            students_data.append({
                'id':         s.id,
                'full_name':  s.full_name,
                'phone':      s.phone or '',
                'check_in':   att.check_in.strftime('%H:%M')  if att and att.check_in  else None,
                'check_out':  att.check_out.strftime('%H:%M') if att and att.check_out else None,
            })

        return Response({'students': students_data})


# ============================================================
# EDU ADMIN — TINGLOVCHI DAVOMATINI QAYD QILISH
# ============================================================

class EduAdminCheckSerializer(serializers.Serializer):
    admin_telegram_id = serializers.IntegerField()
    latitude          = serializers.FloatField()
    longitude         = serializers.FloatField()
    image             = serializers.CharField()
    student_id        = serializers.IntegerField(required=False, allow_null=True)
    action            = serializers.ChoiceField(
        choices=['check_in', 'check_out'],
        required=False,
        default='check_in'
    )


class EduAdminCheckAPIView(generics.CreateAPIView):
    """
    POST /students/edu-admin/api/check/

    O'quv admin WebApp orqali tinglovchi davomatini qayd qilish.

    Ish tartibi:
      1. Admin tekshirish
      2. Admin filialidagi yuz rasmi bor tinglovchilarni olish
      3. Rasmni diskka saqlash
      4. Yuz tanish (face_recognition yoki mediapipe)
      5. Lokatsiya tekshirish (150 m radius)
      6. Bugungi davomatga qarab check_in yoki check_out avtomatik aniqlash
      7. Davomat yozish
    """
    serializer_class       = EduAdminCheckSerializer
    renderer_classes       = [JSONRenderer]
    authentication_classes = []
    permission_classes     = [AllowAny]

    def create(self, request):
        import os
        import tempfile
        from utils.face_recognition_util import recognize_student

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        admin_telegram_id  = data['admin_telegram_id']
        latitude           = data['latitude']
        longitude          = data['longitude']
        image_base64       = data['image']
        selected_student_id = data.get('student_id')   # bot orqali tanlangan tinglovchi

        # ── 1. Admin tekshirish (filial filtr uchun) ────────────
        from apps.superadmin.models import Administrator
        from apps.students.models import Student, StudentAttendance

        admin = Administrator.objects.select_related('filial').filter(
            telegram_id=admin_telegram_id,
            role__in=['edu_admin', 'org_admin', 'filial_admin']
        ).first()

        # ── 2. Tinglovchi(lar)ni olish ───────────────────────
        if selected_student_id:
            # student_id berilgan — faqat o'sha 1 ta tinglovchi, 1:1 tekshiruv
            qs = Student.objects.filter(
                id=selected_student_id,
                face_image__isnull=False,
            )
        else:
            # Admin uchun — filialdagi barcha tinglovchilar qidiruvi
            qs = Student.objects.filter(face_image__isnull=False)
            if admin and admin.filial:
                qs = qs.filter(filial=admin.filial)

        students_data = []
        for s in qs.only('id', 'full_name', 'phone', 'face_image', 'face_encoding'):
            try:
                path = s.face_image.path if s.face_image else None
                # face_encoding bo'lsa — rasm yo'lini tekshirmasdan ham qo'shish mumkin
                has_encoding = bool(s.face_encoding)
                has_image    = bool(path and os.path.exists(path))
                if has_encoding or has_image:
                    students_data.append({
                        'id':            s.id,
                        'full_name':     s.full_name,
                        'phone':         s.phone or '',
                        'image_path':    path or '',
                        'face_encoding': s.face_encoding or '',
                    })
            except Exception:
                pass

        if not students_data:
            reason = (
                "Bu tinglovchining yuz rasmi tizimda topilmadi."
                if selected_student_id else
                "Tizimda yuz rasmi yuklangan tinglovchi topilmadi."
            )
            return Response({"status": "FAIL", "reason": reason}, status=404)

        # ── 3. Rasmni vaqtinchalik faylga saqlash ────────────
        tmp_path = None
        try:
            if "," in image_base64:
                _, raw = image_base64.split(",", 1)
            else:
                raw = image_base64
            import base64 as _b64
            img_bytes = _b64.b64decode(raw)

            fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="edu_admin_")
            with os.fdopen(fd, "wb") as f:
                f.write(img_bytes)
        except Exception as ex:
            return Response({"status": "FAIL", "reason": f"Rasm o'qib bo'lmadi: {ex}"}, status=400)

        # ── 4. Yuz tanish ─────────────────────────────────────
        # student_id berilsa — 1:1 tasdiq (yumshoqroq threshold)
        try:
            result = recognize_student(
                tmp_path,
                students_data,
                top_n=1,
                one_to_one=bool(selected_student_id),
            )
        except Exception as ex:
            return Response({"status": "FAIL", "reason": f"Yuz tanish xatosi: {ex}"}, status=500)
        finally:
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

        if not result.get('found') or not result.get('best_match'):
            if not result.get('candidates'):
                reason = "Rasmda yuz aniqlanmadi. Aniqroq rasm olishga harakat qiling."
            elif selected_student_id:
                reason = "Yuz mos kelmadi. Bu tanlangan tinglovchi emas yoki rasm sifati past."
            else:
                reason = "Tinglovchi tanib olunmadi. Yuz aniqroq ko'rinishi kerak."
            return Response({"status": "FAIL", "reason": reason}, status=404)

        student_id = result['best_match']['id']

        # ── 5. Tinglovchini DB dan topish ─────────────────────
        try:
            student_qs = Student.objects.select_related('filial__organization')
            if admin and admin.filial:
                student_qs = student_qs.filter(filial=admin.filial)
            student = student_qs.get(id=student_id)
        except Student.DoesNotExist:
            return Response({"status": "FAIL", "reason": "Tinglovchi topilmadi"}, status=404)

        today    = timezone.localdate()
        now_time = timezone.localtime().time()

        # ── 6. Lokatsiya tekshirish ───────────────────────────
        loc_name, loc_ok, group, lesson, distance_m = find_student_location(
            student, latitude, longitude, today
        )

        if not group:
            return Response({
                "status": "FAIL",
                "reason": f"✅ {student.full_name} aniqlandi, lekin hech qanday guruhga biriktirilmagan."
            }, status=403)

        if not loc_ok:
            if loc_name is None:
                reason = f"✅ {student.full_name} aniqlandi.\n⚠️ Bugun uchun dars lokatsiyasi belgilanmagan."
            else:
                dist_txt = f" ({distance_m} m uzoqda)" if distance_m is not None else ""
                reason = f"✅ {student.full_name} aniqlandi.\n⚠️ Dars lokatsiyasiga yaqin emassiz: «{loc_name}»{dist_txt}."
            return Response({"status": "FAIL", "reason": reason}, status=403)

        # ── 7. Jadval vaqtlari ────────────────────────────────
        expected_start, expected_end = get_lesson_schedule_times(group, today, lesson)

        # ── 8. Davomat holati → action (check_in / check_out) ──
        action = data.get('action', 'check_in')

        if action == 'check_out':
            # ── check_out ──────────────────────────────────
            # Kirishsiz ham chiqish qayd qilinadi. Eng KECH chiqish saqlanadi,
            # erta ketish shu vaqtdan qayta hisoblanadi.
            attendance, _ = StudentAttendance.objects.get_or_create(
                student=student, group=group, date=today,
            )
            if attendance.check_out is None or now_time > attendance.check_out:
                attendance.check_out = now_time
            early_leave_minutes = _compute_student_early_leave(
                attendance.check_out, today, lesson, expected_end
            )
            attendance.early_leave_minutes = early_leave_minutes
            attendance.save(update_fields=['check_out', 'early_leave_minutes'])

            # Alohida hodisa yozuvi — rasm (allaqachon decode qilingan) va lokatsiya bilan
            from apps.main.models import AttendanceEvent
            event = AttendanceEvent.objects.create(
                person_type='student', student=student, student_attendance=attendance,
                event_type='check_out', date=today, time=now_time,
                location_name=loc_name, latitude=latitude, longitude=longitude,
                distance_meters=distance_m, verified_by='edu_admin',
                face_match_score=result['best_match'].get('score'),
            )
            photo_file = save_event_photo_from_bytes(img_bytes, f"stu{student.id}_out_edu")
            if photo_file:
                event.photo.save(photo_file.name, photo_file, save=True)

            return Response({
                "status":               "SUCCESS",
                "type":                 "check_out",
                "student_name":         student.full_name,
                "time":                 now_time.strftime('%H:%M'),
                "check_in":             attendance.check_in.strftime('%H:%M') if attendance.check_in else None,
                "location":             loc_name,
                "distance_meters":      distance_m,
                "early_leave_minutes":  early_leave_minutes,
                "expected_end":         expected_end.strftime('%H:%M') if expected_end else None,
            }, status=200)

        else:
            # ── check_in ───────────────────────────────────
            # Takror kirish bloklanmaydi. Eng ERTA kirish saqlanadi,
            # kechikish shu vaqtdan qayta hisoblanadi.
            attendance, created = StudentAttendance.objects.get_or_create(
                student=student, group=group, date=today,
                defaults={'check_in': now_time, 'verified_by_face': True},
            )
            if attendance.check_in is None or now_time < attendance.check_in:
                attendance.check_in = now_time
            late_minutes, status_val = _compute_student_late(
                attendance.check_in, today, lesson, expected_start
            )
            attendance.status           = status_val
            attendance.late_minutes     = late_minutes
            attendance.verified_by_face = True
            attendance.save(update_fields=['check_in', 'status', 'late_minutes', 'verified_by_face'])

            # Face ID muvaffaqiyatli o'tdi → is_registered = True
            if not student.is_registered:
                student.is_registered = True
                student.save(update_fields=['is_registered'])

            # Alohida hodisa yozuvi — rasm (allaqachon decode qilingan) va lokatsiya bilan
            from apps.main.models import AttendanceEvent
            event = AttendanceEvent.objects.create(
                person_type='student', student=student, student_attendance=attendance,
                event_type='check_in', date=today, time=now_time,
                location_name=loc_name, latitude=latitude, longitude=longitude,
                distance_meters=distance_m, verified_by='edu_admin',
                face_match_score=result['best_match'].get('score'),
            )
            photo_file = save_event_photo_from_bytes(img_bytes, f"stu{student.id}_in_edu")
            if photo_file:
                event.photo.save(photo_file.name, photo_file, save=True)

            return Response({
                "status":         "SUCCESS",
                "type":           "check_in",
                "student_name":   student.full_name,
                "time":           now_time.strftime('%H:%M'),
                "location":       loc_name,
                "distance_meters": distance_m,
                "late_minutes":   late_minutes,
                "expected_start": expected_start.strftime('%H:%M') if expected_start else None,
            }, status=200)
