"""
URL-маршрутизация REST API.
Реплицирует все /api/* маршруты из Flask app.py.
"""
# path — функция формирования URL-паттернов в Django
from django.urls import path

# ── Импорт вьюх по разделам ───────────────────────────────────────────────────

# Вьюхи справочников (Directory)
from .views.directories import DirectoryListView, DirectoryCreateView, DirectoryDetailView
# Вьюхи пользователей (User + Employee)
from .views.users import UserListView, UserDetailView, UserPasswordResetView, DeptEmployeesView
# Вьюхи делегирований ролей
from .views.delegations import DelegationListView, DelegationDetailView
# Публичные вьюхи: справочники для регистрации и сама регистрация
from .views.auth import DirsPublicView, RegisterPublicView
# Настройки колонок таблицы (ширина, видимость)
from .views.col_settings import ColSettingsView
# Вьюхи задач (plan_tasks)
from .views.tasks import (
    TaskListView, TaskCreateView, TaskDetailView,
    TaskDeleteAllView, TaskExecutorsView,
)
# Вьюхи отчётных документов (WorkReport)
from .views.reports import ReportListView, ReportCreateView, ReportDetailView
# Вьюхи производственного плана (PPWork)
from .views.production_plan import (
    ProductionPlanListView, ProductionPlanCreateView,
    ProductionPlanDetailView, ProductionPlanSyncView,
)
# Вьюхи проектов производственного плана (PPProject)
from .views.pp_projects import PPProjectListView, PPProjectCreateView, PPProjectDetailView
# Вьюхи УП-проектов и изделий (Project + ProjectProduct)
from .views.projects import (
    ProjectListView, ProjectCreateView, ProjectDetailView,
    ProjectProductListView, ProjectProductCreateView, ProjectProductDetailView,
)
# Вьюхи отпусков и проверки конфликтов
from .views.vacations import (
    VacationListView, VacationCreateView,
    VacationDetailView, VacationConflictView,
)
# Вьюхи журнала извещений
from .views.journal import JournalListView, JournalCreateView, JournalDetailView
# Вьюхи производственного календаря (WorkCalendar + Holiday)
from .views.work_calendar import (
    WorkCalendarListView, WorkCalendarCreateView, WorkCalendarDetailView,
    HolidayListView, HolidayDetailView,
)
# Вьюхи для заполнения тестовыми данными (seed)
from .views.seed import (
    SeedDataView, SeedExecutorsView, SeedVacationsView,
    FillAllView, FillDeptView,
)
# Вьюхи зависимостей задач (TaskDependency)
from .views.dependencies import (
    TaskDependencyListView, TaskDependencyDetailView,
    AllDependenciesView, AlignDatesView,
)
# Health check
from .views.health import HealthCheckView

