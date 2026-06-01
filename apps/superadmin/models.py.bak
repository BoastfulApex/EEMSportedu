from django.db import models
from django.contrib.auth.models import User


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
        return f"{self.filial_name or 'Unnamed'} ({self.organization.name  or 'Unnamed'})" if self.organization else self.filial_name or "Unnamed Filial"

    class Meta:
        verbose_name = "Filial"
        verbose_name_plural = "Filiallar"


class Administrator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    telegram_id = models.BigIntegerField(unique=True)
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
    is_org_admin = models.BooleanField(default=False)  # True = tashkilot superadmini

    def __str__(self):
        return f"{self.full_name} ({'OrgAdmin' if self.is_org_admin else 'FilialAdmin'})"


class Weekday(models.Model):
    name = models.CharField(max_length=20, unique=True)
    name_en = models.CharField(max_length=20, unique=True, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Hafta kuni"
        verbose_name_plural = "Hafta kunlari"
