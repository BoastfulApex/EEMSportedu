from django.contrib import admin
from .models import *


admin.site.register(Weekday)
admin.site.register(Employee)
admin.site.register(WorkSchedule)
admin.site.register(Schedule)
admin.site.register(ScheduleDay)
admin.site.register(InviteToken)