import json
import calendar
import openpyxl
from datetime import timedelta, datetime

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from apps.superadmin.decorators import hr_admin_required, any_admin_required, monitoring_required
from django.db.models import Q, OuterRef, Subquery, Count, F
from django.db.models.functions import TruncMonth, ExtractWeekDay
from django.http import HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.template import loader
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic.edit import DeleteView

from apps.superadmin.models import Administrator, Filial, Weekday
from apps.main.models import Employee, WorkSchedule, Attendance, Schedule, ScheduleDay, ExtraSchedule, SalaryConfig
from apps.main.forms import (
    EmployeeForm, ScheduleForm, AttendanceDateRangeForm, SalaryConfigForm
)


# ============================================================
# HISOBOT YORDAMCHI FUNKSIYALARI
# ============================================================

def _parse_dates(start_date, end_date):
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date   = datetime.strptime(end_date,   '%Y-%m-%d').date()
    return start_date, end_date


def _total_minutes(check_in, check_out, date):
    if not check_in or not check_out:
        return 0
    delta = datetime.combine(date, check_out) - datetime.combine(date, check_in)
    return max(0, int(delta.total_seconds() / 60))


def _late_minutes(check_in, schedule_start, date):
    if not check_in:
        return '-'
    diff = int((datetime.combine(date, check_in) -
                datetime.combine(date, schedule_start)).total_seconds() / 60)
    return max(0, diff)


def _early_leave_minutes(check_out, schedule_end, date):
    if not check_out:
        return '-'
    diff = int((datetime.combine(date, schedule_end) -
                datetime.combine(date, check_out)).total_seconds() / 60)
    return max(0, diff)


def _build_day_rows(employee, current, weekday_obj, week_uz):
    """
    Bir xodimning bir kuniga tegishli barcha jadval qatorlarini qaytaradi.
    Yangi Schedule M2M dan foydalanadi.
    """
    rows = []

    # Xodimga biriktirilgan jadvallarning bugungi kunga mos ScheduleDay larini olish
    schedule_days = ScheduleDay.objects.filter(
        schedule__employees=employee,
        weekday=weekday_obj
    ).select_related('schedule__location', 'weekday')

    for sd in schedule_days:
        sch = sd.schedule
        att = Attendance.objects.filter(
            employee=employee, date=current, location=sch.location
        ).first()
        if att is None:
            att = Attendance.objects.filter(employee=employee, date=current).first()

        check_in  = att.check_in  if att else None
        check_out = att.check_out if att else None
        status    = "Kelgan" if att else "Kelmagan"
        worked_min = _total_minutes(check_in, check_out, current)
        worked_str = f"{worked_min // 60}s {worked_min % 60}d" if worked_min else "-"

        rows.append({
            'date':                current,
            'weekday':             week_uz,
            'employee':            employee.name,
            'employee_type':       employee.get_employee_type_display(),
            'schedule_type':       sch.name,
            'location':            sch.location.name if sch.location else '-',
            'schedule_start':      sd.start,
            'schedule_end':        sd.end,
            'status':              status,
            'check_in':            check_in or '-',
            'check_out':           check_out or '-',
            'worked':              worked_str,
            'late_minutes':        _late_minutes(check_in, sd.start, current),
            'early_leave_minutes': _early_leave_minutes(check_out, sd.end, current),
        })

    return rows


# ============================================================
# ASOSIY HISOBOT FUNKSIYALARI
# ============================================================

def build_report(start_date, end_date, filial_id=None):
    start_date, end_date = _parse_dates(start_date, end_date)
    report = []
    delta  = timedelta(days=1)
    current = start_date

    while current <= end_date:
        weekday_name = calendar.day_name[current.weekday()]
        try:
            weekday_obj = Weekday.objects.get(name_en=weekday_name)
            week_uz = weekday_obj.name
        except Weekday.DoesNotExist:
            current += delta
            continue

        # Shu kunda ScheduleDay yozuvi bor xodimlar
        employees_today = Employee.objects.filter(
            schedules__days__weekday=weekday_obj,
            created_at__date__lte=current,
        ).distinct()
        if filial_id:
            employees_today = employees_today.filter(filial_id=int(filial_id))

        for employee in employees_today:
            rows = _build_day_rows(employee, current, weekday_obj, week_uz)
            report.extend(rows)

        current += delta

    for i, row in enumerate(report, 1):
        row['index'] = i
    return report


