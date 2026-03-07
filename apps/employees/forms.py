from django import forms
from .models import Employee, Vacation, KPI


class EmployeeForm(forms.ModelForm):
    class Meta:
        model  = Employee
        fields = [
            'user', 'role',
            'last_name', 'first_name', 'patronymic',
            'position', 'ntc_center', 'department', 'sector',
            'phone', 'email_corp',
            'hire_date', 'dismissal_date',
            'monthly_hours_norm', 'personal_coeff',
            'must_change_password', 'is_active',
        ]
        widgets = {
            'hire_date':       forms.DateInput(attrs={'type': 'date'}),
            'dismissal_date':  forms.DateInput(attrs={'type': 'date'}),
        }


class VacationForm(forms.ModelForm):
    class Meta:
        model  = Vacation
        fields = ['vac_type', 'date_start', 'date_end', 'notes']
        widgets = {
            'date_start': forms.DateInput(attrs={'type': 'date'}),
            'date_end':   forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        ds = cleaned.get('date_start')
        de = cleaned.get('date_end')
        if ds and de and ds > de:
            raise forms.ValidationError(
                'Дата окончания не может быть раньше даты начала.'
            )
        return cleaned


class KPIForm(forms.ModelForm):
    class Meta:
        model  = KPI
        fields = [
            'year', 'month',
            'plan_hours', 'fact_hours',
            'norm_control_remarks', 'docs_issued',
            'score', 'notes',
        ]
