from django.urls import path
from . import views
from .api_views import StudentCheckAPIView

urlpatterns = [
    # Tinglovchi davomat web app va API
    path('web_app/', views.student_web_app, name='student_web_app'),
    path('api/check/', StudentCheckAPIView.as_view(), name='student-check'),

    # Guruhlar
    path('groups/', views.groups_list, name='groups_list'),
    path('groups/create/', views.group_create, name='group_create'),
    path('groups/<int:pk>/', views.group_detail, name='group_detail'),
    path('groups/<int:pk>/delete/', views.GroupDelete.as_view(), name='group_delete'),

    # Yo'nalishlar
    path('directions/', views.directions_list, name='directions_list'),
    path('directions/create/', views.direction_create, name='direction_create'),
    path('directions/<int:pk>/', views.direction_detail, name='direction_detail'),
    path('directions/<int:pk>/delete/', views.DirectionDelete.as_view(), name='direction_delete'),

    # Guruh tinglovchilari
    path('groups/<int:pk>/students/', views.group_students, name='group_students'),
    path('groups/<int:pk>/students/export/', views.group_students_export, name='group_students_export'),
    path('groups/<int:pk>/students/<int:student_pk>/remove/', views.group_student_remove, name='group_student_remove'),

    # Taklif havolalari
    path('invites/', views.invite_links, name='invite_links'),
    path('invites/<int:pk>/regenerate/', views.regenerate_invite_token, name='regenerate_invite_token'),

    # Smenalar
    path('smenas/', views.smenas_list, name='smenas_list'),
    path('smenas/create/', views.smena_create, name='smena_create'),
    path('smenas/<int:pk>/', views.smena_detail, name='smena_detail'),
    path('smenas/<int:pk>/delete/', views.SmenaDelete.as_view(), name='smena_delete'),

    # Guruh jadvali (kalendar)
    path('groups/<int:pk>/schedule/', views.group_schedule, name='group_schedule'),
    path('groups/<int:pk>/schedule/save/', views.save_group_lessons, name='save_group_lessons'),
    path('groups/<int:pk>/schedule/<str:date_str>/delete/', views.delete_group_lesson, name='delete_group_lesson'),

    # Hisobot
    path('reports/', views.student_report, name='student_report'),

    # AJAX
    path('ajax/directions/', views.directions_by_filial, name='directions_by_filial'),

    # Telegram ID tozalash
    path('telegram-reset/', views.student_telegram_reset, name='student_telegram_reset'),
    path('telegram-reset/<int:pk>/confirm/', views.student_telegram_reset_confirm, name='student_telegram_reset_confirm'),
]
