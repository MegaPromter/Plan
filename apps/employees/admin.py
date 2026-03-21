# Импорт стандартного модуля администрирования Django
from django.contrib import admin
# Импорт всех моделей, которые будут зарегистрированы в Admin
from .models import (
    Department, Sector, NTCCenter,
    Employee, Vacation, KPI, EmployeeDocument, RoleDelegation,
)


# ── Регистрация модели Department ─────────────────────────────────────────────

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    # Поля, отображаемые в списке отделов
    list_display  = ('code', 'name', 'ntc_center')
    # Боковой фильтр по НТЦ-центру
    list_filter   = ('ntc_center',)
    # Поиск по коду и названию отдела
    search_fields = ('code', 'name')


# ── Регистрация модели Sector ──────────────────────────────────────────────────

@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    # Поля, отображаемые в списке секторов
    list_display = ('code', 'department', 'name')
    # Боковой фильтр по отделу
    list_filter  = ('department',)
    # Поиск по коду сектора
    search_fields = ('code',)


# ── Регистрация модели NTCCenter ──────────────────────────────────────────────

@admin.register(NTCCenter)
class NTCCenterAdmin(admin.ModelAdmin):
    # Отображаем код и название НТЦ-центра в списке
    list_display = ('code', 'name')


# ── Инлайн-редактор Vacation (отпуска) ────────────────────────────────────────

class VacationInline(admin.TabularInline):
    # Табличный инлайн для отпусков в форме сотрудника
    model  = Vacation
    # extra=0: не показывать пустые строки для новых записей
    extra  = 0
    # Поля для редактирования в инлайне
    fields = ('vac_type', 'date_start', 'date_end', 'notes')


# ── Инлайн-редактор KPI ───────────────────────────────────────────────────────

class KPIInline(admin.TabularInline):
    # Табличный инлайн для KPI-записей в форме сотрудника
    model  = KPI
    # extra=0: не показывать пустые строки
    extra  = 0
    # Поля для редактирования и отображения
    fields = ('year', 'month', 'plan_hours', 'fact_hours', 'completion_pct', 'score')
    # completion_pct вычисляется автоматически — только для чтения
    readonly_fields = ('completion_pct',)


# ── Инлайн-редактор EmployeeDocument ─────────────────────────────────────────

class DocumentInline(admin.TabularInline):
    # Табличный инлайн для документов/характеристик сотрудника
    model  = EmployeeDocument
    # extra=0: не показывать пустые строки
    extra  = 0
    # Основные поля документа
    fields = ('doc_type', 'title', 'date', 'notes')


# ── Регистрация основной модели Employee ──────────────────────────────────────

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    # Поля, отображаемые в списке сотрудников
    list_display  = (
        'full_name', 'short_name', 'role', 'position',
        'department', 'sector', 'ntc_center', 'date_joined', 'is_active',
    )

    @admin.display(description='Зарегистрирован', ordering='user__date_joined')
    def date_joined(self, obj):
        if obj.user and obj.user.date_joined:
            return obj.user.date_joined.strftime('%d.%m.%Y %H:%M')
        return '—'
    # Боковые фильтры: по роли, отделу, НТЦ-центру и активности
    list_filter   = ('role', 'department', 'ntc_center', 'is_active')
    # Поиск по ФИО и username учётной записи
    search_fields = ('last_name', 'first_name', 'patronymic', 'user__username')
    # Поля только для чтения — заполняются автоматически
    readonly_fields = ('created_at', 'updated_at')
    # Встроенные редакторы: отпуска, KPI и документы
    inlines       = [VacationInline, KPIInline, DocumentInline]
    # Группировка полей по тематическим разделам
    fieldsets = (
        ('Учётная запись', {
            # Связь с Django User, роль и служебные флаги
            'fields': ('user', 'role', 'must_change_password', 'is_active'),
        }),
        ('ФИО', {
            # Фамилия, имя и отчество сотрудника
            'fields': ('last_name', 'first_name', 'patronymic'),
        }),
        ('Должность и подразделение', {
            # Штатная должность и принадлежность к структурным единицам
            'fields': ('position', 'ntc_center', 'department', 'sector'),
        }),
        ('Контакты', {
            # Рабочий телефон и корпоративный email
            'fields': ('phone', 'email_corp'),
        }),
        ('Параметры работы', {
            # Даты трудовых отношений и параметры нормирования часов
            'fields': ('hire_date', 'dismissal_date',
                       'monthly_hours_norm', 'personal_coeff'),
        }),
        ('Аудит', {
            # Метки времени создания и обновления (свёрнуты по умолчанию)
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


# ── Регистрация модели Vacation ────────────────────────────────────────────────

@admin.register(Vacation)
class VacationAdmin(admin.ModelAdmin):
    # Поля, отображаемые в списке отпусков
    list_display  = ('employee', 'vac_type', 'date_start', 'date_end', 'duration_days')
    # Боковые фильтры по типу отпуска и дате начала
    list_filter   = ('vac_type', 'date_start')
    # Поиск по фамилии сотрудника
    search_fields = ('employee__last_name',)
    # Метки времени — только для чтения
    readonly_fields = ('created_at', 'updated_at')


# ── Регистрация модели KPI ─────────────────────────────────────────────────────

@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    # Поля, отображаемые в списке KPI-записей
    list_display  = ('employee', 'year', 'month',
                     'plan_hours', 'fact_hours', 'completion_pct', 'score')
    # Боковые фильтры по году и месяцу
    list_filter   = ('year', 'month')
    # Поиск по фамилии сотрудника
    search_fields = ('employee__last_name',)
    # completion_pct вычисляется в KPI.save(), метки времени — автоматически
    readonly_fields = ('completion_pct', 'created_at', 'updated_at')


# ── Регистрация модели RoleDelegation ─────────────────────────────────────────

@admin.register(RoleDelegation)
class RoleDelegationAdmin(admin.ModelAdmin):
    # Поля, отображаемые в списке делегирований
    list_display  = ('delegator', 'delegate', 'scope_type', 'scope_value',
                     'can_write', 'valid_until')
    # Боковые фильтры: по типу зоны и наличию права записи
    list_filter   = ('scope_type', 'can_write')
    # Поиск по фамилиям делегатора и делегата
    search_fields = ('delegator__last_name', 'delegate__last_name')
