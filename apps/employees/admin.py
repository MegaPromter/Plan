from django.contrib import admin
from .models import (
    Department, Sector, NTCCenter,
    Employee, Vacation, KPI, EmployeeDocument, RoleDelegation,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display  = ('code', 'name', 'ntc_center')
    list_filter   = ('ntc_center',)
    search_fields = ('code', 'name')


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ('code', 'department', 'name')
    list_filter  = ('department',)
    search_fields = ('code',)


@admin.register(NTCCenter)
class NTCCenterAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')


class VacationInline(admin.TabularInline):
    model  = Vacation
    extra  = 0
    fields = ('vac_type', 'date_start', 'date_end', 'notes')


class KPIInline(admin.TabularInline):
    model  = KPI
    extra  = 0
    fields = ('year', 'month', 'plan_hours', 'fact_hours', 'completion_pct', 'score')
    readonly_fields = ('completion_pct',)


class DocumentInline(admin.TabularInline):
    model  = EmployeeDocument
    extra  = 0
    fields = ('doc_type', 'title', 'date', 'notes')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display  = (
        'full_name', 'short_name', 'role', 'position',
        'department', 'sector', 'ntc_center', 'is_active',
    )
    list_filter   = ('role', 'department', 'ntc_center', 'is_active')
    search_fields = ('last_name', 'first_name', 'patronymic', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    inlines       = [VacationInline, KPIInline, DocumentInline]
    fieldsets = (
        ('Учётная запись', {
            'fields': ('user', 'role', 'must_change_password', 'is_active'),
        }),
        ('ФИО', {
            'fields': ('last_name', 'first_name', 'patronymic'),
        }),
        ('Должность и подразделение', {
            'fields': ('position', 'ntc_center', 'department', 'sector'),
        }),
        ('Контакты', {
            'fields': ('phone', 'email_corp'),
        }),
        ('Параметры работы', {
            'fields': ('hire_date', 'dismissal_date',
                       'monthly_hours_norm', 'personal_coeff'),
        }),
        ('Аудит', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Vacation)
class VacationAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'vac_type', 'date_start', 'date_end', 'duration_days')
    list_filter   = ('vac_type', 'date_start')
    search_fields = ('employee__last_name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'year', 'month',
                     'plan_hours', 'fact_hours', 'completion_pct', 'score')
    list_filter   = ('year', 'month')
    search_fields = ('employee__last_name',)
    readonly_fields = ('completion_pct', 'created_at', 'updated_at')


@admin.register(RoleDelegation)
class RoleDelegationAdmin(admin.ModelAdmin):
    list_display  = ('delegator', 'delegate', 'scope_type', 'scope_value',
                     'can_write', 'valid_until')
    list_filter   = ('scope_type', 'can_write')
    search_fields = ('delegator__last_name', 'delegate__last_name')
