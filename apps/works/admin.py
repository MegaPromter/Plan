# Импорт стандартного модуля администрирования Django
from django.contrib import admin
# Импорт моделей, которые будут зарегистрированы в Admin
from .models import (
    Project, Work, WorkReport, Notice,
)


# ── Регистрация модели Project ─────────────────────────────────────────────────

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display  = ('name', 'code', 'created_at')
    search_fields = ('name_full', 'name_short', 'code')


# ── Инлайн-редактор WorkReport (отчётные документы) ──────────────────────────

class WorkReportInline(admin.TabularInline):
    model  = WorkReport
    extra  = 0
    fields = ('doc_name', 'doc_designation', 'date_accepted',
              'doc_type', 'sheets_a4', 'norm', 'coeff')


# ── Регистрация основной модели Work ──────────────────────────────────────────

@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display  = (
        'work_name', 'show_in_pp', 'show_in_plan', 'task_type',
        'department', 'executor', 'date_start', 'date_end',
    )
    list_filter   = ('show_in_pp', 'show_in_plan', 'department', 'ntc_center')
    search_fields = ('work_name', 'work_num', 'executor__last_name')
    readonly_fields = ('created_at', 'updated_at')
    inlines       = [WorkReportInline]
    fieldsets = (
        ('Основное', {
            'fields': (
                'show_in_pp', 'show_in_plan', 'task_type', 'work_name',
                'work_num', 'work_designation',
            ),
        }),
        ('Принадлежность', {
            'fields': ('ntc_center', 'department', 'sector', 'project'),
        }),
        ('Исполнитель', {
            'fields': ('executor',),
        }),
        ('Сроки', {
            'fields': ('date_start', 'date_end', 'deadline'),
        }),
        ('Плановые часы', {
            'fields': ('plan_hours',),
        }),
        ('Поля задачи (СП)', {
            'fields': ('justification', 'executors_list', 'actions'),
            'classes': ('collapse',),
        }),
        ('Поля ПП', {
            'fields': (
                'pp_project', 'row_code', 'work_order', 'stage_num',
                'milestone_num', 'sheets_a4', 'norm', 'coeff',
                'total_2d', 'total_3d', 'labor',
            ),
            'classes': ('collapse',),
        }),
        ('Аудит', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


# ── Регистрация модели Notice (журнал извещений) ──────────────────────────────

@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display  = ('subject', 'notice_type', 'department',
                     'executor', 'date_issued', 'status')
    list_filter   = ('status', 'department')
    search_fields = ('subject', 'description')
    readonly_fields = ('created_at', 'updated_at')
