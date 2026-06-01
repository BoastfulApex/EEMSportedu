from django.db import models
from django.utils import timezone
from apps.superadmin.models import *


class TelegramUser(models.Model):
    user_id = models.BigIntegerField(unique=True, null=True, blank=True)
    username = models.CharField(max_length=100, null=True, blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username if self.username else "Unnamed User"
    
    class Meta:
        verbose_name = "Telegram User"
        verbose_name_plural = "Telegram Users"
    

class Location(models.Model):
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
    name = models.CharField(max_length=200, blank=True, null=True)
    user_id = models.IntegerField(null=True, blank=True, unique=True)
    filial = models.ForeignKey(Filial, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    image = models.ImageField(null=True)

    class Meta:
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar"
        
    @property
    def imageURL(self):
        try:
            url = self.image.url
        except:
            url = ''
        return url

    def __str__(self):
        return self.name if self.name else "Unnamed Employee"

    def __str__(self):
        return self.name
        

class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    check_number = models.IntegerField(null=True, default=0)

    class Meta:
        unique_together = ('employee', 'date')  # Har bir xodim uchun kuniga 1 ta yozuv

    def __str__(self):
        return f"{self.employee.name} - {self.date}"
    
    class Meta:
        verbose_name = "Kirish Chiqishlar"
        verbose_name_plural = "Kirish Chiqishlar"
    

class WorkSchedule(models.Model):
    weekday = models.ManyToManyField(Weekday, related_name='work_schedules')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='work_schedules', null=True, blank=True)
    admin = models.ForeignKey(Administrator, on_delete=models.SET_NULL,  related_name='work_schedules', null=True, blank=True)
    start = models.TimeField()
    end = models.TimeField()

    def __str__(self):
        return f"{self.employee.name}"

    class Meta:
        verbose_name = "Ish jadvali"
        verbose_name_plural = "Ish jadvali"