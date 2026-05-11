import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from apps.superadmin.models import Organization, Filial, Building, Administrator, Weekday


class TelegramUser(models.Model):
    user_id = models.BigIntegerField(unique=True, null=True, blank=True)
    username = models.CharField(max_length=100, null=True, blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username if self.username else f"User {self.user_id}"

    class Meta:
        verbose_name = "Telegram Foydalanuvchi"
        verbose_name_plural = "Telegram Foydalanuvchilar"


class Location(models.Model):
    """Filial joylashuvi — xodimlar davomati uchun"""
    filial = models.ForeignKey(Filial, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name if self.name else "Unnamed Location"

    class Meta:
        verbose_name = "Manzil"
        verbose_name_plural = "Manzillar"


class Employee(models.Model):
    EMPLOYEE_TYPE_CHOICES = [
        ('employee', 'Xodim'),
        ('teacher', "O'qituvchi"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employee'
    )
    name = models.CharField(max_length=200, blank=True, null=True)
    employee_type = models.CharField(max_length=20, choices=EMPLOYEE_TYPE_CHOICES, default='employee')
    telegram_user_id = models.BigIntegerField(null=True, blank=True, unique=True)
    filial = models.ForeignKey(Filial, on_delete=models.CASCADE, null=True, blank=True)
    schedules = models.ManyToManyField(
        'Schedule',
        blank=True,
        related_name='employees',
        verbose_name="Jadvallar"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(null=True, blank=True)

    @property
    def imageURL(self):
        try:
            url = self.image.url
        except Exception:
            url = ''
        return url

    def __str__(self):
        return self.name if self.name else "Unnamed Employee"

    class Meta:
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar"


class Schedule(models.Model):
    """
    Tayyor jadval shabloni — xodimga bog'liq emas.
    Admin oldin jadval yaratadi (hafta kunlari, vaqt, lokatsiya),
    keyin xodimga shu jadval biriktiriladi.
    """
    name = models.CharField(max_length=200, verbose_name="Jadval nomi")
    filial = models.ForeignKey(
        'superadmin.Filial',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='schedules',
        verbose_name="Filial"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='schedules',
        verbose_name="Lokatsiya"
    )
    lunch_start = models.TimeField(null=True, blank=True, verbose_name="Tushlik boshlanishi")
    lunch_end   = models.TimeField(null=True, blank=True, verbose_name="Tushlik tugashi")

    def __str__(self):
        return self.name

    def get_day(self, weekday):
        """Berilgan hafta kuni uchun ScheduleDay qaytaradi (yoki None)"""
        return self.days.filter(weekday=weekday).first()

    class Meta:
        verbose_name = "Jadval"
        verbose_name_plural = "Jadvallar"


class ScheduleDay(models.Model):
    """Jadvalning har bir hafta kuniga kelish/ketish vaqtlari"""
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='days',
        verbose_name="Jadval"
    )
    weekday = models.ForeignKey(
        Weekday,
        on_delete=models.CASCADE,
        related_name='schedule_days',
        verbose_name="Hafta kuni"
    )
    start = models.TimeField(verbose_name="Kelish vaqti")
    end = models.TimeField(verbose_name="Ketish vaqti")

    def __str__(self):
        return f"{self.schedule.name} — {self.weekday.name} ({self.start}-{self.end})"

    class Meta:
        unique_together = ('schedule', 'weekday')
        verbose_name = "Jadval kuni"
        verbose_name_plural = "Jadval kunlari"


class WorkSchedule(models.Model):
    weekday = models.ManyToManyField(Weekday, related_name='work_schedules')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='work_schedules', null=True, blank=True)
    admin = models.ForeignKey(Administrator, on_delete=models.SET_NULL, related_name='work_schedules', null=True, blank=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='work_schedules'
    )
    start = models.TimeField()
    end = models.TimeField()

    def __str__(self):
        return self.employee.name if self.employee else 'Unnamed'

    class Meta:
        verbose_name = "Ish jadvali (eski)"
        verbose_name_plural = "Ish jadvallari (eski)"


class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    check_number = models.IntegerField(null=True, default=0)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attendances'
    )

    class Meta:
        unique_together = ('employee', 'date', 'location')
        verbose_name = "Kirish Chiqish"
        verbose_name_plural = "Kirish Chiqishlar"

    def __str__(self):
        return f"{self.employee.name} - {self.date}"


class ExtraSchedule(models.Model):
    """
    ESKI model — yangi Schedule + Employee.schedules M2M bilan almashtirildi.
    Migratsiya uchun saqlab qolindi.
    """
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='extra_schedules'
    )
    weekday = models.ManyToManyField(Weekday, related_name='extra_schedules')
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='extra_schedules'
    )
    start = models.TimeField()
    end = models.TimeField()

    def __str__(self):
        loc = self.location.name if self.location else "Lokatsiyasiz"
        return f"{self.employee.name} → {loc} ({self.start}-{self.end})"

    class Meta:
        verbose_name = "Qo'shimcha jadval"
        verbose_name_plural = "Qo'shimcha jadvallar"


