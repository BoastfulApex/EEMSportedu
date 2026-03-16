from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from .models import Administrator, Organization, Filial
from apps.main.models import Location


# ── Org Admin yaratish uchun custom form ──────────────────────────────────────

class OrgAdminCreateForm(forms.ModelForm):
    """
    Django admin orqali org_admin yaratish:
    username + parol shu formada kiritiladi, User avtomatik yaratiladi.
    """
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"class": "vTextField"}),
    )
    password = forms.CharField(
        label="Parol",
        widget=forms.PasswordInput(attrs={"class": "vTextField"}),
    )

    class Meta:
        model = Administrator
        fields = ['username', 'password', 'full_name', 'organization', 'telegram_id']

    def save(self, commit=True):
        username  = self.cleaned_data['username']
        password  = self.cleaned_data['password']
        full_name = self.cleaned_data['full_name']

        # User doim saqlanadi — Django admin commit=False bilan chaqirganda ham.
        # (save_form → commit=False, save_model → obj.save() oqimi)
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=full_name,
            is_staff=True,
        )

        admin_obj = super().save(commit=False)
        admin_obj.user      = user
        admin_obj.role      = 'org_admin'
        admin_obj.full_name = full_name
        if commit:
            admin_obj.save()
        return admin_obj


@admin.register(Administrator)
class AdministratorAdmin(admin.ModelAdmin):
    add_form      = OrgAdminCreateForm
    list_display  = ['full_name', 'get_username', 'role', 'organization', 'filial']
    list_filter   = ['role', 'organization']
    search_fields = ['full_name', 'user__username']

    def get_username(self, obj):
        return obj.user.username if obj.user_id else '-'
    get_username.short_description = 'Username'

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            return self.add_form
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return ['username', 'password', 'full_name', 'organization', 'telegram_id']
        return ['user', 'full_name', 'organization', 'filial', 'role', 'telegram_id']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display  = ['name', 'created_at']
    search_fields = ['name']


@admin.register(Filial)
class FilialAdmin(admin.ModelAdmin):
    list_display  = ['filial_name', 'organization']
    list_filter   = ['organization']
    search_fields = ['filial_name']


admin.site.register(Location)
