from django.urls import path
from apps.superadmin import views

urlpatterns = [

    path('filials/', views.filials, name='admin_filials'),
    path('filial_create/', views.filial_create, name='admin_filial_create'),
    path('filial/<int:pk>', views.filial_detail, name='admin_filial_update'),
    path('filial_delete/<int:pk>', views.FilialDelete.as_view(), name='admin_filial_delete'),
    path('admins/', views.admin_list, name='admin_adminstrators'),
    path('admins/create/', views.admin_create, name='admin_adminstrator_create'),
    path('admins/<int:pk>/', views.admin_detail, name='admin_adminstrator_detail'),
    path('admins/<int:pk>/delete/', views.AdminstratorDeleteView.as_view(), name='admin_adminstrator_delete'),
    path('select-filial/<str:filial_id>/', views.select_filial, name='admin_select_filial'),
    path('locations/', views.locations, name='admin_locations'),
    path('ajax/create-location/', views.create_location_ajax, name='create_location_ajax'),
    path('locations/create', views.create_location, name='admin_create_location'),
    path('locations/<int:pk>/delete/', views.LocationDeleteView.as_view(), name='admin_location_delete'),

    # ── Filial admin — o'z filiali uchun sub-adminlar ──────────────────────────
    path('my-admins/',                 views.filial_admin_list,                     name='filial_admin_list'),
    path('my-admins/create/',          views.filial_admin_create,                   name='filial_admin_create'),
    path('my-admins/<int:pk>/',        views.filial_admin_detail,                   name='filial_admin_detail'),
    path('my-admins/<int:pk>/delete/', views.FilialSubAdminDeleteView.as_view(),    name='filial_admin_delete'),
    path('tg-search/',                 views.filial_telegram_search,                name='filial_telegram_search'),

    # Referal havolalar
    path('referral-links/', views.referral_links, name='referral_links'),
    path('referral-links/<int:filial_id>/regenerate/', views.regenerate_invite_token, name='regenerate_invite_token'),
]
