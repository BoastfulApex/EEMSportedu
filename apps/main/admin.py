from django.contrib import admin
from django.utils.html import format_html
from .models import *


class ScheduleDayInline(admin.TabularInline):
    model = ScheduleDay
    extra = 1
    fields = ('weekday', 'start', 'end')


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display  = ('name', 'filial', 'location', 'lunch_start', 'lunch_end')
    search_fields = ('name',)
    list_filter   = ('filial',)
    fieldsets = (
        (None, {
            'fields': ('name', 'filial', 'location')
        }),
        ('Tushlik vaqti', {
            'fields': ('lunch_start', 'lunch_end'),
            'description': 'Tushlik vaqti ish soatidan chiqarib tashlanadi.'
        }),
    )
    inlines = [ScheduleDayInline]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display  = ('name', 'telegram_user_id', 'employee_type', 'filial')
    search_fields = ('name', 'telegram_user_id')
    list_filter   = ('employee_type', 'filial')

    fieldsets = (
        ('Asosiy', {
            'fields': ('name', 'employee_type', 'filial')
        }),
        ('Telegram', {
            'fields': ('telegram_user_id',),
            'description': "Xodimning Telegram bot orqali bog'langan ID si"
        }),
        ('Jadval va lokatsiya', {
            'fields': ('schedules',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Weekday)
class WeekdayAdmin(admin.ModelAdmin):
    list_display  = ['name', 'name_en']
    search_fields = ['name', 'name_en']


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display  = ['employee', 'location', 'start', 'end']
    search_fields = ['employee__name']
    list_filter   = ['location']


@admin.register(ScheduleDay)
class ScheduleDayAdmin(admin.ModelAdmin):
    list_display  = ['schedule', 'weekday', 'start', 'end']
    search_fields = ['schedule__name']
    list_filter   = ['weekday']


@admin.register(InviteToken)
class InviteTokenAdmin(admin.ModelAdmin):
    list_display  = ['token', 'filial', 'created_at']
    search_fields = ['token', 'filial__filial_name']
    list_filter   = ['filial']


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display  = ['user_id', 'first_name', 'last_name', 'username']
    search_fields = ['first_name', 'last_name', 'username', 'user_id']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display  = ['employee', 'date', 'check_in', 'check_out', 'location']
    search_fields = ['employee__name']
    list_filter   = ['date', 'location', 'employee__filial']
    date_hierarchy = 'date'