def build_report_for_employee(employee_id, start_date, end_date):
    start_date, end_date = _parse_dates(start_date, end_date)
    employee = Employee.objects.get(id=employee_id)
    report   = []
    delta    = timedelta(days=1)
    current  = start_date

    while current <= end_date:
        if employee.created_at.date() > current:
            current += delta
            continue

        weekday_name = calendar.day_name[current.weekday()]
        try:
            weekday_obj = Weekday.objects.get(name_en=weekday_name)
            week_uz = weekday_obj.name
        except Weekday.DoesNotExist:
            current += delta
            continue

        rows = _build_day_rows(employee, current, weekday_obj, week_uz)
        report.extend(rows)
        current += delta

    for i, row in enumerate(report, 1):
        row['index'] = i
    return report


# ============================================================
# DASHBOARD
# ============================================================

@any_admin_required
def index(request):
    admin_user = request.admin_user

    data = {}
    filial = ''
    total_attendance_count = 0
    todays_attendance_count = 0
    early_leave_percent = 0
    late_percent = 0
    late_count = 0
    early_leave_count = 0
    chart_labels = []
    late_values = []
    early_values = []

    tashkent_time = timezone.localtime(timezone.now())

    if admin_user.is_org_admin and 'selected_filial_id' not in request.session:
        request.session['selected_filial_id'] = 'super_admin'

    selected_filial_id = request.session.get('selected_filial_id', 'super_admin')

    if admin_user.is_org_admin:
        filials = Filial.objects.filter(organization=admin_user.organization)
        data['filials'] = filials
        data['selected_filial_id'] = selected_filial_id
        template = 'home/superuser/super_dashboard.html'
        try:
            filial = Filial.objects.get(id=int(selected_filial_id))
        except Exception:
            filial = ''
    else:
        template = 'home/user/staff_dashboard.html'
        filial = admin_user.filial

    if selected_filial_id != 'super_admin' and filial:
        today = timezone.localdate()
        week_start = today - timedelta(days=6)

        todays_attendance_count = Attendance.objects.filter(
            employee__filial=filial, date=today
        ).count()

        attendances = Attendance.objects.filter(
            employee__filial=filial,
            date__range=[week_start, today]
        ).select_related('employee__schedules')

        for att in attendances:
            total_attendance_count += 1
            # Xodimning bugungi ScheduleDay orqali kechikish/erta ketishni hisoblaymiz
            today_wd = att.date.weekday()  # 0=Monday
            emp_day = ScheduleDay.objects.filter(
                schedule__employees=att.employee
            ).select_related('weekday').filter(weekday__name_en__iexact=calendar.day_name[today_wd]).first()
            if emp_day:
                if att.check_in and att.check_in > emp_day.start:
                    late_count += 1
                if att.check_out and att.check_out < emp_day.end:
                    early_leave_count += 1

        if total_attendance_count > 0:
            late_percent = late_count / total_attendance_count * 100
            early_leave_percent = early_leave_count / total_attendance_count * 100

        template = 'home/user/staff_dashboard.html'

    context = {
        'segment': 'dashboard',
        'data': data,
        'filial': filial,
        'tashkent_time': tashkent_time,
        'todays_attendance_count': todays_attendance_count,
        'late_percent': round(late_percent, 1),
        'early_leave_percent': round(early_leave_percent, 1),
        'chart_labels_json': json.dumps(chart_labels),
        'late_values_json': json.dumps(late_values),
        'early_values_json': json.dumps(early_values),
    }
    return HttpResponse(loader.get_template(template).render(context, request))


