import os
from datetime import date, datetime
from typing import List, Any
from asgiref.sync import sync_to_async
from apps.main.models import *
from apps.superadmin.models import *
from django.db.models import F, ExpressionWrapper, DurationField
from datetime import timedelta


@sync_to_async
def get_employee(user_id):
    try:
        user = Employee.objects.filter(telegram_user_id=user_id).first()
        return user
    except:
        return None


@sync_to_async
def add_employee(user_id, full_name, admin_id):
    # try:
    Employee.objects.create(telegram_user_id=user_id, name=full_name).save()
    admin = Administrator.objects.filter(telegram_id=admin_id).first()
    emp = Employee.objects.filter(telegram_user_id=user_id).first()
    emp.filial = admin.filial
    emp.save()
    return emp
    # except Exception as exx:
    #     print(exx)
    #     return None

@sync_to_async
def get_telegram_user(user_id: int) -> TelegramUser:
    try:
        return TelegramUser.objects.get(user_id=user_id)
    except TelegramUser.DoesNotExist:
        return None

@sync_to_async
def add_telegram_user(user_id, username, first_name, last_name):
    try:
        user = TelegramUser.objects.create(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        return user
    except Exception as exx:
        print(exx)
        return None


@sync_to_async
def get_all_filials():
    return list(Filial.objects.all())
    
    
@sync_to_async
def get_employees() -> List[Employee]:
    eps = Employee.objects.all()
    return eps


@sync_to_async
def get_employees() -> List[Employee]:
    eps = Employee.objects.all()
    return eps


@sync_to_async
def is_user_employee(user_id: int) -> bool:
    return Employee.objects.filter(telegram_user_id=user_id).exists()


@sync_to_async
def is_user_admin(user_id: int) -> bool:
    return Administrator.objects.filter(telegram_id=user_id).exists()


@sync_to_async
def is_user_student(user_id: int) -> bool:
    from apps.students.models import Student
    return Student.objects.filter(telegram_id=user_id).exists()


@sync_to_async
def get_admins_by_filial(filial_id: int):
    return list(Administrator.objects.filter(filial_id=filial_id))


@sync_to_async
def get_all_admin_ids() -> list[int]:
    user_ids = list(Administrator.objects.values_list('telegram_id', flat=True))
    print(user_ids)
    return user_ids


@sync_to_async
def get_all_addresses()-> list[str]:
    return list(Location.objects.filter(name__isnull=False).values_list("name", flat=True))


@sync_to_async
def get_filial_location(user_id):
    admin = Administrator.objects.filter(telegram_id=user_id).first()
    return Location.objects.filter(filial = admin.filial).last()


@sync_to_async
def save_location(name, lat, lon, user_id):
    try:
        admin = Administrator.objects.get(telegram_id=user_id)
        location = Location.objects.filter(filial=admin.filial).first()
        if location:
            # Mavjud locationni yangilaymiz
            location.name = name
            location.latitude = lat
            location.longitude = lon
            location.save()
        else:
            # Yangi location yaratamiz
            Location.objects.create(
                filial=admin.filial,
                name=name,
                latitude=lat,
                longitude=lon
            )    
    except Exception as exx:
        print(exx)
        return None
    
    
        
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

async def get_location_name(lat, lon):
    geolocator = Nominatim(user_agent="myuzbot (jigar@t.me)")
    try:
        location = geolocator.reverse((lat, lon), timeout=10)
        return location.address if location else "Nomaʼlum manzil"
    except GeocoderTimedOut:
        return "Geocoding vaqti tugadi"
    

@sync_to_async
def create_employee_if_not_exists(user_id, full_name):
    if not Employee.objects.filter(telegram_user_id=user_id).exists():
        Employee.objects.create(telegram_user_id=user_id, name=full_name)
        

@sync_to_async
def get_all_weekdays():
    return list(Weekday.objects.all())


@sync_to_async
def save_work_schedule(user_id, data):
    admin = Administrator.objects.filter(telegram_id=user_id).first()

    employee = Employee.objects.filter(telegram_user_id=data["employee_id"]).first()
    if not employee:
        raise Exception("Foydalanuvchi topilmadi!")
    
    weekdays = Weekday.objects.filter(name__in=data["selected_weekdays"])
    ws = WorkSchedule.objects.create(
        employee=employee,
        start=data["start"],
        end=data["end"],
        admin=admin
    )
    ws.weekday.set(weekdays)
    

@sync_to_async
def delete_employee_by_user_id(user_id: int) -> bool:
    employee = Employee.objects.filter(telegram_user_id=user_id).first()
    if employee:
        employee.delete()
        return True  # O'chirildi
    return False  # Topilmadi


@sync_to_async
def get_employee_schedule_text(employee_id: int) -> str:
    try:
        emp = Employee.objects.filter(telegram_user_id=employee_id).first()
        if not emp:
            return "❌ Xodim topilmadi."

        schedules = WorkSchedule.objects.filter(employee_id=emp.id).prefetch_related('weekday')
        
        if not schedules:
            return "⚠️ Ish jadvali mavjud emas."

        jadval_matni = "🗓 Sizning ish jadvalingiz:\n\n"
        for schedule in schedules:
            kunlar = ", ".join([w.name for w in schedule.weekday.all()])
            vaqt = f"{schedule.start.strftime('%H:%M')} - {schedule.end.strftime('%H:%M')}"
            jadval_matni += f"📅 {kunlar} | ⏰ {vaqt}\n"

        return jadval_matni
    except Exception as e:
        print(f"Xatolik: {e}")
        return "⚠️ Ish jadvali topilmadi yoki xato yuz berdi."

@sync_to_async
def get_daily_report(filial):
    today = datetime.today().date()  # faqat sana

    records = (
        Attendance.objects.filter(employee__filial_id=filial.id, date=today)
        .annotate(
            worked_hours=ExpressionWrapper(
                F("check_out") - F("check_in"),
                output_field=DurationField()
            )
        )
        .select_related("employee")
    )

    lines = []
    for rec in records:
        worked = rec.worked_hours or timedelta()
        hours, remainder = divmod(int(worked.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)

        lines.append(
            f"👤 {rec.employee.name}\n"
            f" ⏰ Keldi: {rec.check_in.strftime('%H:%M') if rec.check_in else '-'}\n"
            f" 🚪 Ketdi: {rec.check_out.strftime('%H:%M') if rec.check_out else '-'}\n"
            f" ⌛ Ishlagan: {hours:02d}:{minutes:02d}"
        )
    if not lines:
        return "Bugun hech kim kelmadi."
    return "\n\n".join(lines)

# @sync_to_async
# def generate_attendance_excel_file(start_date, end_date, file_name="hisobot.xlsx"):
#     import os
#     import pandas as pd
#     from datetime import datetime, timedelta

#     data = []
#     current_date = start_date
#     while current_date <= end_date:
#         weekday_name = current_date.strftime('%A').lower()
#         weekday = Weekday.objects.filter(name_en__iexact=weekday_name).first()
#         if not weekday:
#             current_date += timedelta(days=1)
#             continue

#         schedules = WorkSchedule.objects.filter(weekday=weekday).select_related('employee')

#         for schedule in schedules:
#             emp = schedule.employee
#             attendance = Attendance.objects.filter(employee=emp, date=current_date).first()
#             check_in = attendance.check_in if attendance else None
#             check_out = attendance.check_out if attendance else None

#             in_diff = out_diff = None
#             if check_in:
#                 delta_in = datetime.combine(current_date, check_in) - datetime.combine(current_date, schedule.start)
#                 in_diff = int(delta_in.total_seconds() // 60)
#             if check_out:
#                 delta_out = datetime.combine(current_date, check_out) - datetime.combine(current_date, schedule.end)
#                 out_diff = int(delta_out.total_seconds() // 60)
#             print(schedule.id)
#             data.append({
#                 "Sana": current_date.strftime("%d.%m.%Y"),
#                 "Xodim": emp.name,
#                 "Xafta kuni": weekday.name,
#                 "Kutilgan kirish": schedule.start.strftime("%H:%M"),
#                 "Amalda kirgan": check_in.strftime("%H:%M") if check_in else "-",
#                 "Kech/erta kirish (min)": in_diff,
#                 "Kutilgan chiqish": schedule.end.strftime("%H:%M"),
#                 "Amalda chiqqan": check_out.strftime("%H:%M") if check_out else "-",
#                 "Kech/erta chiqish (min)": out_diff,
#             })

#         current_date += timedelta(days=1)

#     df = pd.DataFrame(data)

#     dir_path = "media/reports"
#     os.makedirs(dir_path, exist_ok=True)
#     full_path = os.path.join(dir_path, file_name)

#     with pd.ExcelWriter(full_path, engine='openpyxl') as writer:
#         df.to_excel(writer, index=False, sheet_name="Hisobot")
        
#     print(full_path)

#     return full_path

@sync_to_async
def generate_attendance_excel_file(user_id, start_date, end_date, file_name="hisobot.xlsx"):
    import os
    import pandas as pd
    from datetime import datetime, timedelta
    
    
    admin = Administrator.objects.filter(telegram_id=user_id).first()
    data = []
    current_date = start_date
    while current_date <= end_date:
        weekday_name = current_date.strftime('%A').lower()
        weekday = Weekday.objects.filter(name_en__iexact=weekday_name).first()
        if not weekday:
            current_date += timedelta(days=1)
            continue

        schedules = WorkSchedule.objects.filter(weekday=weekday, employee__filial_id = admin.filial.id).all()

        for schedule in schedules:
            if not schedule.employee.created_at.date() <= current_date.date():
                continue
            emp = schedule.employee
            attendance = Attendance.objects.filter(employee=emp, date=current_date).first()
            check_in = attendance.check_in if attendance else None
            check_out = attendance.check_out if attendance else None

            in_diff = out_diff = None
            if check_in:
                delta_in = datetime.combine(current_date, check_in) - datetime.combine(current_date, schedule.start)
                in_diff = int(delta_in.total_seconds() // 60)
            if check_out:
                delta_out = datetime.combine(current_date, check_out) - datetime.combine(current_date, schedule.end)
                out_diff = int(delta_out.total_seconds() // 60)

            data.append({
                "Sana": current_date.strftime("%d.%m.%Y"),
                "Xodim": emp.name,
                "Xafta kuni": weekday.name,
                "Kutilgan kirish": schedule.start.strftime("%H:%M"),
                "Amalda kirgan": check_in.strftime("%H:%M") if check_in else "-",
                "Kech/erta kirish (min)": in_diff,
                "Kutilgan chiqish": schedule.end.strftime("%H:%M"),
                "Amalda chiqqan": check_out.strftime("%H:%M") if check_out else "-",
                "Kech/erta chiqish (min)": out_diff,
            })

        current_date += timedelta(days=1)

    df = pd.DataFrame(data)

    dir_path = "files/reports"
    os.makedirs(dir_path, exist_ok=True)
    full_path = os.path.join(dir_path, file_name)
    df.to_excel(full_path, index=False)
    print(full_path)
    return full_path

@sync_to_async
def get_organizations():
    from apps.superadmin.models import Organization
    return list(Organization.objects.all().values("id", "name"))


@sync_to_async
def get_filials_by_org(org_id):
    from apps.superadmin.models import Filial
    return list(Filial.objects.filter(organization_id=org_id).values("id", "filial_name"))


@sync_to_async
def get_filials_by_org_objects(org_id: int):
    """Org bo'yicha filiallar — ORM objektlar sifatida"""
    return list(Filial.objects.filter(organization_id=org_id))


@sync_to_async
def get_organization_by_id(org_id: int):
    """Tashkilotni ID bo'yicha olish"""
    try:
        org = Organization.objects.get(id=org_id)
        return {"id": org.id, "name": org.name}
    except Organization.DoesNotExist:
        return None


@sync_to_async
def get_hr_admins_by_org(org_id: int):
    """HR adminlar: org_admin + hr_admin rollariga ega adminlar"""
    return list(
        Administrator.objects.filter(
            organization_id=org_id,
            role__in=["org_admin", "hr_admin"]
        )
    )


@sync_to_async
def get_hr_admins_by_filial(filial_id: int):
    """Filial bo'yicha HR adminlar: org_admin + hr_admin"""
    return list(
        Administrator.objects.filter(
            filial_id=filial_id,
            role__in=["org_admin", "hr_admin"]
        )
    )


@sync_to_async
def get_filial_by_id(filial_id: int):
    """Filialni ID bo'yicha olish"""
    try:
        filial = Filial.objects.get(id=filial_id)
        return {"id": filial.id, "name": filial.filial_name}
    except Filial.DoesNotExist:
        return None


@sync_to_async
def get_schedules_by_filial(filial_id: int):
    """Filial uchun tayyor jadvallar ro'yxati (days bilan)"""
    from apps.main.models import Schedule
    schedules = list(
        Schedule.objects.filter(filial_id=filial_id)
        .prefetch_related('days__weekday')
    )
    result = []
    for s in schedules:
        days = s.days.order_by('weekday__id').select_related('weekday')
        if days:
            day_names = ", ".join(d.weekday.name[:2] for d in days)
            times = f"{days[0].start.strftime('%H:%M')}-{days[0].end.strftime('%H:%M')}"
            label = f"{s.name} ({day_names} | {times})"
        else:
            label = s.name
        result.append({'id': s.id, 'label': label})
    return result


@sync_to_async
def assign_schedules_to_employee(emp_user_id: int, schedule_ids: list):
    """Xodimga tanlangan jadvallarni biriktirish (M2M)"""
    from apps.main.models import Schedule
    employee = Employee.objects.filter(telegram_user_id=emp_user_id).first()
    if not employee:
        return False
    schedules = Schedule.objects.filter(id__in=schedule_ids)
    employee.schedules.set(schedules)
    return True


@sync_to_async
def get_invite_token(token: str):
    """Token orqali filial va tashkilot ma'lumotlarini olish"""
    from apps.main.models import InviteToken
    try:
        invite = InviteToken.objects.select_related(
            'filial', 'filial__organization'
        ).get(token=token, is_active=True)
        return {
            'filial_id': invite.filial.id,
            'filial_name': invite.filial.filial_name,
            'org_id': invite.filial.organization.id,
            'org_name': invite.filial.organization.name,
        }
    except InviteToken.DoesNotExist:
        return None


@sync_to_async
def get_group_by_invite_token(token: str):
    """Guruh taklif tokeni orqali guruhni olish"""
    from apps.students.models import Group
    try:
        group = Group.objects.select_related(
            'filial', 'organization', 'direction'
        ).get(invite_token=token)
        return {
            'id':           group.id,
            'name':         group.name,
            'filial_id':    group.filial_id,
            'filial_name':  group.filial.filial_name if group.filial else '',
            'org_id':       group.organization_id,
            'direction':    group.direction.name if group.direction else '',
            'year':         group.year,
            'month':        group.get_month_display(),
        }
    except (Group.DoesNotExist, Exception):
        return None


@sync_to_async
def get_students_by_group(group_id: int):
    """Guruhdagi barcha tinglovchilar ro'yxatini qaytaradi"""
    from apps.students.models import Group
    try:
        group = Group.objects.get(id=group_id)
        return [
            {'id': s.id, 'full_name': s.full_name}
            for s in group.students.all().order_by('full_name')
        ]
    except Exception:
        return []


@sync_to_async
def link_student_telegram(student_id: int, telegram_id: int):
    """Student ga telegram_id bog'lash"""
    from apps.students.models import Student
    try:
        student = Student.objects.get(id=student_id)
        student.telegram_id = telegram_id
        student.save(update_fields=['telegram_id'])
        return {
            'full_name': student.full_name,
            'login':     student.user.username if student.user else '',
            'password':  student.plain_password or '',
        }
    except Exception:
        return None


@sync_to_async
def register_student_to_group(telegram_id: int, full_name: str, group_id: int):
    """Tinglovchini guruhga qo'shish, Student va User yaratish"""
    from apps.students.models import Student, Group
    from django.contrib.auth.models import User
    import random

    group = Group.objects.get(id=group_id)

    # Student yaratish yoki topish
    student, created = Student.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'full_name':    full_name,
            'organization': group.organization,
            'filial':       group.filial,
        }
    )

    # Yangi student uchun user yaratish
    if created or not student.user_id:
        login    = str(student.pk).zfill(8)
        chars    = 'aeiou0123456789'
        password = ''.join(random.choices(chars, k=4))
        user     = User.objects.create_user(username=login, password=password)
        student.user           = user
        student.plain_password = password
        student.save(update_fields=['user', 'plain_password'])

    # Guruhga qo'shish
    already_in = group.students.filter(pk=student.pk).exists()
    if not already_in:
        group.students.add(student)

    return {
        'login':      student.user.username if student.user else '',
        'password':   student.plain_password or '',
        'already_in': already_in,
        'group_name': group.name,
    }


@sync_to_async
def set_telegram_user_organization(user_id: int, org_id: int) -> bool:
    """TelegramUser.organization ni saqlash (referal orqali kelinganda)"""
    try:
        tg_user = TelegramUser.objects.get(user_id=user_id)
        org = Organization.objects.get(id=org_id)
        tg_user.organization = org
        tg_user.save()
        return True
    except Exception as e:
        print(f"set_telegram_user_organization xatosi: {e}")
        return False


@sync_to_async
def get_or_create_telegram_user(user_id: int, username: str, first_name: str, last_name: str):
    """TelegramUser olish yoki yaratish"""
    obj, created = TelegramUser.objects.get_or_create(
        user_id=user_id,
        defaults={
            "username": username or "",
            "first_name": first_name or "",
            "last_name": last_name or "",
        }
    )
    return obj


@sync_to_async
def create_employee_with_filial(user_id: int, full_name: str, filial_id: int):
    """Xodim yaratish va filialga biriktirish"""
    try:
        emp, _ = Employee.objects.get_or_create(telegram_user_id=user_id)
        emp.name = full_name
        emp.filial_id = filial_id
        emp.save()
        return emp
    except Exception as e:
        print(f"create_employee_with_filial xatosi: {e}")
        return None


@sync_to_async
def save_work_schedule_by_weekday_names(
    employee_user_id: int,
    weekday_names: list,
    start_time,
    end_time,
    admin_telegram_id: int
):
    """WorkSchedule saqlash (hafta kunlari nomlari bo'yicha)"""
    try:
        employee = Employee.objects.filter(telegram_user_id=employee_user_id).first()
        if not employee:
            raise Exception(f"Xodim topilmadi: user_id={employee_user_id}")

        admin = Administrator.objects.filter(telegram_id=admin_telegram_id).first()
        weekdays = list(Weekday.objects.filter(name__in=weekday_names))

        ws = WorkSchedule.objects.create(
            employee=employee,
            start=start_time,
            end=end_time,
            admin=admin,
        )
        ws.weekday.set(weekdays)
        return ws
    except Exception as e:
        print(f"save_work_schedule_by_weekday_names xatosi: {e}")
        return None


async def set_user_organization(user_id: int, org_id: int):
    from apps.superadmin.models import Organization
    org = await sync_to_async(Organization.objects.get)(id=org_id)
    user = await get_telegram_user(user_id)
    if user:
        user.organization = org
        await sync_to_async(user.save)()


async def set_user_filial(user_id: int, filial_id: int):
    from apps.superadmin.models import Filial
    filial = await sync_to_async(Filial.objects.get)(id=filial_id)
    user = await get_telegram_user(user_id)
    if user:
        user.filial = filial
        await sync_to_async(user.save)()


# ============================================================
# XODIM RASM SAQLASH
# ============================================================

@sync_to_async
def save_employee_photo(user_id: int, photo_path: str) -> bool:
    """
    Xodimning yuz rasmini saqlaydi.
    photo_path — fayl tizimidagi to'liq yo'l (MEDIA_ROOT ichida).
    """
    try:
        employee = Employee.objects.filter(telegram_user_id=user_id).first()
        if not employee:
            return False
        # Eski rasmni o'chirish
        if employee.image:
            try:
                import os
                if os.path.exists(employee.image.path):
                    os.remove(employee.image.path)
            except Exception:
                pass
        employee.image = photo_path
        employee.save()
        return True
    except Exception as e:
        print(f"save_employee_photo xatosi: {e}")
        return False


@sync_to_async
def has_employee_photo(user_id: int) -> bool:
    """Xodimning rasmi borligini tekshiradi"""
    employee = Employee.objects.filter(telegram_user_id=user_id).first()
    if not employee:
        return False
    return bool(employee.image)


# ============================================================
# MAOSH / STATISTIKA
# ============================================================

@sync_to_async
def get_employee_monthly_stats(user_id: int, year: int, month: int) -> dict:
    """
    Xodimning berilgan oy bo'yicha statistikasi:
    - kelgan kunlar soni
    - jami ishlagan daqiqa (→ soat)
    - joriy oy uchun hozirgi holat
    - kerakli oylik soat (SalaryConfig dan)
    """
    from datetime import date, datetime
    import calendar as cal_mod
    from apps.main.models import Attendance, SalaryConfig

    employee = Employee.objects.filter(telegram_user_id=user_id).first()
    if not employee:
        return {}

    # Oyning birinchi va oxirgi kuni
    first_day = date(year, month, 1)
    last_day  = date(year, month, cal_mod.monthrange(year, month)[1])

    attendances = Attendance.objects.filter(
        employee=employee,
        date__gte=first_day,
        date__lte=last_day,
        check_in__isnull=False,
        check_out__isnull=False,
    )

    came_days   = 0
    total_minutes = 0

    for att in attendances:
        came_days += 1
        delta = datetime.combine(att.date, att.check_out) - \
                datetime.combine(att.date, att.check_in)
        total_minutes += max(0, int(delta.total_seconds() / 60))

    total_hours = round(total_minutes / 60, 1)

    # Kerakli oylik soat
    try:
        salary_cfg = SalaryConfig.objects.get(employee=employee)
        monthly_hours = salary_cfg.monthly_hours
    except SalaryConfig.DoesNotExist:
        monthly_hours = None

    # Ish kunlari soni (dushanba-juma, shanba emas)
    work_days_in_month = sum(
        1 for d in range(1, last_day.day + 1)
        if date(year, month, d).weekday() < 5
    )

    return {
        'year':              year,
        'month':             month,
        'month_name':        cal_mod.month_name[month],
        'came_days':         came_days,
        'work_days_in_month': work_days_in_month,
        'total_hours':       total_hours,
        'monthly_hours':     monthly_hours,
        'percent':           round(total_hours / monthly_hours * 100, 1) if monthly_hours else None,
    }


@sync_to_async
def get_available_months(user_id: int) -> list:
    """
    Xodimning davomat yozuvlari mavjud bo'lgan oylar ro'yxati.
    Oxirgi 6 oy, eng yangi birinchi.
    """
    from datetime import date
    from django.db.models.functions import TruncMonth

    employee = Employee.objects.filter(telegram_user_id=user_id).first()
    if not employee:
        return []

    months = (
        Attendance.objects.filter(employee=employee)
        .annotate(month=TruncMonth('date'))
        .values_list('month', flat=True)
        .distinct()
        .order_by('-month')[:6]
    )

    result = []
    for m in months:
        result.append({'year': m.year, 'month': m.month, 'month_name': m.strftime('%B %Y')})

    # Joriy oyni ham qo'shamiz (agar yo'q bo'lsa)
    today = date.today()
    if not any(r['year'] == today.year and r['month'] == today.month for r in result):
        import calendar as cal_mod
        result.insert(0, {
            'year': today.year,
            'month': today.month,
            'month_name': cal_mod.month_name[today.month] + f" {today.year} (joriy)"
        })

    return result


# ============================================================
# BOT HISOBOTLARI UCHUN FUNKSIYALAR
# ============================================================

_GRACE = 15  # daqiqa — kechikish grace period
_UZ_MONTHS = {
    1:'Yanvar', 2:'Fevral', 3:'Mart', 4:'Aprel', 5:'May', 6:'Iyun',
    7:'Iyul', 8:'Avgust', 9:'Sentabr', 10:'Oktabr', 11:'Noyabr', 12:'Dekabr',
}
_UZ_DAYS = {
    0:'Du', 1:'Se', 2:'Ch', 3:'Pa', 4:'Ju', 5:'Sh', 6:'Ya',
}


def _bot_compute_stats_sync(employee, start_date, end_date):
    """
    [start_date, end_date] uchun xodim statistikasini hisoblaydi.
    15 daqiqa grace period qo'llaniladi.
    """
    from apps.main.models import ScheduleDay, Attendance
    required_min = worked_min = late_total = overtime_total = 0
    current = start_date

    while current <= end_date:
        wd_name = current.strftime('%A')
        try:
            weekday_obj = Weekday.objects.get(name_en=wd_name)
        except Weekday.DoesNotExist:
            current += timedelta(days=1)
            continue

        sds = ScheduleDay.objects.filter(
            schedule__employees=employee, weekday=weekday_obj
        ).select_related('schedule__location')

        counted = set()
        day_late = day_ot = 0

        for sd in sds:
            req = int((
                datetime.combine(current, sd.end) -
                datetime.combine(current, sd.start)
            ).total_seconds() / 60)
            required_min += max(0, req)

            att = Attendance.objects.filter(
                employee=employee, date=current, location=sd.schedule.location
            ).first()
            if att is None:
                att = Attendance.objects.filter(
                    employee=employee, date=current
                ).exclude(id__in=counted).first()

            if att and att.id not in counted:
                counted.add(att.id)
                if att.check_in and att.check_out:
                    d = datetime.combine(current, att.check_out) - \
                        datetime.combine(current, att.check_in)
                    worked_min += max(0, int(d.total_seconds() / 60))

            if att and att.check_in:
                diff = int((
                    datetime.combine(current, att.check_in) -
                    datetime.combine(current, sd.start)
                ).total_seconds() / 60)
                if diff > _GRACE:
                    day_late = max(day_late, diff)

            if att and att.check_out:
                ot = int((
                    datetime.combine(current, att.check_out) -
                    datetime.combine(current, sd.end)
                ).total_seconds() / 60)
                if ot > 0:
                    day_ot += ot

        late_total += day_late
        overtime_total += day_ot
        current += timedelta(days=1)

    req_h = required_min / 60
    wrk_h = worked_min / 60
    progress = min(150, round(wrk_h / req_h * 100, 1)) if req_h > 0 else 0.0

    return {
        'required_h': round(req_h, 1),
        'worked_h':   round(wrk_h, 1),
        'progress':   progress,
        'late_total': late_total,
        'late_h':     late_total // 60,
        'late_m':     late_total % 60,
        'overtime_total': overtime_total,
        'overtime_h': overtime_total // 60,
        'overtime_m': overtime_total % 60,
    }


@sync_to_async
def get_emp_weekly_monthly_stats(user_id: int) -> dict:
    """
    Xodimning haftalik va oylik statistikasini qaytaradi.
    Bot "Hisobotlar" overview uchun.
    """
    employee = Employee.objects.filter(telegram_user_id=user_id).first()
    if not employee:
        return {}

    today = date.today()
    week_start  = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    weekly  = _bot_compute_stats_sync(employee, week_start, today)
    monthly = _bot_compute_stats_sync(employee, month_start, today)

    return {
        'weekly':      weekly,
        'monthly':     monthly,
        'week_start':  week_start,
        'month_start': month_start,
        'today':       today,
        'month_label': f"{_UZ_MONTHS[today.month]} {today.year}",
        'employee_name': employee.name,
    }


@sync_to_async
def get_emp_stats_period(user_id: int, start_date, end_date) -> dict:
    """
    Xodimning berilgan davr uchun statistikasi (sana bo'yicha hisobot).
    """
    employee = Employee.objects.filter(telegram_user_id=user_id).first()
    if not employee:
        return {}
    stats = _bot_compute_stats_sync(employee, start_date, end_date)
    stats['employee_name'] = employee.name
    return stats


@sync_to_async
def get_emp_daily_report_month(user_id: int, year: int, month: int) -> list:
    """
    Xodimning berilgan oy uchun kunlik davomat jadvali.
    """
    import calendar as cal_mod
    from apps.main.models import ScheduleDay, Attendance

    employee = Employee.objects.filter(telegram_user_id=user_id).first()
    if not employee:
        return []

    first_day = date(year, month, 1)
    last_day  = date(year, month, cal_mod.monthrange(year, month)[1])
    end       = min(last_day, date.today())

    rows = []
    current = first_day

    while current <= end:
        wd_name = current.strftime('%A')
        try:
            weekday_obj = Weekday.objects.get(name_en=wd_name)
        except Weekday.DoesNotExist:
            current += timedelta(days=1)
            continue

        sds = ScheduleDay.objects.filter(
            schedule__employees=employee, weekday=weekday_obj
        ).select_related('schedule__location')

        if not sds.exists():
            current += timedelta(days=1)
            continue

        counted = set()
        for sd in sds:
            att = Attendance.objects.filter(
                employee=employee, date=current, location=sd.schedule.location
            ).first()
            if att is None:
                att = Attendance.objects.filter(
                    employee=employee, date=current
                ).exclude(id__in=counted).first()

            check_in  = att.check_in  if att else None
            check_out = att.check_out if att else None

            if att and att.id not in counted:
                counted.add(att.id)

            worked_min = 0
            if check_in and check_out:
                d = datetime.combine(current, check_out) - \
                    datetime.combine(current, check_in)
                worked_min = max(0, int(d.total_seconds() / 60))

            late_min = 0
            if check_in:
                diff = int((
                    datetime.combine(current, check_in) -
                    datetime.combine(current, sd.start)
                ).total_seconds() / 60)
                if diff > _GRACE:
                    late_min = diff

            rows.append({
                'date':      current,
                'day_uz':    _UZ_DAYS.get(current.weekday(), ''),
                'status':    'Kelgan' if att else 'Kelmagan',
                'check_in':  check_in,
                'check_out': check_out,
                'sch_start': sd.start,
                'sch_end':   sd.end,
                'worked_h':  worked_min // 60,
                'worked_m':  worked_min % 60,
                'late_min':  late_min,
            })

        current += timedelta(days=1)

    return rows


@sync_to_async
def get_emp_late_days_month(user_id: int, year: int, month: int) -> list:
    """
    Xodimning berilgan oyda kechikkan kunlari.
    15 daqiqagacha kechiriladi.
    """
    import calendar as cal_mod
    from apps.main.models import ScheduleDay, Attendance

    employee = Employee.objects.filter(telegram_user_id=user_id).first()
    if not employee:
        return []

    first_day = date(year, month, 1)
    last_day  = date(year, month, cal_mod.monthrange(year, month)[1])
    end       = min(last_day, date.today())

    late_days = []
    current = first_day

    while current <= end:
        wd_name = current.strftime('%A')
        try:
            weekday_obj = Weekday.objects.get(name_en=wd_name)
        except Weekday.DoesNotExist:
            current += timedelta(days=1)
            continue

        sds = ScheduleDay.objects.filter(
            schedule__employees=employee, weekday=weekday_obj
        )
        if not sds.exists():
            current += timedelta(days=1)
            continue

        day_late = 0
        for sd in sds:
            att = Attendance.objects.filter(
                employee=employee, date=current
            ).first()
            if att and att.check_in:
                diff = int((
                    datetime.combine(current, att.check_in) -
                    datetime.combine(current, sd.start)
                ).total_seconds() / 60)
                if diff > _GRACE:
                    day_late = max(day_late, diff)

        if day_late > 0:
            late_days.append({
                'date':    current,
                'day_uz':  _UZ_DAYS.get(current.weekday(), ''),
                'late_min': day_late,
                'late_h':  day_late // 60,
                'late_m':  day_late % 60,
            })

        current += timedelta(days=1)

    return late_days


@sync_to_async
def get_report_months_for_employee(user_id: int) -> list:
    """
    Hisobot uchun oylar ro'yxati (joriy + oxirgi 5 oy).
    """
    from django.db.models.functions import TruncMonth
    import calendar as cal_mod

    employee = Employee.objects.filter(telegram_user_id=user_id).first()
    if not employee:
        return []

    months = (
        Attendance.objects.filter(employee=employee)
        .annotate(month=TruncMonth('date'))
        .values_list('month', flat=True)
        .distinct()
        .order_by('-month')[:5]
    )

    result = []
    for m in months:
        result.append({
            'year': m.year, 'month': m.month,
            'label': f"{_UZ_MONTHS[m.month]} {m.year}",
        })

    today = date.today()
    if not any(r['year'] == today.year and r['month'] == today.month for r in result):
        result.insert(0, {
            'year': today.year, 'month': today.month,
            'label': f"{_UZ_MONTHS[today.month]} {today.year} (joriy)",
        })

    return result


# ============================================================
# TINGLOVCHI DAVOMAT FUNKSIYALARI
# ============================================================

PARA_DURATION_MINUTES = 80


def _get_lesson_times(group, today):
    """
    Guruh va sanaga mos dars vaqtlarini qaytaradi.

    Qaytaradi: (expected_start, expected_end, lesson) yoki (None, None, None)

    Ustuvorlik tartibi:
      1. GroupLesson (muayyan kun uchun) → smena → para vaqtlari
      2. GroupSchedule (haftalik jadval) → start_time / end_time
    """
    from apps.students.models import GroupLesson, GroupSchedule
    from datetime import datetime, timedelta
    from django.db import models

    # ── 1. Muayyan kun uchun GroupLesson ──────────────────────
    lesson = GroupLesson.objects.filter(group=group, date=today).select_related('smena').first()
    if lesson and lesson.smena:
        smena = lesson.smena
        # Birinchi para = kirish vaqti
        expected_start = smena.para1_start
        # Oxirgi para + 80 daqiqa = chiqish vaqti
        last_para = smena.para3_start or smena.para2_start or smena.para1_start
        expected_end = (
            datetime.combine(today, last_para) + timedelta(minutes=PARA_DURATION_MINUTES)
        ).time()
        return expected_start, expected_end, lesson

    # ── 2. Haftalik GroupSchedule (fallback) ──────────────────
    # Bugungi hafta kuni nomi (Weekday modeli bilan solishtirish uchun)
    uz_weekdays = {
        0: 'Dushanba', 1: 'Seshanba', 2: 'Chorshanba',
        3: 'Payshanba', 4: 'Juma',    5: 'Shanba',    6: 'Yakshanba',
    }
    weekday_name = uz_weekdays.get(today.weekday())
    schedule = GroupSchedule.objects.filter(
        group=group,
        is_active=True,
        weekdays__name=weekday_name,
    ).filter(
        models.Q(date_from__isnull=True) | models.Q(date_from__lte=today),
        models.Q(date_to__isnull=True)   | models.Q(date_to__gte=today),
    ).first()

    if schedule:
        return schedule.start_time, schedule.end_time, None

    return None, None, None


@sync_to_async
def student_mark_check_in(telegram_id: int) -> dict:
    """
    Tinglovchini bugungi darsga keldi deb belgilash.
    Kechikish dars jadvali/smenasiga qarab hisoblanadi.
    Hech qanday xabar yuborilmaydi — faqat DB ga yoziladi.
    """
    from apps.students.models import Student, StudentAttendance
    from datetime import date, datetime

    try:
        student = Student.objects.get(telegram_id=telegram_id)
    except Student.DoesNotExist:
        return {'ok': False, 'error': 'student_not_found'}

    today = date.today()
    now_time = datetime.now().time()

    # Bugungi dars guruhi — avval GroupLesson'da, keyin birinchi guruh
    group = student.groups.filter(lessons__date=today).first()
    if not group:
        group = student.groups.first()
    if not group:
        return {'ok': False, 'error': 'no_group'}

    # Allaqachon kirganligi tekshirish
    existing = StudentAttendance.objects.filter(
        student=student, group=group, date=today, check_in__isnull=False
    ).first()
    if existing:
        return {
            'ok': False,
            'error': 'already_checked_in',
            'time': existing.check_in.strftime('%H:%M'),
        }

    # Jadval vaqtlarini aniqlash
    expected_start, expected_end, lesson = _get_lesson_times(group, today)

    # Kechikishni hisoblash
    late_minutes = 0
    status = 'present'
    if expected_start:
        now_dt = datetime.combine(today, now_time)
        exp_dt = datetime.combine(today, expected_start)
        if now_dt > exp_dt:
            late_minutes = int((now_dt - exp_dt).total_seconds() / 60)
            status = 'late'

    # Attendance yozish (mavjud bo'lsa yangilash, bo'lmasa yaratish)
    attendance, created = StudentAttendance.objects.get_or_create(
        student=student,
        group=group,
        date=today,
        defaults={
            'check_in': now_time,
            'status': status,
            'late_minutes': late_minutes,
        }
    )
    if not created:
        attendance.check_in = now_time
        attendance.status = status
        attendance.late_minutes = late_minutes
        attendance.save(update_fields=['check_in', 'status', 'late_minutes'])

    return {
        'ok': True,
        'time': now_time.strftime('%H:%M'),
        'full_name': student.full_name,
        'late_minutes': late_minutes,
        'expected_start': expected_start.strftime('%H:%M') if expected_start else None,
    }


@sync_to_async
def student_mark_check_out(telegram_id: int) -> dict:
    """
    Tinglovchini bugungi darsdan ketdi deb belgilash.
    Erta ketish dars jadvali/smenasiga qarab hisoblanadi.
    Hech qanday xabar yuborilmaydi — faqat DB ga yoziladi.
    """
    from apps.students.models import Student, StudentAttendance
    from datetime import date, datetime

    try:
        student = Student.objects.get(telegram_id=telegram_id)
    except Student.DoesNotExist:
        return {'ok': False, 'error': 'student_not_found'}

    today = date.today()
    now_time = datetime.now().time()

    # Bugungi kirish yozuvini topish
    attendance = StudentAttendance.objects.filter(
        student=student, date=today, check_in__isnull=False
    ).select_related('group').first()

    if not attendance:
        return {'ok': False, 'error': 'not_checked_in'}
    if attendance.check_out:
        return {
            'ok': False,
            'error': 'already_checked_out',
            'time': attendance.check_out.strftime('%H:%M'),
        }

    # Jadval vaqtlarini aniqlash
    expected_start, expected_end, lesson = _get_lesson_times(attendance.group, today)

    # Erta ketishni hisoblash
    early_leave_minutes = 0
    if expected_end:
        now_dt = datetime.combine(today, now_time)
        exp_end_dt = datetime.combine(today, expected_end)
        if now_dt < exp_end_dt:
            early_leave_minutes = int((exp_end_dt - now_dt).total_seconds() / 60)

    attendance.check_out = now_time
    attendance.early_leave_minutes = early_leave_minutes
    attendance.save(update_fields=['check_out', 'early_leave_minutes'])

    return {
        'ok': True,
        'time': now_time.strftime('%H:%M'),
        'full_name': student.full_name,
        'early_leave_minutes': early_leave_minutes,
        'expected_end': expected_end.strftime('%H:%M') if expected_end else None,
    }


@sync_to_async
def has_student_photo(telegram_id: int) -> bool:
    """Tinglovchining yuz rasmi saqlanganligini tekshiradi"""
    from apps.students.models import Student
    student = Student.objects.filter(telegram_id=telegram_id).first()
    if not student:
        return False
    return bool(student.face_image and student.face_verified)


@sync_to_async
def save_student_face_photo(telegram_id: int, photo_path: str) -> bool:
    """Tinglovchi yuz rasmini saqlash va face_verified=True qo'yish"""
    from apps.students.models import Student
    try:
        student = Student.objects.get(telegram_id=telegram_id)
        # Eski rasmni o'chirish
        if student.face_image:
            try:
                old_path = student.face_image.path
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception:
                pass
        student.face_image = photo_path
        student.face_verified = True
        student.save(update_fields=['face_image', 'face_verified'])
        return True
    except Exception as e:
        print(f"save_student_face_photo xatosi: {e}")
        return False


@sync_to_async
def get_student_by_telegram_id(telegram_id: int):
    """Telegram ID bo'yicha tinglovchini qaytaradi"""
    from apps.students.models import Student
    try:
        s = Student.objects.get(telegram_id=telegram_id)
        return {'id': s.id, 'full_name': s.full_name, 'face_image': s.face_image.name if s.face_image else None}
    except Student.DoesNotExist:
        return None


@sync_to_async
def save_student_face_photo(telegram_id: int, photo_path: str) -> bool:
    """Tinglovchi yuz rasmini saqlash"""
    from apps.students.models import Student
    try:
        student = Student.objects.get(telegram_id=telegram_id)
        student.face_image = photo_path
        student.face_verified = True
        student.save(update_fields=['face_image', 'face_verified'])
        return True
    except Exception:
        return False
