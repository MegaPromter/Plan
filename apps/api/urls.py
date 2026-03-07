"""
URL-маршрутизация REST API.
Реплицирует все /api/* маршруты из Flask app.py.
"""
from django.urls import path

from .views.directories import DirectoryListView, DirectoryCreateView, DirectoryDetailView
from .views.users import UserListView, UserDetailView, UserPasswordResetView
from .views.delegations import DelegationListView, DelegationDetailView
from .views.auth import DirsPublicView, RegisterPublicView
from .views.col_settings import ColSettingsView
from .views.tasks import (
    TaskListView, TaskCreateView, TaskDetailView,
    TaskDeleteAllView, TaskExecutorsView,
)
from .views.reports import ReportListView, ReportCreateView, ReportDetailView
from .views.production_plan import (
    ProductionPlanListView, ProductionPlanCreateView,
    ProductionPlanDetailView, ProductionPlanSyncView,
)
from .views.pp_projects import PPProjectListView, PPProjectCreateView, PPProjectDetailView
from .views.projects import (
    ProjectListView, ProjectCreateView, ProjectDetailView,
    ProjectProductListView, ProjectProductCreateView, ProjectProductDetailView,
)
from .views.vacations import (
    VacationListView, VacationCreateView,
    VacationDetailView, VacationConflictView,
)
from .views.journal import JournalListView, JournalCreateView, JournalDetailView
from .views.work_calendar import (
    WorkCalendarListView, WorkCalendarCreateView, WorkCalendarDetailView,
)
from .views.seed import (
    SeedDataView, SeedExecutorsView, SeedVacationsView,
    FillAllView, FillDeptView,
)

urlpatterns = [
    # ── Справочники ──────────────────────────────────────────────────────
    path('directories/',        DirectoryListView.as_view()),
    path('directories/create/', DirectoryCreateView.as_view()),
    path('directories/<int:pk>/', DirectoryDetailView.as_view()),

    # ── Пользователи ────────────────────────────────────────────────────
    path('users/',              UserListView.as_view()),
    path('users/<int:pk>/',     UserDetailView.as_view()),
    path('users/<int:pk>/password/', UserPasswordResetView.as_view()),

    # ── Делегирования ────────────────────────────────────────────────────
    path('delegations/',        DelegationListView.as_view()),
    path('delegations/<int:pk>/', DelegationDetailView.as_view()),

    # ── Публичные (без авторизации) ─────────────────────────────────────
    path('dirs_public/',        DirsPublicView.as_view()),
    path('register_public/',    RegisterPublicView.as_view()),

    # ── Настройки колонок ────────────────────────────────────────────────
    path('col_settings/',       ColSettingsView.as_view()),

    # ── Задачи (tasks) ──────────────────────────────────────────────────
    path('tasks/',              TaskListView.as_view()),
    path('tasks/create/',       TaskCreateView.as_view()),
    path('tasks/all/',          TaskDeleteAllView.as_view()),
    path('tasks/<int:pk>/',     TaskDetailView.as_view()),
    path('tasks/<int:pk>/executors/', TaskExecutorsView.as_view()),

    # ── Отчётные документы ──────────────────────────────────────────────
    path('reports/<int:task_id>/', ReportListView.as_view()),
    path('reports/',              ReportCreateView.as_view()),
    path('reports/<int:pk>/detail/', ReportDetailView.as_view()),

    # ── Производственный план ────────────────────────────────────────────
    path('production_plan/',         ProductionPlanListView.as_view()),
    path('production_plan/create/',  ProductionPlanCreateView.as_view()),
    path('production_plan/sync/',    ProductionPlanSyncView.as_view()),
    path('production_plan/<int:pk>/', ProductionPlanDetailView.as_view()),

    # ── Управление проектами (УП) ────────────────────────────────────────
    path('projects/',           ProjectListView.as_view()),
    path('projects/create/',    ProjectCreateView.as_view()),
    path('projects/<int:pk>/',  ProjectDetailView.as_view()),
    path('projects/<int:pk>/products/', ProjectProductListView.as_view()),
    path('projects/<int:pk>/products/create/', ProjectProductCreateView.as_view()),
    path('projects/<int:pk>/products/<int:pid>/', ProjectProductDetailView.as_view()),

    # ── Проекты ПП ──────────────────────────────────────────────────────
    path('pp_projects/',        PPProjectListView.as_view()),
    path('pp_projects/create/', PPProjectCreateView.as_view()),
    path('pp_projects/<int:pk>/', PPProjectDetailView.as_view()),

    # ── Отпуска ─────────────────────────────────────────────────────────
    path('vacations/',          VacationListView.as_view()),
    path('vacations/create/',   VacationCreateView.as_view()),
    path('vacations/<int:pk>/', VacationDetailView.as_view()),
    path('check_vacation_conflict/', VacationConflictView.as_view()),

    # ── Журнал извещений ────────────────────────────────────────────────
    path('journal/',            JournalListView.as_view()),
    path('journal/create/',     JournalCreateView.as_view()),
    path('journal/<int:pk>/',   JournalDetailView.as_view()),

    # ── Производственный календарь ───────────────────────────────────────
    path('work_calendar/',          WorkCalendarListView.as_view()),
    path('work_calendar/create/',   WorkCalendarCreateView.as_view()),
    path('work_calendar/<int:pk>/', WorkCalendarDetailView.as_view()),

]

# ── Seed-данные (только в DEBUG) ─────────────────────────────────────────────
from django.conf import settings
if settings.DEBUG:
    urlpatterns += [
        path('seed/',               SeedDataView.as_view()),
        path('seed_executors/',     SeedExecutorsView.as_view()),
        path('seed_vacations/',     SeedVacationsView.as_view()),
        path('fill_all/',           FillAllView.as_view()),
        path('fill_dept/',          FillDeptView.as_view()),
    ]
