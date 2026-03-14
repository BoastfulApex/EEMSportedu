from rest_framework.response import Response
from rest_framework import serializers, generics
from rest_framework.renderers import JSONRenderer
from .models import Location, Attendance, Employee, WorkSchedule, ExtraSchedule, Schedule, ScheduleDay
from django.utils import timezone
from apps.superadmin.models import Administrator
from datetime import datetime
from data import config
import requests
import base64, io, os
import numpy as np
from PIL import Image

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    mp = None


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

def base64_to_pil(base64_image):
    if "," in base64_image:
        _, data = base64_image.split(",", 1)
    else:
        data = base64_image
    return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")


def detect_face(image_np):
    if not MEDIAPIPE_AVAILABLE:
        return True  # mediapipe yo'q bo'lsa, yuz bor deb hisoblaymiz
    mp_face = mp.solutions.face_detection
    with mp_face.FaceDetection(model_selection=0, min_detection_confidence=0.6) as det:
        results = det.process(image_np)
        return results.detections is not None and len(results.detections) > 0


def verify_face(employee, base64_image):
    if not employee.image:
        return False, "Xodim rasmi topilmadi"
    try:
        known_np = np.array(Image.open(employee.image.path).convert("RGB"))
    except Exception as e:
        return False, f"Xodim rasmi o'qilmadi: {e}"

    if not detect_face(known_np):
        return False, "Xodim rasmida yuz topilmadi"

    try:
        unknown_pil = base64_to_pil(base64_image)
        unknown_np = np.array(unknown_pil)
    except Exception as e:
        return False, f"Yuklangan rasm o'qilmadi: {e}"

    if not detect_face(unknown_np):
        return False, "Yuklangan rasmda yuz topilmadi"

    # Piksel o'xshashlik (cosine similarity)
    size = (100, 100)
    known_small = np.array(Image.fromarray(known_np).resize(size)).flatten().astype(float)
    unknown_small = np.array(unknown_pil.resize(size)).flatten().astype(float)
    norm = np.linalg.norm(known_small) * np.linalg.norm(unknown_small)
    similarity = np.dot(known_small, unknown_small) / norm if norm > 0 else 0

    if similarity >= 0.85:
        return True
    return False, f"Yuz mos kelmadi (o'xshashlik: {similarity:.2f})"


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
    serializer_class = CheckRequestSerializer
    renderer_classes = [JSONRenderer]

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
            employee = Employee.objects.get(user_id=user_id)
        except Employee.DoesNotExist:
            return Response({"status": "FAIL", "reason": "Foydalanuvchi topilmadi"}, status=404)

        # Yuz tekshirish
        if employee.image:
            face_result = verify_face(employee, image_base64)
            if face_result is not True:
                reason = face_result[1] if isinstance(face_result, tuple) else "FaceID mos kelmadi"
                return Response({"status": "FAIL", "reason": reason}, status=403)

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
                send_telegram_message(employee.user_id, msg)

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
