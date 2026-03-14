from django.db import models
from django.contrib.auth.models import User


class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"


class Filial(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="filials",
        null=True, blank=True
    )
    filial_name = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"{self.filial_name or 'Unnamed'} ({self.organization.name or 'Unnamed'})" \
            if self.organization else self.filial_name or "Unnamed Filial"

    class Meta:
        verbose_name = "Filial"
        verbose_name_plural = "Filiallar"


class Building(models.Model):
    """O'quv korpus — masalan 'Sport akademiyasi', 'Asosiy bino' """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="buildings"
    )
    filial = models.ForeignKey(
        Filial,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="buildings"
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.filial.filial_name if self.filial else 'Filialsiz'})"

    class Meta:
        verbose_name = "O'quv korpus"
        verbose_name_plural = "O'quv korpuslar"


class Administrator(models.Model):
    """
    Admin rollari:
    - org_admin     : Tashkilot superadmini (hammasi)
    - hr_admin      : Xodimlar bo'limi (xodimlarni boshqaradi)
    - edu_admin     : O'quv bo'limi (guruh, tinglovchi, jadval kiritadi va tasdiqlaydi)
    - monitoring    : Monitoring bo'limi (faqat tinglovchilar hisobotini ko'radi)
    """
    ROLE_CHOICES = [
        ('org_admin',    'Tashkilot Superadmini'),
        ('filial_admin', 'Filial Admini'),
        ('hr_admin',     "Xodimlar Bo'limi"),
        ('edu_admin',    "O'quv Bo'limi"),
        ('monitoring',   'Monitoring Bo\'limi'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="admins",
        null=True, blank=True
    )
    filial = models.ForeignKey(
        Filial,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="admins"
    )
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='hr_admin')

    # Qulaylik uchun property-lar
    @property
    def is_org_admin(self):
        return self.role == 'org_admin'

    @property
    def is_filial_admin(self):
        return self.role == 'filial_admin'

    @property
    def is_hr_admin(self):
        return self.role in ('org_admin', 'hr_admin')

    @property
    def is_edu_admin(self):
        return self.role in ('org_admin', 'edu_admin')

    @property
    def is_monitoring(self):
        return self.role in ('org_admin', 'monitoring')

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Administrator"
        verbose_name_plural = "Administratorlar"


class Weekday(models.Model):
    name = models.CharField(max_length=20, unique=True)
    name_en = models.CharField(max_length=20, unique=True, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Hafta kuni"
        verbose_name_plural = "Hafta kunlari"
