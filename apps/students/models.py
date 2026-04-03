"""
TINGLOVCHILAR MODULLARI
=======================
Bu fayl hozircha FAOL EMAS.
INSTALLED_APPS ga 'apps.students' qo'shilganda avtomatik ishlaydi.

Ulash uchun:
1. core/settings.py → INSTALLED_APPS ga 'apps.students' qo'shing
2. python manage.py makemigrations students
3. python manage.py migrate
"""

import uuid
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from apps.superadmin.models import Organization, Filial, Building, Administrator, Weekday
from apps.main.models import Location


MONTH_CHOICES = [
    (1, 'Yanvar'), (2, 'Fevral'), (3, 'Mart'), (4, 'Aprel'),
    (5, 'May'), (6, 'Iyun'), (7, 'Iyul'), (8, 'Avgust'),
    (9, 'Sentabr'), (10, 'Oktabr'), (11, 'Noyabr'), (12, 'Dekabr'),
]


class Direction(models.Model):
    """O'quv yo'nalishi — filialga bog'liq"""
    name = models.CharField(max_length=255, verbose_name="Yo'nalish nomi")
    filial = models.ForeignKey(
        Filial,
        on_delete=models.CASCADE,
        related_name='directions',
        verbose_name="Filial"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='directions',
        verbose_name="Tashkilot"
    )

    def __str__(self):
        return f"{self.name} ({self.filial.filial_name if self.filial else '-'})"

    class Meta:
        verbose_name = "Yo'nalish"
        verbose_name_plural = "Yo'nalishlar"


class Student(models.Model):
    """
    Tinglovchi — Telegram bot orqali ro'yxatdan o'tadi.
    Yuz rasmi bot orqali yuklanadi va tekshiriladi.
    """
    VERIFICATION_STATUS = [
        ('pending', 'Kutilmoqda'),
        ('verified', 'Tasdiqlangan'),
        ('rejected', 'Rad etilgan'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='student'
    )
    full_name = models.CharField(max_length=255)
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)

    # Yuz rasmi — davomat belgilashda ishlatiladi
    face_image = models.ImageField(
        upload_to='student_faces/',
        null=True, blank=True
    )
    face_verified = models.BooleanField(default=False)
    face_encoding = models.TextField(
        null=True, blank=True,
        help_text="Yuz ma'lumotlari (base64 yoki JSON formatida)"
    )

    # Ro'yxatdan o'tish holati — o'quv bo'limi tasdiqlaydi
    registration_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='pending'
    )

    plain_password = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="Tizimga kirish paroli (ochiq ko'rinishda)"
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='students'
    )
    filial = models.ForeignKey(
        Filial,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='students'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = "Tinglovchi"
        verbose_name_plural = "Tinglovchilar"


class Group(models.Model):
    """
    O'quv guruhi.
    O'quv bo'limi tomonidan yaratiladi va tasdiqlanadi.
    Har bir guruh ma'lum yil va oyga boglanadi.
    """
    name = models.CharField(max_length=200)
    year = models.PositiveIntegerField(verbose_name="Yil")
    month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES, verbose_name="Oy")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='groups'
    )
    filial = models.ForeignKey(
        Filial,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='groups'
    )
    direction = models.ForeignKey(
        Direction,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='groups',
        verbose_name="Yo'nalish"
    )
    students = models.ManyToManyField(
        Student,
        blank=True,
        related_name='groups'
    )

    invite_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # O'quv bo'limi tasdiqlashi
    is_confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(
        Administrator,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='confirmed_groups'
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        Administrator,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_groups'
    )

    def __str__(self):
        return f"{self.name} ({self.year}-{self.get_month_display()}) ({self.filial.filial_name if self.filial else '-'})"

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"


class Smena(models.Model):
    """Dars smenasi — para boshlanish vaqtlari"""
    name = models.CharField(max_length=100, verbose_name="Smena nomi")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='smenas'
    )
    filial = models.ForeignKey(
        Filial, on_delete=models.SET_NULL, null=True, blank=True, related_name='smenas'
    )
    para1_start = models.TimeField(verbose_name="1-para boshlanishi")
    para2_start = models.TimeField(null=True, blank=True, verbose_name="2-para boshlanishi")
    para3_start = models.TimeField(null=True, blank=True, verbose_name="3-para boshlanishi")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Smena"
        verbose_name_plural = "Smenalar"


class GroupLesson(models.Model):
    """Guruh darsi — muayyan sana uchun lokatsiya va smena"""
    group = models.ForeignKey(
        'Group', on_delete=models.CASCADE, related_name='lessons'
    )
    date = models.DateField(verbose_name="Sana")
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Lokatsiya"
    )
    smena = models.ForeignKey(
        Smena, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Smena"
    )

    class Meta:
        unique_together = ('group', 'date')
        verbose_name = "Guruh darsi"
        verbose_name_plural = "Guruh darslari"
        ordering = ['date']

    def __str__(self):
        return f"{self.group.name} - {self.date}"


class GroupSchedule(models.Model):
    """
    Guruh dars jadvali.
    Guruh turli kunlarda turli korpuslarda o'qiydi.
    Masalan: 'Maktab1' guruhi 10-16 mart kunlari 'Sport akademiyasi'da o'qiydi.
    """
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    building = models.ForeignKey(
        Building,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='schedules'
    )
    weekdays = models.ManyToManyField(
        Weekday,
        related_name='group_schedules'
    )
    start_time = models.TimeField()
    end_time = models.TimeField()

    # Muayyan sana oralig'i uchun (masalan 10-16 mart)
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        building_name = self.building.name if self.building else "Korpussiz"
        date_range = ""
        if self.date_from and self.date_to:
            date_range = f" ({self.date_from} - {self.date_to})"
        return f"{self.group.name} → {building_name}{date_range}"

    class Meta:
        verbose_name = "Guruh dars jadvali"
        verbose_name_plural = "Guruh dars jadvallari"


class StudentAttendance(models.Model):
    """
    Tinglovchi davomati.
    Telegram bot orqali yuz rasmi orqali belgilanadi.
    """
    ATTENDANCE_STATUS = [
        ('present', 'Keldi'),
        ('absent', 'Kelmadi'),
        ('late', 'Kechikdi'),
        ('excused', 'Sababli'),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    group_schedule = models.ForeignKey(
        GroupSchedule,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attendances'
    )
    date = models.DateField(default=timezone.now)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ATTENDANCE_STATUS,
        default='absent'
    )
    face_match_score = models.FloatField(
        null=True, blank=True,
        help_text="Yuz o'xshashlik foizi (0.0 - 1.0)"
    )
    verified_by_face = models.BooleanField(default=False)
    building = models.ForeignKey(
        Building,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    late_minutes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'group', 'date')
        verbose_name = "Tinglovchi davomati"
        verbose_name_plural = "Tinglovchilar davomati"

    def __str__(self):
        return f"{self.student.full_name} - {self.group.name} - {self.date}"