# ============================================================
# XODIMLAR
# ============================================================

def _get_filial_id(admin_user, request):
    if admin_user.is_org_admin:
        selected = request.session.get('selected_filial_id', 'super_admin')
        if selected == 'super_admin':
            return None
        return int(selected)
    return admin_user.filial.id if admin_user.filial else None


def _base_context(admin_user):
    return {
        'filials': Filial.objects.filter(organization=admin_user.organization)
    }


@hr_admin_required
def employees(request):
    admin_user = request.admin_user

    filial_id = _get_filial_id(admin_user, request)
    if filial_id is None:
        return redirect('/home/')

    data = {'filials': _base_context(admin_user)['filials']}
    filial = Filial.objects.get(id=filial_id)
    emps = Employee.objects.filter(filial_id=filial_id)
    search_query = request.GET.get('q')
    if search_query:
        emps = emps.filter(Q(name__icontains=search_query))
    paginator = Paginator(emps, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'segment': 'employees',
        'filial': filial.filial_name,
        'tashkent_time': timezone.localtime(timezone.now()),
        'data': data,
    }
    return HttpResponse(loader.get_template('home/user/employees/employees.html').render(context, request))


@hr_admin_required
def employee_create(request):
    admin_user = request.admin_user

    filial_id = _get_filial_id(admin_user, request)
    if filial_id is None:
        return redirect('/home/')

    data = {'filials': _base_context(admin_user)['filials']}
    filial = Filial.objects.get(id=filial_id)

    if request.method == 'POST':
        emp_form = EmployeeForm(request.POST, request.FILES, filial=filial)
        if emp_form.is_valid():
            employee = emp_form.save(commit=False)
            employee.filial = filial
            employee.save()
            emp_form.save_m2m()
            return redirect('employees')
    else:
        emp_form = EmployeeForm(filial=filial)

    return render(request, 'home/user/employees/employee_create.html', {
        'emp_form': emp_form,
        'filial': filial.filial_name,
        'segment': 'employees',
        'data': data,
        'tashkent_time': timezone.localtime(timezone.now()),
    })


@hr_admin_required
def employee_detail(request, pk):
    admin_user = request.admin_user

    filial_id = _get_filial_id(admin_user, request)
    if filial_id is None:
        return redirect('/home/')

    employee = get_object_or_404(Employee, id=pk)
    if employee.filial_id != filial_id:
        return redirect('home')

    data = {'filials': _base_context(admin_user)['filials']}
    filial = employee.filial

    salary_cfg, _ = SalaryConfig.objects.get_or_create(employee=employee)

    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee, filial=filial)
        salary_form = SalaryConfigForm(request.POST, instance=salary_cfg)
        if form.is_valid() and salary_form.is_valid():
            emp = form.save(commit=False)
            if 'image' in request.FILES:
                emp.image = request.FILES['image']
            emp.save()
            form.save_m2m()
            salary_form.save()
            return redirect('employees')
    else:
        form = EmployeeForm(instance=employee, filial=filial)
        salary_form = SalaryConfigForm(instance=salary_cfg)

    return render(request, 'home/user/employees/employee_detail.html', {
        'form': form,
        'salary_form': salary_form,
        'segment': 'employees',
        'employee': employee,
        'filial': employee.filial.filial_name,
        'tashkent_time': timezone.localtime(timezone.now()),
        'data': data,
    })


class EmployeeDelete(DeleteView):
    model = Employee
    fields = '__all__'
    success_url = reverse_lazy('employees')


# ============================================================
# JADVAL SHABLONLARI (yangi)
# ============================================================

