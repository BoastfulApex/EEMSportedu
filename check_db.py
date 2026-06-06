import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.students.models import StudentAttendance
import datetime

today = datetime.date.today()

total       = StudentAttendance.objects.count()
with_out    = StudentAttendance.objects.filter(check_out__isnull=False).count()
today_total = StudentAttendance.objects.filter(date=today).count()
today_out   = StudentAttendance.objects.filter(date=today, check_out__isnull=False).count()

with open('check_db_result.txt', 'w', encoding='utf-8') as f:
    f.write(f"=== StudentAttendance statistika ===\n")
    f.write(f"Jami yozuv:          {total}\n")
    f.write(f"check_out bor:       {with_out}\n")
    f.write(f"check_out yo'q:      {total - with_out}\n")
    f.write(f"\nBugun ({today}):\n")
    f.write(f"  Jami:              {today_total}\n")
    f.write(f"  check_out bor:     {today_out}\n")
    f.write(f"  check_out yo'q:    {today_total - today_out}\n")

    # So'nggi 5 ta check_out yozuv
    last_outs = StudentAttendance.objects.filter(
        check_out__isnull=False
    ).order_by('-date', '-check_out').select_related('student')[:5]

    f.write(f"\nOxirgi 5 ta check_out:\n")
    for a in last_outs:
        f.write(f"  {a.date} | {a.student.full_name} | in:{a.check_in} out:{a.check_out}\n")

print("Natija check_db_result.txt ga yozildi")