class InviteToken(models.Model):
    """Filial uchun Telegram bot taklif havolasi tokeni"""
    token = models.CharField(max_length=20, unique=True, blank=True)
    filial = models.ForeignKey(
        Filial,
        on_delete=models.CASCADE,
        related_name='invite_tokens',
        verbose_name="Filial"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex[:12]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.filial.filial_name} — {self.token}"

    class Meta:
        verbose_name = "Taklif havolasi"
        verbose_name_plural = "Taklif havolalari"


class DailyAttendanceSummary(models.Model):
    """
    Kunlik kechikish / erta ketish / ortiqcha ishlash xulosasi.
    15 daqiqagacha kechikish/erta ketish hisobga olinmaydi (grace period).
    """
    RECORD_TYPES = [
        ('late', 'Kechikish'),
        ('early_leave', 'Erta ketish'),
        ('overtime', 'Ortiqcha ishlash'),
    ]
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='daily_summaries'
    )
    date = models.DateField()
    duration_minutes = models.IntegerField(default=0)
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)

    class Meta:
        unique_together = ('employee', 'date', 'record_type')
        verbose_name = "Kunlik davomot xulosasi"
        verbose_name_plural = "Kunlik davomot xulosalari"
        ordering = ['-date']

    def __str__(self):
        return f"{self.employee.name} - {self.date} - {self.get_record_type_display()}: {self.duration_minutes} daqiqa"


class SalaryConfig(models.Model):
    """
    Xodimning maosh konfiguratsiyasi.
    Oylik oklad va kerakli soat kiritiladi,
    soatlik ish haqi avtomatik hisoblanadi.
    """
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name='salary_config'
    )
    monthly_hours = models.FloatField(
        default=168,
        help_text="Oyda ishlashi kerak bo'lgan soat soni (masalan 168)"
    )
    monthly_salary = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=0,
        help_text="Oylik oklad (so'm)"
    )
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def hourly_rate(self):
        """Soatlik ish haqi = oklad / kerakli soat"""
        if self.monthly_hours and self.monthly_hours > 0:
            return float(self.monthly_salary) / self.monthly_hours
        return 0

    def __str__(self):
        return f"{self.employee.name} — {self.monthly_salary:,} so'm / oy"

    class Meta:
        verbose_name = "Maosh konfiguratsiyasi"
        verbose_name_plural = "Maosh konfiguratsiyalari"


# ============================================================
# UMUMIY DAM OLISH KUNLARI (kadrlar bo'limi kiritadi)
# ============================================================

class PublicHoliday(models.Model):
    """
    Umumiy bayram / dam olish kunlari.
    Kadrlar bo'limi kiritadi — barcha xodimlar uchun is_day_off=True bo'ladi.
    filial=None → butun tashkilot uchun.
    """
    date = models.DateField(unique=True, verbose_name="Sana")
    name = models.CharField(max_length=200, verbose_name="Nomi")
    filial = models.ForeignKey(
        'superadmin.Filial',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='public_holidays',
        verbose_name="Filial (bo'sh = barchasi)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} — {self.name}"

    class Meta:
        ordering = ['date']
        verbose_name = "Umumiy dam olish kuni"
        verbose_name_plural = "Umumiy dam olish kunlari"


# ============================================================
# XODIMNING KUNLIK JADVALI (shablon → aniq sanalar)
# ============================================================

class EmployeeDailySchedule(models.Model):
    """
    Xodimning har bir kuni uchun aniq jadval yozuvi.
    Schedule shablonidan avtomatik generatsiya qilinadi,
    keyin alohida kunlarni qo'lda o'zgartirish mumkin.
    """
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='daily_schedules',
        verbose_name="Xodim"
    )
    date = models.DateField(verbose_name="Sana")
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='daily_schedules',
        verbose_name="Lokatsiya"
    )
    start = models.TimeField(null=True, blank=True, verbose_name="Ish boshlanishi")
    end   = models.TimeField(null=True, blank=True, verbose_name="Ish tugashi")
    is_day_off    = models.BooleanField(default=False, verbose_name="Dam olish kuni")
    day_off_reason = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name="Dam olish sababi"
    )
    source_schedule = models.ForeignKey(
        Schedule,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='daily_entries',
        verbose_name="Manba jadval"
    )
    lunch_start = models.TimeField(null=True, blank=True, verbose_name="Tushlik boshlanishi")
    lunch_end   = models.TimeField(null=True, blank=True, verbose_name="Tushlik tugashi")
    is_manually_edited = models.BooleanField(
        default=False,
        verbose_name="Qo'lda o'zgartirilgan"
    )

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['date']
        verbose_name = "Xodim kunlik jadvali"
        verbose_name_plural = "Xodim kunlik jadvallari"

    def __str__(self):
        if self.is_day_off:
            return f"{self.employee.name} — {self.date} (Dam olish)"
        return f"{self.employee.name} — {self.date} {self.start}-{self.end}"