# ── Основные URL-паттерны API ─────────────────────────────────────────────────
urlpatterns = [
    # ── Health check ──────────────────────────────────────────────────────
    path('health/', HealthCheckView.as_view()),

    # ── Справочники ──────────────────────────────────────────────────────
    # GET /api/directories/ — список всех записей справочника
    path('directories/',        DirectoryListView.as_view()),
    # POST /api/directories/create/ — создание новой записи (admin)
    path('directories/create/', DirectoryCreateView.as_view()),
    # PUT/DELETE /api/directories/<pk>/ — обновление/удаление записи (admin)
    path('directories/<int:pk>/', DirectoryDetailView.as_view()),

    # ── Пользователи ────────────────────────────────────────────────────
    # GET /api/users/ — список пользователей
    path('users/',              UserListView.as_view()),
    # GET/PUT/DELETE /api/users/<pk>/ — детали, обновление, удаление
    path('users/<int:pk>/',     UserDetailView.as_view()),
    # POST /api/users/<pk>/password/ — сброс пароля (admin)
    path('users/<int:pk>/password/', UserPasswordResetView.as_view()),
    # GET /api/dept_employees/?dept=CODE — сотрудники отдела (для всех авторизованных)
    path('dept_employees/', DeptEmployeesView.as_view()),

    # ── Делегирования ────────────────────────────────────────────────────
    # GET/POST /api/delegations/ — список и создание делегирований
    path('delegations/',        DelegationListView.as_view()),
    # PUT/DELETE /api/delegations/<pk>/ — обновление/удаление делегирования
    path('delegations/<int:pk>/', DelegationDetailView.as_view()),

    # ── Публичные (без авторизации) ─────────────────────────────────────
    # GET /api/dirs_public/ — справочники для формы регистрации (не требует входа)
    path('dirs_public/',        DirsPublicView.as_view()),
    # POST /api/register_public/ — публичная регистрация нового пользователя
    path('register_public/',    RegisterPublicView.as_view()),

    # ── Настройки колонок ────────────────────────────────────────────────
    # GET/POST /api/col_settings/ — чтение и сохранение ширин/видимости колонок
    path('col_settings/',       ColSettingsView.as_view()),

    # ── Задачи (tasks) ──────────────────────────────────────────────────
    # GET /api/tasks/ — список задач с фильтрами и пагинацией
    path('tasks/',              TaskListView.as_view()),
    # POST /api/tasks/create/ — создание новой задачи
    path('tasks/create/',       TaskCreateView.as_view()),
    # DELETE /api/tasks/all/ — удаление всех задач (только admin)
    path('tasks/all/',          TaskDeleteAllView.as_view()),
    # GET/PUT/DELETE /api/tasks/<pk>/ — чтение, обновление, удаление задачи
    path('tasks/<int:pk>/',     TaskDetailView.as_view()),
    # GET /api/tasks/<pk>/executors/ — список исполнителей задачи
    path('tasks/<int:pk>/executors/', TaskExecutorsView.as_view()),

    # ── Зависимости задач ─────────────────────────────────────────────
    # GET/POST /api/tasks/<pk>/dependencies/ — список и создание зависимостей
    path('tasks/<int:pk>/dependencies/', TaskDependencyListView.as_view()),
    # POST /api/tasks/<pk>/align_dates/ — выравнивание дат по зависимостям
    path('tasks/<int:pk>/align_dates/', AlignDatesView.as_view()),
    # PUT/DELETE /api/dependencies/<pk>/ — обновление/удаление зависимости
    path('dependencies/<int:pk>/', TaskDependencyDetailView.as_view()),
    # GET /api/dependencies/ — все зависимости (для диаграммы Ганта)
    path('dependencies/', AllDependenciesView.as_view()),

    # ── Отчётные документы ──────────────────────────────────────────────
    # GET /api/reports/<task_id>/ — список отчётов по задаче
    path('reports/<int:task_id>/', ReportListView.as_view()),
    # POST /api/reports/ — создание нового отчёта
    path('reports/',              ReportCreateView.as_view()),
    # GET/PUT/DELETE /api/reports/<pk>/detail/ — операции с конкретным отчётом
    path('reports/<int:pk>/detail/', ReportDetailView.as_view()),

    # ── Производственный план ────────────────────────────────────────────
    # GET /api/production_plan/ — список записей ПП
    path('production_plan/',         ProductionPlanListView.as_view()),
    # POST /api/production_plan/create/ — создание записи ПП
    path('production_plan/create/',  ProductionPlanCreateView.as_view()),
    # POST /api/production_plan/sync/ — синхронизация ПП → план задач
    path('production_plan/sync/',    ProductionPlanSyncView.as_view()),
    # PUT/DELETE /api/production_plan/<pk>/ — обновление/удаление записи ПП
    path('production_plan/<int:pk>/', ProductionPlanDetailView.as_view()),

    # ── Управление проектами (УП) ────────────────────────────────────────
    # GET /api/projects/ — список УП-проектов
    path('projects/',           ProjectListView.as_view()),
    # POST /api/projects/create/ — создание УП-проекта
    path('projects/create/',    ProjectCreateView.as_view()),
    # PUT/DELETE /api/projects/<pk>/ — обновление/удаление УП-проекта
    path('projects/<int:pk>/',  ProjectDetailView.as_view()),
    # GET /api/projects/<pk>/products/ — список изделий проекта
    path('projects/<int:pk>/products/', ProjectProductListView.as_view()),
    # POST /api/projects/<pk>/products/create/ — создание изделия
    path('projects/<int:pk>/products/create/', ProjectProductCreateView.as_view()),
    # PUT/DELETE /api/projects/<pk>/products/<pid>/ — операции с изделием
    path('projects/<int:pk>/products/<int:pid>/', ProjectProductDetailView.as_view()),

    # ── Проекты ПП ──────────────────────────────────────────────────────
    # GET /api/pp_projects/ — список проектов производственного плана
    path('pp_projects/',        PPProjectListView.as_view()),
    # POST /api/pp_projects/create/ — создание проекта ПП (admin)
    path('pp_projects/create/', PPProjectCreateView.as_view()),
    # PUT/DELETE /api/pp_projects/<pk>/ — обновление/удаление проекта ПП (admin)
    path('pp_projects/<int:pk>/', PPProjectDetailView.as_view()),

    # ── Отпуска ─────────────────────────────────────────────────────────
    # GET /api/vacations/ — список отпусков (с фильтрацией по роли)
    path('vacations/',          VacationListView.as_view()),
    # POST /api/vacations/create/ — создание записи об отпуске
    path('vacations/create/',   VacationCreateView.as_view()),
    # PUT/DELETE /api/vacations/<pk>/ — обновление/удаление записи об отпуске
    path('vacations/<int:pk>/', VacationDetailView.as_view()),
    # GET /api/check_vacation_conflict/ — проверка пересечений отпусков
    path('check_vacation_conflict/', VacationConflictView.as_view()),

    # ── Журнал извещений ────────────────────────────────────────────────
    # GET /api/journal/ — список записей журнала
    path('journal/',            JournalListView.as_view()),
    # POST /api/journal/create/ — создание записи журнала
    path('journal/create/',     JournalCreateView.as_view()),
    # PUT/DELETE /api/journal/<pk>/ — обновление/удаление записи журнала
    path('journal/<int:pk>/',   JournalDetailView.as_view()),

    # ── Производственный календарь ───────────────────────────────────────
    # GET /api/work_calendar/ — список месячных норм рабочего времени
    path('work_calendar/',          WorkCalendarListView.as_view()),
    # POST /api/work_calendar/create/ — создание/обновление записи календаря (admin)
    path('work_calendar/create/',   WorkCalendarCreateView.as_view()),
    # PUT/DELETE /api/work_calendar/<pk>/ — операции с записью календаря (admin)
    path('work_calendar/<int:pk>/', WorkCalendarDetailView.as_view()),

    # ── Нерабочие дни (Holiday) ────────────────────────────────────────
    # GET/POST /api/holidays/ — список и создание нерабочих дней
    path('holidays/',          HolidayListView.as_view()),
    # DELETE /api/holidays/<pk>/ — удаление нерабочего дня (admin)
    path('holidays/<int:pk>/', HolidayDetailView.as_view()),

]

# ── Seed-данные и дамп (только в DEBUG) ────────────────────────────────────
# Импортируем настройки Django для проверки режима DEBUG
from django.conf import settings
if settings.DEBUG:
    # Загрузка дампа данных (только в DEBUG-режиме!)
    from apps.api.views.load_dump import LoadDumpView
    urlpatterns += [
        path('load_dump/', LoadDumpView.as_view()),
    ]

    # В режиме отладки добавляем вспомогательные маршруты для заполнения БД данными
    urlpatterns += [
        # POST /api/seed/ — заполнение базы тестовыми задачами/проектами
        path('seed/',               SeedDataView.as_view()),
        # POST /api/seed_executors/ — заполнение исполнителями
        path('seed_executors/',     SeedExecutorsView.as_view()),
        # POST /api/seed_vacations/ — заполнение отпусками
        path('seed_vacations/',     SeedVacationsView.as_view()),
        # POST /api/fill_all/ — заполнение всеми тестовыми данными сразу
        path('fill_all/',           FillAllView.as_view()),
        # POST /api/fill_dept/ — заполнение данными конкретного отдела
        path('fill_dept/',          FillDeptView.as_view()),
    ]