@hr_admin_required
def schedules(request):
    """Jadval shablonlari ro'yxati"""
    admin_user = request.admin_user

    filial_id = _get_filial_id(admin_user, request)
    if filial_id is None:
        return redirect('/home/')

    data = {'filials': _base_context(admin_user)['filials']}
    filial = Filial.objects.get(id=filial_id)
    search_query = request.GET.get('q', '')

    qs = Schedule.objects.filter(filial_id=filial_id).prefetch_related('days__weekday', 'location').order_by('name')
    if search_query:
        qs = qs.filter(name__icontains=search_query)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'home/user/workschedule/schedules.html', {
        'page_obj': page_obj,
        'segment': 'schedules',
        'filial': filial.filial_name,
        'tashkent_time': timezone.localtime(timezone.now()),
        'data': data,
        'search_query': search_query,
    })


def _save_schedule_days(schedule, post_data):
    """POST dan kun vaqtlarini o'qib ScheduleDay larni yaratadi/yangilaydi."""
    all_weekdays = Weekday.objects.all()
    for wd in all_weekdays:
        key = f'day_{wd.id}'
        start_val = post_data.get(f'{key}_start', '').strip()
        end_val   = post_data.get(f'{key}_end', '').strip()
        if start_val and end_val:
            ScheduleDay.objects.update_or_create(
                schedule=schedule, weekday=wd,
                defaults={'start': start_val, 'end': end_val}
            )
        else:
            ScheduleDay.objects.filter(schedule=schedule, weekday=wd).delete()


@hr_admin_required
def schedule_create(request):
    """Yangi jadval shabloni yaratish"""
    admin_user = request.admin_user

    filial_id = _get_filial_id(admin_user, request)
    if filial_id is None:
        return redirect('/home/')

    data = {'filials': _base_context(admin_user)['filials']}
    filial = Filial.objects.get(id=filial_id)
    weekdays = Weekday.objects.all()

    if request.method == 'POST':
        form = ScheduleForm(request.POST, filial=filial)
        if form.is_valid():
            sch = form.save(commit=False)
            sch.filial = filial
            sch.save()
            _save_schedule_days(sch, request.POST)
            return redirect('schedules')
    else:
        form = ScheduleForm(filial=filial)

    return render(request, 'home/user/workschedule/schedule_create.html', {
        'form': form,
        'weekdays': weekdays,
        'filial': filial.filial_name,
        'segment': 'schedules',
        'tashkent_time': timezone.localtime(timezone.now()),
        'data': data,
    })


@hr_admin_required
def schedule_detail(request, pk):
    """Jadval shablonini tahrirlash"""
    admin_user = request.admin_user

    filial_id = _get_filial_id(admin_user, request)
    if filial_id is None:
        return redirect('/home/')

    schedule = get_object_or_404(Schedule, id=pk, filial_id=filial_id)
    data = {'filials': _base_context(admin_user)['filials']}
    filial = Filial.objects.get(id=filial_id)
    weekdays = Weekday.objects.all()

    # Mavjud kunlar dict: {weekday_id: ScheduleDay}
    existing_days = {sd.weekday_id: sd for sd in schedule.days.select_related('weekday')}

    if request.method == 'POST':
        form = ScheduleForm(request.POST, instance=schedule, filial=filial)
        if form.is_valid():
            form.save()
            _save_schedule_days(schedule, request.POST)
            return redirect('schedules')
    else:
        form = ScheduleForm(instance=schedule, filial=filial)

    return render(request, 'home/user/workschedule/schedule_detail.html', {
        'form': form,
        'schedule': schedule,
        'weekdays': weekdays,
        'existing_days': existing_days,
        'filial': filial.filial_name,
        'segment': 'schedules',
        'tashkent_time': timezone.localtime(timezone.now()),
        'data': data,
    })


class ScheduleDelete(DeleteView):
    model = Schedule
    success_url = reverse_lazy('schedules')
    template_name = 'main/schedule_confirm_delete.html'


# ============================================================
# HISOBOT
# ============================================================

