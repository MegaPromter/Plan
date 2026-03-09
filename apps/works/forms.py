# Импорт базового модуля форм Django
from django import forms
# Импорт моделей, для которых создаются формы
from .models import Work, WorkReport, Notice


# ── Форма создания/редактирования основной записи о работе ────────────────────

class WorkForm(forms.ModelForm):
    class Meta:
        # Модель, на основе которой строится форма
        model  = Work
        # Поля модели, включаемые в форму (все основные поля Work)
        fields = [
            'show_in_pp', 'show_in_plan', 'task_type', 'work_name', 'work_num',
            'work_designation', 'ntc_center', 'department', 'sector', 'project',
            'executor', 'executor_name_raw',
            'date_start', 'date_end', 'deadline',
            'plan_hours',
        ]
        # Переопределяем виджеты для улучшения UX в браузере
        widgets = {
            # Поля дат используют нативный HTML5 date-picker
            'date_start': forms.DateInput(attrs={'type': 'date'}),
            'date_end':   forms.DateInput(attrs={'type': 'date'}),
            'deadline':   forms.DateInput(attrs={'type': 'date'}),
            # plan_hours — JSON-строка; textarea с примером формата
            'plan_hours': forms.Textarea(attrs={'rows': 3,
                          'placeholder': '{"2026-01": 40, "2026-02": 80}'}),
            # Обозначение отображается как многострочное текстовое поле
            'work_designation': forms.Textarea(attrs={'rows': 3}),
        }


# ── Форма создания/редактирования отчётного документа ────────────────────────

class WorkReportForm(forms.ModelForm):
    class Meta:
        # Модель отчётного документа
        model  = WorkReport
        # Все редактируемые поля документа (work устанавливается программно)
        fields = [
            'doc_name', 'doc_designation', 'inventory_num',
            'date_accepted', 'doc_type', 'doc_class',
            'sheets_a4', 'norm', 'coeff', 'bvd_hours',
            'norm_control', 'doc_link',
        ]
        # Дата приёмки — нативный HTML5 date-picker
        widgets = {
            'date_accepted': forms.DateInput(attrs={'type': 'date'}),
        }


# ── Форма создания/редактирования извещения ───────────────────────────────────

class NoticeForm(forms.ModelForm):
    class Meta:
        # Модель журнала корректирующих извещений
        model  = Notice
        # Редактируемые поля (created_at и updated_at заполняются автоматически)
        fields = [
            'notice_type', 'department', 'executor',
            'date_issued', 'subject', 'description', 'status',
        ]
        # Переопределяем виджеты для удобства ввода
        widgets = {
            # Дата выдачи извещения — нативный HTML5 date-picker
            'date_issued': forms.DateInput(attrs={'type': 'date'}),
            # Описание — многострочное текстовое поле (4 строки)
            'description': forms.Textarea(attrs={'rows': 4}),
        }
