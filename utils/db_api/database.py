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
        user = Employee.objects.filter(user_id=user_id).first()
        return user
    except:
        return None


@sync_to_async
def add_employee(user_id, full_name, admin_id):
    # try:
    Employee.objects.create(user_id=user_id, name=full_name).save()
    admin = Administrator.objects.filter(telegram_id=admin_id).first()
    emp = Employee.objects.filter(user_id=user_id).first()
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
    return Employee.objects.filter(user_id=user_id).exists()


@sync_to_async
def is_user_admin(user_id: int) -> bool:
    return Administrator.objects.filter(telegram_id=user_id).exists()


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
    if not Employee.objects.filter(user_id=user_id).exists():
        Employee.objects.create(user_id=user_id, full_name=full_name)
        

@sync_to_async
def get_all_weekdays():
    return list(Weekday.objects.all())


@sync_to_async
def save_work_schedule(user_id, data):
    admin = Administrator.objects.filter(telegram_id=user_id).first()

    employee = Employee.objects.filter(user_id=data["employee_id"]).first()
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
    employee = Employee.objects.filter(user_id=user_id).first()
    if employee:
        employee.delete()
        return True  # O'chirildi
    return False  # Topilmadi


@sync_to_async
def get_employee_schedule_text(employee_id: int) -> str:
    try:
        emp = Employee.objects.filter(user_id=employee_id).first()
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
    employee = Employee.objects.filter(user_id=emp_user_id).first()
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
        emp, _ = Employee.objects.get_or_create(user_id=user_id)
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
        employee = Employee.objects.filter(user_id=employee_user_id).first()
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
        employee = Employee.objects.filter(user_id=user_id).first()
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
    employee = Employee.objects.filter(user_id=user_id).first()
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

    employee = Employee.objects.filter(user_id=user_id).first()
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

    employee = Employee.objects.filter(user_id=user_id).first()
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
