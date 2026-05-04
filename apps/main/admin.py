from django.contrib import admin
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


admin.site.register(Weekday)
admin.site.register(WorkSchedule)
admin.site.register(ScheduleDay)
admin.site.register(InviteToken)
