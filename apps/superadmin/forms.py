from django import forms
from django.contrib.auth.models import User
from .models import Administrator, Filial


class FilialForm(forms.ModelForm):
    filial_name = forms.CharField(
        widget=forms.TextInput(attrs={
            "placeholder": "Nomi",
            "class": "form-control",
        })
    )

    class Meta:
        model = Filial
        fields = '__all__'


class AdminUserForm(forms.ModelForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Foydalanuvchi nomi"
        })
    )
    password = forms.CharField(
        label="Parol",
        required=False,
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Parol kiriting (o'zgartirmasangiz bo'sh qoldiring)"
        })
    )
    telegram_id = forms.IntegerField(
        label="Telegram ID (user_id)",
        required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Telegram user_id"
        })
    )
    full_name = forms.CharField(
        label="To'liq ism",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ism Familiya"
        })
    )
    filial = forms.ModelChoiceField(
        queryset=Filial.objects.none(),
        label="Filial",
        required=False,
        widget=forms.Select(attrs={"class": "form-control"})
    )
    role = forms.ChoiceField(
        label="Rol",
        choices=Administrator.ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = Administrator
        fields = ['telegram_id', 'full_name', 'filial', 'role']

    def __init__(self, *args, **kwargs):
        admin_user = kwargs.pop('admin_user', None)
        super().__init__(*args, **kwargs)

        # Mavjud instance uchun username ni to'ldirish
        if self.instance and hasattr(self.instance, 'user') and self.instance.user_id:
            self.fields['username'].initial = self.instance.user.username

        if admin_user and hasattr(admin_user, 'organization'):
            self.fields['filial'].queryset = Filial.objects.filter(
                organization=admin_user.organization
            )
        else:
            self.fields['filial'].queryset = Filial.objects.none()

    def save(self, commit=True):
        # Mavjud instance bormi?
        if self.instance and self.instance.pk and hasattr(self.instance, 'user') and self.instance.user_id:
            user = self.instance.user
            user.username = self.cleaned_data['username']
            user.first_name = self.cleaned_data['full_name']
            if self.cleaned_data.get('password'):
                user.set_password(self.cleaned_data['password'])
            user.is_staff = True
            user.is_superuser = False
            if commit:
                user.save()
        else:
            # Yangi user yaratish
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                password=self.cleaned_data['password'],
                first_name=self.cleaned_data['full_name'],
            )
            user.is_staff = True
            user.is_superuser = False
            if commit:
                user.save()

        admin = super().save(commit=False)
        admin.user = user
        admin.telegram_id = self.cleaned_data.get('telegram_id')
        admin.full_name = self.cleaned_data['full_name']
        admin.filial = self.cleaned_data.get('filial')
        admin.role = self.cleaned_data['role']
        if commit:
            admin.save()
        return admin


# ── Filial admin uchun: faqat hr/edu/monitoring yaratadi ──────────────────────

class FilialSubAdminForm(forms.ModelForm):
    """
    filial_admin o'z filiali uchun hr_admin / edu_admin / monitoring yaratadi.
    Filial maydoni yo'q — view da avtomatik o'rnatiladi.
    """
    SUB_ROLE_CHOICES = [
        ('hr_admin',   "Xodimlar Bo'limi"),
        ('edu_admin',  "O'quv Bo'limi"),
        ('monitoring', "Monitoring Bo'limi"),
    ]

    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Foydalanuvchi nomi"})
    )
    password = forms.CharField(
        label="Parol",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Parol (o'zgartirmasa bo'sh)"})
    )
    full_name = forms.CharField(
        label="To'liq ism",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ism Familiya"})
    )
    telegram_id = forms.IntegerField(
        label="Telegram ID",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Telegram user_id"})
    )
    role = forms.ChoiceField(
        label="Rol",
        choices=SUB_ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = Administrator
        fields = ['telegram_id', 'full_name', 'role']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user_id:
            self.fields['username'].initial = self.instance.user.username

    def save(self, commit=True, filial=None, organization=None):
        if self.instance and self.instance.pk and self.instance.user_id:
            user = self.instance.user
            user.username = self.cleaned_data['username']
            user.first_name = self.cleaned_data['full_name']
            if self.cleaned_data.get('password'):
                user.set_password(self.cleaned_data['password'])
            if commit:
                user.save()
        else:
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                password=self.cleaned_data['password'],
                first_name=self.cleaned_data['full_name'],
            )
            user.is_staff = True
            if commit:
                user.save()

        admin_obj = super().save(commit=False)
        admin_obj.user        = user
        admin_obj.full_name   = self.cleaned_data['full_name']
        admin_obj.telegram_id = self.cleaned_data.get('telegram_id')
        admin_obj.role        = self.cleaned_data['role']
        if filial:
            admin_obj.filial = filial
        if organization:
            admin_obj.organization = organization
        if commit:
            admin_obj.save()
        return admin_obj
