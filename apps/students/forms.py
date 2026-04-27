from django import forms
from django.forms import inlineformset_factory
from datetime import datetime

from .models import Group, Direction, Smena, SmenaSlot
from apps.superadmin.models import Building


class DirectionForm(forms.ModelForm):
    class Meta:
        model = Direction
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': "Yo'nalish nomi",
                'class': 'form-control',
            }),
        }


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'direction', 'year', 'month']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Guruh nomi',
                'class': 'form-control',
            }),
            'direction': forms.Select(attrs={'class': 'form-control', 'id': 'id_direction'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000}),
            'month': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, filial_id=None, **kwargs):
        kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        # Yo'nalish queryset — filial bo'yicha
        if filial_id:
            self.fields['direction'].queryset = Direction.objects.filter(filial_id=filial_id)
        elif self.instance and self.instance.pk and self.instance.filial_id:
            self.fields['direction'].queryset = Direction.objects.filter(
                filial_id=self.instance.filial_id
            )
        else:
            self.fields['direction'].queryset = Direction.objects.none()

        self.fields['direction'].required = False

        # Standart qiymatlar (yangi yaratish uchun)
        if not self.instance.pk:
            self.fields['year'].initial = datetime.now().year
            self.fields['month'].initial = datetime.now().month


class SmenaForm(forms.ModelForm):
    class Meta:
        model = Smena
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Smena nomi'}),
        }


SmenaSlotFormSet = inlineformset_factory(
    Smena, SmenaSlot,
    fields=['order', 'start', 'end'],
    extra=1,
    can_delete=True,
    widgets={
        'order': forms.NumberInput(attrs={
            'class': 'form-control form-control-sm text-center', 'min': 1, 'style': 'width:60px'
        }),
        'start': forms.TimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'time'}),
        'end':   forms.TimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'time'}),
    }
)


class BuildingForm(forms.ModelForm):
    class Meta:
        model = Building
        fields = ['name', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lokatsiya nomi'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Manzil (ixtiyoriy)'}),
        }
