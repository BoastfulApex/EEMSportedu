from django.urls import path
from .views import index
from apps.main.api_views import SimpleCheckAPIView, TestDataUploadAPIView, GenerateAttendanceAPIView


urlpatterns = [

    path('', index, name='web_app_page_home'),
    path('api/check/', SimpleCheckAPIView.as_view(), name='simple-check'),
    path('api/test-upload/', TestDataUploadAPIView.as_view(), name='test-upload'),
    path('api/generate-attendance/', GenerateAttendanceAPIView.as_view(), name='generate-attendance'),
]
