from django.urls import path
from . import views

urlpatterns = [
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

    # AJAX
    path('ajax/directions/', views.directions_by_filial, name='directions_by_filial'),
]
