from django import forms
from apps.main.models import Employee, WorkSchedule, ExtraSchedule, Location, Attendance, Schedule, ScheduleDay
from apps.superadmin.models import Weekday, Filial


class ScheduleForm(forms.ModelForm):
    """Tayyor jadval shabloni yaratish/tahrirlash formi (faqat name + location)"""
    name = forms.CharField(
        label="Jadval nomi",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Masalan: Asosiy jadval"})
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Lokatsiya",
        required=False,
        empty_label="— Tanlang —"
    )

    class Meta:
        model = Schedule
        fields = ['name', 'location']

    def __init__(self, *args, **kwargs):
        filial = kwargs.pop('filial', None)
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if filial and filial.organization:
            self.fields['location'].queryset = Location.objects.filter(
                organization=filial.organization
            )
        elif organization:
            self.fields['location'].queryset = Location.objects.filter(organization=organization)
        else:
            self.fields['location'].queryset = Location.objects.none()


class EmployeeForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={
            "placeholder": "Ism",
            "class": "form-control",
        })
    )
    telegram_user_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            "placeholder": "Telegram UserID",
            "class": "form-control",
        })
    )
    employee_type = forms.ChoiceField(
        choices=Employee.EMPLOYEE_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"})
    )
    image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"})
    )
    schedules = forms.ModelMultipleChoiceField(
        queryset=Schedule.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        label="Jadvallar"
    )

    class Meta:
        model = Employee
        fields = ['name', 'telegram_user_id', 'employee_type', 'image', 'schedules']

    def __init__(self, *args, **kwargs):
        filial = kwargs.pop('filial', None)
        super().__init__(*args, **kwargs)
        if filial:
            self.fields['schedules'].queryset = Schedule.objects.filter(filial=filial)
        else:
            self.fields['schedules'].queryset = Schedule.objects.all()


class AttendanceDateRangeForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            "class": "form-control datepicker",
            "placeholder": "Boshlanish sanasi"
        })
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            "class": "form-control datepicker",
            "placeholder": "Tugash sanasi"
        })
    )


class LocationForm(forms.ModelForm):
    filial = forms.ModelChoiceField(
        queryset=Filial.objects.none(),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )
    name = forms.CharField(
        label="Lokatsiya nomi",
        widget=forms.TextInput(attrs={
            "placeholder": "Masalan: Asosiy bino, 3-xona",
            "class": "form-control",
        }),
        required=True,
    )
    address = forms.CharField(
        label="Manzil (xaritadan avtomatik)",
        widget=forms.TextInput(attrs={
            "placeholder": "Xaritadan nuqta tanlang",
            "class": "form-control",
            "readonly": "readonly",
        }),
        required=False,
    )
    latitude = forms.FloatField(widget=forms.HiddenInput())
    longitude = forms.FloatField(widget=forms.HiddenInput())

    class Meta:
        model = Location
        fields = ['filial', 'name', 'latitude', 'longitude']

    def __init__(self, *args, **kwargs):
        admin_user = kwargs.pop('admin_user', None)
        super().__init__(*args, **kwargs)
        if admin_user and hasattr(admin_user, 'organization'):
            self.fields['filial'].queryset = Filial.objects.filter(
                organization=admin_user.organization
            )
        else:
            self.fields['filial'].queryset = Filial.objects.none()


class SalaryConfigForm(forms.ModelForm):
    monthly_hours = forms.FloatField(
        label="Oylik kerakli soat",
        initial=168,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Masalan: 168",
            "step": "0.5",
        })
    )
    monthly_salary = forms.DecimalField(
        label="Oylik oklad (so'm)",
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Masalan: 3000000",
        })
    )

    class Meta:
        from apps.main.models import SalaryConfig
        model = SalaryConfig
        fields = ["monthly_hours", "monthly_salary"]