@any_admin_required
def get_report_date(request):
    admin_user = request.admin_user

    filial_id = _get_filial_id(admin_user, request)
    if filial_id is None:
        return redirect('/home/')

    data = {'filials': _base_context(admin_user)['filials']}
    filial_name = admin_user.filial.filial_name if admin_user.filial else ''
    report = []

    if request.method == 'POST':
        form = AttendanceDateRangeForm(request.POST)
        if form.is_valid():
            report = build_report(
                form.cleaned_data['start_date'],
                form.cleaned_data['end_date'],
                filial_id=filial_id
            )
    else:
        form = AttendanceDateRangeForm()

    return render(request, 'home/user/report/get_report_date.html', {
        'form': form,
        'report': report,
        'segment': 'report',
        'tashkent_time': timezone.localtime(timezone.now()),
        'filial': filial_name,
        'data': data,
    })


@any_admin_required
def download_excel(request):
    admin_user = request.admin_user

    filial_id = _get_filial_id(admin_user, request)
    if filial_id is None:
        return redirect('/home/')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if not start_date or not end_date:
        return redirect('home_get_dates')

    report_data = build_report(start_date=start_date, end_date=end_date, filial_id=filial_id)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Davomat hisoboti"
    headers = ['T/r', 'Sana', 'Hafta kuni', 'Xodim', 'Turi', 'Holati',
               'Jadval', 'Lokatsiya', 'Jadval (boshlanish)', 'Jadval (tugash)',
               'Kirish', 'Chiqish', 'Jami ish vaqti', 'Kechikdi (daqiqa)', 'Erta ketdi (daqiqa)']
    ws.append(headers)
    for row in report_data:
        ws.append([
            row['index'], str(row['date']), row['weekday'],
            row['employee'], row['employee_type'], row['status'],
            row['schedule_type'], row['location'],
            str(row['schedule_start']), str(row['schedule_end']),
            str(row['check_in']), str(row['check_out']),
            row['worked'], row['late_minutes'], row['early_leave_minutes'],
        ])
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename=hisobot.xlsx'
    wb.save(response)
    return response


@any_admin_required
def employee_report(request, pk):
    admin_user = request.admin_user

    filial_id = _get_filial_id(admin_user, request)
    if filial_id is None:
        return redirect('/home/')

    employee = get_object_or_404(Employee, id=pk)
    data = {'filials': _base_context(admin_user)['filials']}
    filial_name = admin_user.filial.filial_name if admin_user.filial else ''
    report = []

    if request.method == 'POST':
        form = AttendanceDateRangeForm(request.POST)
        if form.is_valid():
            report = build_report_for_employee(
                pk,
                form.cleaned_data['start_date'],
                form.cleaned_data['end_date']
            )
    else:
        form = AttendanceDateRangeForm()

    return render(request, 'home/user/report/get_report_date.html', {
        'employee': employee,
        'form': form,
        'report': report,
        'tashkent_time': timezone.localtime(timezone.now()),
        'filial': filial_name,
        'segment': 'employees',
        'data': data,
    })


@any_admin_required
def employee_download_excel(request, pk):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if not start_date or not end_date:
        return redirect('home_get_dates')

    report_data = build_report_for_employee(pk, start_date, end_date)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Xodim hisoboti"
    headers = ['T/r', 'Sana', 'Hafta kuni', 'Xodim', 'Turi', 'Holati',
               'Jadval', 'Lokatsiya', 'Jadval (boshlanish)', 'Jadval (tugash)',
               'Kirish', 'Chiqish', 'Jami ish vaqti', 'Kechikdi (daqiqa)', 'Erta ketdi (daqiqa)']
    ws.append(headers)
    for row in report_data:
        ws.append([
            row['index'], str(row['date']), row['weekday'],
            row['employee'], row['employee_type'], row['status'],
            row['schedule_type'], row['location'],
            str(row['schedule_start']), str(row['schedule_end']),
            str(row['check_in']), str(row['check_out']),
            row['worked'], row['late_minutes'], row['early_leave_minutes'],
        ])
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename=hisobot.xlsx'
    wb.save(response)
    return response
