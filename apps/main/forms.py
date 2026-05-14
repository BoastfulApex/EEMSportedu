from django import forms
from django.forms import inlineformset_factory
from apps.main.models import Employee, WorkSchedule, ExtraSchedule, Location, Attendance, Schedule, ScheduleDay, PublicHoliday, EmployeeDailySchedule, EmployeeDailyExtraShift
from apps.superadmin.models import Weekday, Filial


class ScheduleForm(forms.ModelForm):
    """Tayyor jadval shabloni yaratish/tahrirlash formi"""
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
    lunch_start = forms.TimeField(
        label="Tushlik boshlanishi",
        required=False,
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"})
    )
    lunch_end = forms.TimeField(
        label="Tushlik tugashi",
        required=False,
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"})
    )

    class Meta:
        model = Schedule
        fields = ['name', 'location', 'lunch_start', 'lunch_end']

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


class AssignScheduleForm(forms.Form):
    """Xodimga jadval biriktirish + qaysi sanadan boshlanishini belgilash"""
    schedule = forms.ModelChoiceField(
        queryset=Schedule.objects.none(),
        label="Jadval",
        empty_label="— Jadval tanlang —",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    from_date = forms.DateField(
        label="Qaysi sanadan boshlansin",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )

    def __init__(self, *args, **kwargs):
        filial = kwargs.pop('filial', None)
        super().__init__(*args, **kwargs)
        if filial:
            self.fields['schedule'].queryset = Schedule.objects.filter(
                filial=filial
            ).order_by('name')
        else:
            self.fields['schedule'].queryset = Schedule.objects.all().order_by('name')


class PublicHolidayForm(forms.ModelForm):
    date = forms.DateField(
        label="Sana",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
    name = forms.CharField(
        label="Bayram nomi",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Masalan: Navro'z bayrami"})
    )
    filial = forms.ModelChoiceField(
        queryset=Filial.objects.all(),
        required=False,
        empty_label="— Barcha filiallar uchun —",
        label="Filial",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = PublicHoliday
        fields = ['date', 'name', 'filial']


class DailyScheduleEditForm(forms.ModelForm):
    start = forms.TimeField(
        label="Ish boshlanishi",
        required=False,
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"})
    )
    end = forms.TimeField(
        label="Ish tugashi",
        required=False,
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"})
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        required=False,
        empty_label="— Tanlang —",
        label="Lokatsiya",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    is_day_off = forms.BooleanField(
        required=False,
        label="Dam olish kuni",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    lunch_start = forms.TimeField(
        label="Tushlik boshlanishi",
        required=False,
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"})
    )
    lunch_end = forms.TimeField(
        label="Tushlik tugashi",
        required=False,
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"})
    )
    day_off_reason = forms.CharField(
        required=False,
        label="Dam olish sababi",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Masalan: Bayram, Kasallik..."})
    )

    class Meta:
        model = EmployeeDailySchedule
        fields = ['start', 'end', 'lunch_start', 'lunch_end', 'location', 'is_day_off', 'day_off_reason']

    def __init__(self, *args, **kwargs):
        filial = kwargs.pop('filial', None)
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if filial and filial.organization:
            self.fields['location'].queryset = Location.objects.filter(organization=filial.organization)
        elif organization:
            self.fields['location'].queryset = Location.objects.filter(organization=organization)
        else:
            self.fields['location'].queryset = Location.objects.all()


class ExtraShiftForm(forms.ModelForm):
    """Qo'shimcha shift (bir kunda bir nechta lokatsiya) formi"""
    location = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        required=False,
        empty_label="— Lokatsiya —",
        label="Lokatsiya",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"})
    )
    start = forms.TimeField(
        label="Boshlanish",
        widget=forms.TimeInput(attrs={"class": "form-control form-control-sm", "type": "time"})
    )
    end = forms.TimeField(
        label="Tugash",
        widget=forms.TimeInput(attrs={"class": "form-control form-control-sm", "type": "time"})
    )
    lunch_start = forms.TimeField(
        label="Tushlik bosh.",
        required=False,
        widget=forms.TimeInput(attrs={"class": "form-control form-control-sm", "type": "time"})
    )
    lunch_end = forms.TimeField(
        label="Tushlik tug.",
        required=False,
        widget=forms.TimeInput(attrs={"class": "form-control form-control-sm", "type": "time"})
    )
    note = forms.CharField(
        label="Izoh",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Ixtiyoriy izoh"})
    )

    class Meta:
        model = EmployeeDailyExtraShift
        fields = ['location', 'start', 'end', 'lunch_start', 'lunch_end', 'note']

    def __init__(self, *args, **kwargs):
        filial = kwargs.pop('filial', None)
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if filial and filial.organization:
            self.fields['location'].queryset = Location.objects.filter(organization=filial.organization)
        elif organization:
            self.fields['location'].queryset = Location.objects.filter(organization=organization)
        else:
            self.fields['location'].queryset = Location.objects.all()


def make_extra_shift_formset(filial=None, organization=None, **kwargs):
    """Inline formset — bir kunlik jadvaldagi qo'shimcha shiftlar"""
    BaseFormSet = inlineformset_factory(
        EmployeeDailySchedule,
        EmployeeDailyExtraShift,
        form=ExtraShiftForm,
        extra=1,
        can_delete=True,
        min_num=0,
        validate_min=False,
    )

    class BoundFormSet(BaseFormSet):
        def get_form_kwargs(self, index):
            kw = super().get_form_kwargs(index)
            kw['filial'] = filial
            kw['organization'] = organization
            return kw

    return BoundFormSet(**kwargs)
