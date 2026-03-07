from django.contrib import admin
from .models import (
    Project, WorkType, Work, TaskWork, PPWork, WorkReport, Notice,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display  = ('name', 'code', 'created_at')
    search_fields = ('name', 'code')


@admin.register(WorkType)
class WorkTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


class TaskWorkInline(admin.StackedInline):
    model  = TaskWork
    extra  = 0
    fields = ('stage', 'justification', 'executors_list', 'actions')


class PPWorkInline(admin.StackedInline):
    model  = PPWork
    extra  = 0
    fields = (
        'row_code', 'work_order', 'stage_num', 'milestone_num',
        'sheets_a4', 'norm', 'coeff', 'total_2d', 'total_3d', 'labor',
        'sector_head_name',
    )


class WorkReportInline(admin.TabularInline):
    model  = WorkReport
    extra  = 0
    fields = ('doc_name', 'doc_designation', 'date_accepted',
              'doc_type', 'sheets_a4', 'norm', 'coeff')


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display  = (
        'work_name', 'source_type', 'work_type',
        'department', 'executor', 'date_start', 'date_end',
    )
    list_filter   = ('source_type', 'work_type', 'department', 'ntc_center')
    search_fields = ('work_name', 'work_number', 'executor__last_name')
    readonly_fields = ('created_at', 'updated_at')
    inlines       = [TaskWorkInline, PPWorkInline, WorkReportInline]
    fieldsets = (
        ('Основное', {
            'fields': (
                'source_type', 'work_type', 'work_name',
                'work_number', 'description',
            ),
        }),
        ('Принадлежность', {
            'fields': ('ntc_center', 'department', 'sector', 'project'),
        }),
        ('Исполнитель', {
            'fields': ('executor', 'executor_name_raw'),
        }),
        ('Сроки', {
            'fields': ('date_start', 'date_end', 'deadline'),
        }),
        ('Плановые часы', {
            'fields': ('plan_hours',),
        }),
        ('Аудит', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display  = ('subject', 'notice_type', 'department',
                     'executor', 'date_issued', 'status')
    list_filter   = ('status', 'department')
    search_fields = ('subject', 'description')
    readonly_fields = ('created_at', 'updated_at')
