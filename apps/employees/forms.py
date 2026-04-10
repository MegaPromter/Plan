# Импорт базового модуля форм Django
from django import forms

# Импорт моделей, для которых создаются формы
from .models import KPI, Employee, Vacation

# ── Форма создания/редактирования профиля сотрудника ─────────────────────────


class EmployeeForm(forms.ModelForm):
    class Meta:
        # Модель сотрудника, на основе которой строится форма
        model = Employee
        # Поля модели, включаемые в форму (все редактируемые поля)
        fields = [
            "user",
            "role",  # учётная запись и роль
            "last_name",
            "first_name",
            "patronymic",  # ФИО
            "position",
            "ntc_center",
            "department",
            "sector",  # должность и подразделение
            "phone",
            "email_corp",  # контактные данные
            "hire_date",
            "dismissal_date",  # даты трудовых отношений
            "monthly_hours_norm",
            "personal_coeff",  # параметры нормирования
            "must_change_password",
            "is_active",  # служебные флаги
        ]
        # Переопределяем виджеты для полей с датами — нативный HTML5 date-picker
        widgets = {
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "dismissal_date": forms.DateInput(attrs={"type": "date"}),
        }


# ── Форма создания/редактирования записи об отпуске ──────────────────────────


class VacationForm(forms.ModelForm):
    class Meta:
        # Модель отпуска сотрудника
        model = Vacation
        # Поля: тип отсутствия, период и примечания (employee задаётся программно)
        fields = ["vac_type", "date_start", "date_end", "notes"]
        # Поля дат — нативный HTML5 date-picker для удобства ввода
        widgets = {
            "date_start": forms.DateInput(attrs={"type": "date"}),
            "date_end": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        # Вызываем стандартную валидацию Django (required, format и т.д.)
        cleaned = super().clean()
        # Получаем очищенные значения дат
        ds = cleaned.get("date_start")
        de = cleaned.get("date_end")
        # Проверяем логическую корректность: дата начала не может быть позже конца
        if ds and de and ds > de:
            raise forms.ValidationError(
                "Дата окончания не может быть раньше даты начала."
            )
        # Возвращаем очищенные данные для дальнейшего сохранения
        return cleaned


# ── Форма создания/редактирования KPI сотрудника ─────────────────────────────


class KPIForm(forms.ModelForm):
    class Meta:
        # Модель показателей эффективности
        model = KPI
        # Редактируемые поля (completion_pct вычисляется автоматически в KPI.save)
        fields = [
            "year",
            "month",  # период (год и месяц)
            "plan_hours",
            "fact_hours",  # трудоёмкость план/факт
            "norm_control_remarks",
            "docs_issued",  # показатели качества
            "score",
            "notes",  # итоговый балл и примечания
        ]
