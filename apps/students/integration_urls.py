"""
LMS integratsiyasi endpointlari.

Bular `core/urls.py` da ROOT ga (`/api/integration/`) ulanadi — `apps.students.urls`
`students/` prefiksi bilan ulangani uchun, shartnomadagi manzilni saqlash maqsadida
alohida ajratilgan.
"""
from django.urls import path

from .api_views import IntegrationAttendanceAPIView

urlpatterns = [
    path('attendance/', IntegrationAttendanceAPIView.as_view(), name='integration-attendance'),
]
