from django.urls import path 
from .views import index
from apps.main.api_views import SimpleCheckAPIView


urlpatterns = [

    path('', index, name='web_app_page_home'),
    path('api/check/', SimpleCheckAPIView.as_view(), name='simple-check'),]
