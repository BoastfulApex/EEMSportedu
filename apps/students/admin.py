from django.contrib import admin
from django.utils.html import format_html
from .models import Student, Group, Direction, Smena, SmenaSlot, StudentAttendance


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display  = ('full_name', 'telegram_id', 'phone', 'organization', 'filial',
                     'registration_status', 'face_verified', 'created_at')
    search_fields = ('full_name', 'telegram_id', 'phone')
    list_filter   = ('registration_status', 'face_verified', 'organization', 'filial')
    readonly_fields = ('created_at',)

    fieldsets = (
        ('Asosiy', {
            'fields': ('full_name', 'phone', 'user', 'plain_password')
        }),
        ('Telegram', {
            'fields': ('telegram_id',),
            'description': 'Tinglovchining Telegram bot orqali bog\'langan ID si'
        }),
        ('Tashkilot', {
            'fields': ('organization', 'filial')
        }),
        ('Yuz ID', {
            'fields': ('face_image', 'face_verified', 'face_encoding'),
            'classes': ('collapse',)
        }),
        ('Holat', {
            'fields': ('registration_status', 'created_at')
        }),
    )


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display  = ('name', 'year', 'month', 'organization', 'filial', 'direction')
    search_fields = ('name',)
    list_filter   = ('year', 'month', 'organization', 'filial')


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display  = ('name', 'filial', 'organization')
    search_fields = ('name',)
    list_filter   = ('organization', 'filial')


@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display   = ('student', 'group', 'date', 'check_in', 'check_out',
                      'status', 'late_minutes', 'early_leave_minutes', 'verified_by_face')
    search_fields  = ('student__full_name', 'student__telegram_id')
    list_filter    = ('status', 'date', 'group', 'verified_by_face')
    ordering       = ('-date', '-check_in')
    readonly_fields = ('date',)
    date_hierarchy = 'date'
    list_per_page  = 50

    fieldsets = (
        ('Tinglovchi', {
            'fields': ('student', 'group', 'date')
        }),
        ('Davomat', {
            'fields': ('check_in', 'check_out', 'status', 'verified_by_face')
        }),
        ('Kechikish / Erta ketish', {
            'fields': ('late_minutes', 'early_leave_minutes'),
            'classes': ('collapse',)
        }),
    )


class SmenaSlotInline(admin.TabularInline):
    model  = SmenaSlot
    extra  = 0
    fields = ('order', 'start', 'end')


@admin.register(Smena)
class SmenaAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'filial')
    search_fields = ('name',)
    list_filter  = ('organization', 'filial')
    inlines      = [SmenaSlotInline]