# ============================================================
# GENERATSIYA FUNKSIYASI
# ============================================================

# Python date.weekday() → inglizcha nom
_PYTHON_WD_TO_EN = {
    0: 'Monday', 1: 'Tuesday', 2: 'Wednesday',
    3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday',
}


def generate_employee_daily_schedules(employee, from_date=None, to_date=None):
    """
    Xodimga biriktirilgan barcha Schedule lar asosida
    EmployeeDailySchedule yozuvlarini yaratadi.

    Qoidalar:
      1. PublicHoliday → is_day_off=True, sabab: bayram nomi
      2. Jadvalda bo'lmagan hafta kuni → is_day_off=True, sabab: "Dam olish kuni"
      3. Bir kun bir nechta jadvalda bo'lsa → birinchisi qo'llaniladi (priority: jadval tartibi)
      4. Qo'lda o'zgartirilgan kunlar (is_manually_edited=True) saqlanib qoladi

    from_date: default = bugun
    to_date:   default = joriy yil 31-dekabri
    """
    from datetime import date, timedelta
    from django.db.models import Q

    today = date.today()
    if from_date is None:
        from_date = today
    if to_date is None:
        to_date = date(today.year, 12, 31)

    if from_date > to_date:
        return 0

    # ── Umumiy bayramlar (filial = None yoki xodimning filiali) ──
    holiday_qs = PublicHoliday.objects.filter(
        date__gte=from_date, date__lte=to_date
    ).filter(
        Q(filial__isnull=True) | Q(filial=employee.filial)
    )
    holiday_map = {h.date: h.name for h in holiday_qs}

    # ── Jadvallar va ularning kunlari ──────────────────────────
    schedules = list(
        employee.schedules.prefetch_related('days__weekday').filter(
            days__isnull=False
        ).distinct()
    )

    # weekday_en → (schedule, schedule_day) birinchi topilgani
    from apps.superadmin.models import Weekday
    day_map: dict[str, tuple] = {}  # 'Monday' → (schedule, schedule_day)
    for sched in schedules:
        for sd in sched.days.select_related('weekday'):
            en_name = sd.weekday.name_en or ''
            if en_name and en_name not in day_map:
                day_map[en_name] = (sched, sd)

    # ── Qo'lda o'zgartirilmagan yozuvlarni o'chirish ──────────
    EmployeeDailySchedule.objects.filter(
        employee=employee,
        date__gte=from_date,
        date__lte=to_date,
        is_manually_edited=False,
    ).delete()

    # ── Kunlik yozuvlarni yaratish ─────────────────────────────
    to_create = []
    current = from_date
    while current <= to_date:
        # Qo'lda o'zgartirilgan kun bo'lsa — o'tkazib yuborish
        already_edited = EmployeeDailySchedule.objects.filter(
            employee=employee, date=current, is_manually_edited=True
        ).exists()
        if already_edited:
            current += timedelta(days=1)
            continue

        en_name = _PYTHON_WD_TO_EN[current.weekday()]

        if current in holiday_map:
            # Bayram kuni
            sched_loc = None
            sched_start = sched_end = None
            sched_ref = None
            if en_name in day_map:
                ref_sched, ref_sd = day_map[en_name]
                sched_loc   = ref_sched.location
                sched_start = ref_sd.start
                sched_end   = ref_sd.end
                sched_ref   = ref_sched
            to_create.append(EmployeeDailySchedule(
                employee=employee, date=current,
                location=sched_loc, start=sched_start, end=sched_end,
                is_day_off=True,
                day_off_reason=holiday_map[current],
                source_schedule=sched_ref,
            ))
        elif en_name in day_map:
            # Oddiy ish kuni
            ref_sched, ref_sd = day_map[en_name]
            to_create.append(EmployeeDailySchedule(
                employee=employee, date=current,
                location=ref_sched.location,
                start=ref_sd.start,
                end=ref_sd.end,
                lunch_start=ref_sched.lunch_start,
                lunch_end=ref_sched.lunch_end,
                is_day_off=False,
                source_schedule=ref_sched,
            ))
        else:
            # Dam olish kuni (jadvalda yo'q hafta kuni)
            to_create.append(EmployeeDailySchedule(
                employee=employee, date=current,
                is_day_off=True,
                day_off_reason="Dam olish kuni",
            ))

        current += timedelta(days=1)

    if to_create:
        EmployeeDailySchedule.objects.bulk_create(to_create, ignore_conflicts=True)

    return len(to_create)
