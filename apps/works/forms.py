from django import forms
from .models import Work, TaskWork, PPWork, WorkReport, Notice


class WorkForm(forms.ModelForm):
    class Meta:
        model  = Work
        fields = [
            'source_type', 'work_type', 'work_name', 'work_number',
            'description', 'ntc_center', 'department', 'sector', 'project',
            'executor', 'executor_name_raw',
            'date_start', 'date_end', 'deadline',
            'plan_hours',
        ]
        widgets = {
            'date_start': forms.DateInput(attrs={'type': 'date'}),
            'date_end':   forms.DateInput(attrs={'type': 'date'}),
            'deadline':   forms.DateInput(attrs={'type': 'date'}),
            'plan_hours': forms.Textarea(attrs={'rows': 3,
                          'placeholder': '{"2026-01": 40, "2026-02": 80}'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class WorkReportForm(forms.ModelForm):
    class Meta:
        model  = WorkReport
        fields = [
            'doc_name', 'doc_designation', 'inventory_num',
            'date_accepted', 'doc_type', 'doc_class',
            'sheets_a4', 'norm', 'coeff', 'bvd_hours',
            'norm_control', 'doc_link',
        ]
        widgets = {
            'date_accepted': forms.DateInput(attrs={'type': 'date'}),
        }


class NoticeForm(forms.ModelForm):
    class Meta:
        model  = Notice
        fields = [
            'notice_type', 'department', 'executor',
            'date_issued', 'subject', 'description', 'status',
        ]
        widgets = {
            'date_issued': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }
