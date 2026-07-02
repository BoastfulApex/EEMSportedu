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


@admin.register(AttendanceEvent)
class AttendanceEventAdmin(admin.ModelAdmin):
    list_display   = ('person_name_display', 'person_type', 'event_type', 'date', 'time',
                      'location_display', 'distance_meters', 'verified_by', 'photo_thumb')
    search_fields  = ('employee__name', 'student__full_name')
    list_filter    = ('person_type', 'event_type', 'date', 'verified_by')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'photo_preview')
    list_per_page  = 50

    fieldsets = (
        ('Kim', {'fields': ('person_type', 'employee', 'student')}),
        ("Bog'liq yozuv", {'fields': ('attendance', 'student_attendance', 'event_type', 'date', 'time')}),
        ('Lokatsiya', {'fields': ('location', 'location_name', 'latitude', 'longitude', 'distance_meters')}),
        ('Rasm', {'fields': ('photo', 'photo_preview')}),
        ('Tekshiruv', {'fields': ('verified_by', 'face_match_score', 'created_at')}),
    )

    def person_name_display(self, obj):
        return obj.person_name
    person_name_display.short_description = 'Kim'

    def location_display(self, obj):
        return obj.location.name if obj.location else (obj.location_name or '—')
    location_display.short_description = 'Lokatsiya'

    def photo_thumb(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="height:40px;border-radius:4px;" />', obj.photo.url)
        return '—'
    photo_thumb.short_description = 'Rasm'

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-height:300px;border-radius:6px;" />', obj.photo.url)
        return '—'
    photo_preview.short_description = "Rasm ko'rinishi"
