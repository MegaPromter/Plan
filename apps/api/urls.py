"""
URL-маршрутизация REST API.
Реплицирует все /api/* маршруты из Flask app.py.
"""

# path — функция формирования URL-паттернов в Django
from django.urls import path

# Вьюха пересечений отсутствий
from .views.absence_overlaps import AbsenceOverlapsView

# Аналитика
from .views.analytics import (
    EmployeeAnalyticsView,
    PPAnalyticsView,
    WorkloadAnalyticsView,
)
from .views.analytics_plan import PlanAnalyticsView
from .views.analytics_reports import ReportsAnalyticsView

# Журнал аудита (только admin)
from .views.audit_log import AuditLogListView

# Публичные вьюхи: справочники для регистрации и сама регистрация
from .views.auth import DirsPublicView, RegisterPublicView

# Вьюхи командировок
from .views.business_trips import BusinessTripDetailView, BusinessTripListView

# Вьюхи наборов изменений (Changeset / Песочница)
from .views.changesets import (
    ChangesetApproveView,
    ChangesetCreateView,
    ChangesetDetailView,
    ChangesetDiffView,
    ChangesetItemCreateView,
    ChangesetItemDetailView,
    ChangesetListView,
    ChangesetRejectView,
    ChangesetReopenView,
    ChangesetSubmitView,
)

# Настройки колонок таблицы (ширина, видимость)
from .views.col_settings import ColSettingsView

# Вьюхи комментариев к задачам (WorkComment)
from .views.comments import CommentDetailView, CommentListView
from .views.dashboard import (
    DashboardAPIView,
    DashboardEmployeeView,
    DashboardExportView,
    DashboardScopeView,
)

# Вьюхи делегирований ролей
from .views.delegations import DelegationDetailView, DelegationListView

# Вьюхи зависимостей задач (TaskDependency)
from .views.dependencies import (
    AlignDatesView,
    AllDependenciesView,
    TaskDependencyDetailView,
    TaskDependencyListView,
)

# ── Импорт вьюх по разделам ───────────────────────────────────────────────────
# Вьюхи справочников (Directory)
from .views.directories import (
    DirectoryCreateView,
    DirectoryDetailView,
    DirectoryListView,
)

# Вьюхи замечаний и предложений (Feedback)
from .views.feedback import (
    FeedbackAttachmentDeleteView,
    FeedbackDetailView,
    FeedbackListView,
)

# Health check
from .views.health import HealthCheckView

# Вьюхи журнала извещений
from .views.journal import (
    JournalCreateView,
    JournalDetailView,
    JournalFacetsView,
    JournalListView,
)

# Уведомления
from .views.notifications import (
    NotificationListView,
    NotificationReadAllView,
    NotificationReadView,
    NotificationSyncView,
    NotificationUnreadCountView,
)

# Вьюхи проектов производственного плана (PPProject)
from .views.pp_projects import (
    PPProjectCreateView,
    PPProjectDetailView,
    PPProjectListView,
)
from .views.pp_stages import PPStageCreateView, PPStageDetailView, PPStageListView

# Вьюхи производственного плана (PPWork)
from .views.production_plan import (
    PPCrossStagesView,
    ProductionPlanCreateView,
    ProductionPlanDetailView,
    ProductionPlanListView,
    ProductionPlanSyncView,
)

# Вьюхи УП-проектов и изделий (Project + ProjectProduct)
from .views.projects import (
    ProjectCreateView,
    ProjectDetailView,
    ProjectListView,
    ProjectMetricsView,
    ProjectProductCreateView,
    ProjectProductDetailView,
    ProjectProductListView,
)

# Вьюхи отчётных документов (WorkReport)
from .views.reports import ReportCreateView, ReportDetailView, ReportListView

# Вьюхи для заполнения тестовыми данными (seed)
from .views.seed import (
    FillAllView,
    FillDeptView,
    SeedAnalyticsView,
    SeedDataView,
    SeedExecutorsView,
    SeedVacationsView,
)

# Вьюхи задач (plan_tasks)
from .views.tasks import (
    TaskBulkDeleteView,
    TaskCreateView,
    TaskDeleteAllView,
    TaskDetailView,
    TaskExecutorsView,
    TaskListView,
)

# Вьюхи пользователей (User + Employee)
from .views.users import (
    DeptEmployeesView,
    UserDetailView,
    UserListView,
    UserPasswordResetView,
)

# Вьюхи отпусков и проверки конфликтов
from .views.vacations import (
    VacationConflictView,
    VacationCreateView,
    VacationDetailView,
    VacationListView,
)

# Вьюхи производственного календаря (WorkCalendar + Holiday)
from .views.work_calendar import (
    HolidayDetailView,
    HolidayListView,
    WorkCalendarCreateView,
    WorkCalendarDetailView,
    WorkCalendarListView,
)

# ── Основные URL-паттерны API ─────────────────────────────────────────────────
urlpatterns = [
    # ── Health check ──────────────────────────────────────────────────────
    path("health/", HealthCheckView.as_view()),
    # ── Справочники ──────────────────────────────────────────────────────
    # GET /api/directories/ — список всех записей справочника
    path("directories/", DirectoryListView.as_view()),
    # POST /api/directories/create/ — создание новой записи (admin)
    path("directories/create/", DirectoryCreateView.as_view()),
    # PUT/DELETE /api/directories/<pk>/ — обновление/удаление записи (admin)
    path("directories/<int:pk>/", DirectoryDetailView.as_view()),
    # ── Пользователи ────────────────────────────────────────────────────
    # GET /api/users/ — список пользователей
    path("users/", UserListView.as_view()),
    # GET/PUT/DELETE /api/users/<pk>/ — детали, обновление, удаление
    path("users/<int:pk>/", UserDetailView.as_view()),
    # POST /api/users/<pk>/password/ — сброс пароля (admin)
    path("users/<int:pk>/password/", UserPasswordResetView.as_view()),
    # GET /api/dept_employees/?dept=CODE — сотрудники отдела (для всех авторизованных)
    path("dept_employees/", DeptEmployeesView.as_view()),
    # ── Делегирования ────────────────────────────────────────────────────
    # GET/POST /api/delegations/ — список и создание делегирований
    path("delegations/", DelegationListView.as_view()),
    # PUT/DELETE /api/delegations/<pk>/ — обновление/удаление делегирования
    path("delegations/<int:pk>/", DelegationDetailView.as_view()),
    # ── Публичные (без авторизации) ─────────────────────────────────────
    # GET /api/dirs_public/ — справочники для формы регистрации (не требует входа)
    path("dirs_public/", DirsPublicView.as_view()),
    # POST /api/register_public/ — публичная регистрация нового пользователя
    path("register_public/", RegisterPublicView.as_view()),
    # ── Настройки колонок ────────────────────────────────────────────────
    # GET/POST /api/col_settings/ — чтение и сохранение ширин/видимости колонок
    path("col_settings/", ColSettingsView.as_view()),
    # ── Задачи (tasks) ──────────────────────────────────────────────────
    # GET /api/tasks/ — список задач с фильтрами и пагинацией
    path("tasks/", TaskListView.as_view()),
    # POST /api/tasks/create/ — создание новой задачи
    path("tasks/create/", TaskCreateView.as_view()),
    # DELETE /api/tasks/all/ — удаление всех задач (только admin)
    path("tasks/all/", TaskDeleteAllView.as_view()),
    # POST /api/tasks/bulk_delete/ — удаление нескольких задач по списку ID
    path("tasks/bulk_delete/", TaskBulkDeleteView.as_view()),
    # GET/PUT/DELETE /api/tasks/<pk>/ — чтение, обновление, удаление задачи
    path("tasks/<int:pk>/", TaskDetailView.as_view()),
    # GET /api/tasks/<pk>/executors/ — список исполнителей задачи
    path("tasks/<int:pk>/executors/", TaskExecutorsView.as_view()),
    # ── Зависимости задач ─────────────────────────────────────────────
    # GET/POST /api/tasks/<pk>/dependencies/ — список и создание зависимостей
    path("tasks/<int:pk>/dependencies/", TaskDependencyListView.as_view()),
    # POST /api/tasks/<pk>/align_dates/ — выравнивание дат по зависимостям
    path("tasks/<int:pk>/align_dates/", AlignDatesView.as_view()),
    # PUT/DELETE /api/dependencies/<pk>/ — обновление/удаление зависимости
    path("dependencies/<int:pk>/", TaskDependencyDetailView.as_view()),
    # GET /api/dependencies/ — все зависимости (для диаграммы Ганта)
    path("dependencies/", AllDependenciesView.as_view()),
    # ── Отчётные документы ──────────────────────────────────────────────
    # GET /api/reports/<task_id>/ — список отчётов по задаче
    path("reports/<int:task_id>/", ReportListView.as_view()),
    # POST /api/reports/ — создание нового отчёта
    path("reports/", ReportCreateView.as_view()),
    # GET/PUT/DELETE /api/reports/<pk>/detail/ — операции с конкретным отчётом
    path("reports/<int:pk>/detail/", ReportDetailView.as_view()),
    # ── Производственный план ────────────────────────────────────────────
    # GET /api/production_plan/ — список записей ПП
    path("production_plan/", ProductionPlanListView.as_view()),
    # POST /api/production_plan/create/ — создание записи ПП
    path("production_plan/create/", ProductionPlanCreateView.as_view()),
    # POST /api/production_plan/sync/ — синхронизация ПП → план задач
    path("production_plan/sync/", ProductionPlanSyncView.as_view()),
    # PUT/DELETE /api/production_plan/<pk>/ — обновление/удаление записи ПП
    path("production_plan/<int:pk>/", ProductionPlanDetailView.as_view()),
    # ── Управление проектами (УП) ────────────────────────────────────────
    # GET /api/projects/ — список УП-проектов
    path("projects/", ProjectListView.as_view()),
    # POST /api/projects/create/ — создание УП-проекта
    path("projects/create/", ProjectCreateView.as_view()),
    # PUT/DELETE /api/projects/<pk>/ — обновление/удаление УП-проекта
    path("projects/<int:pk>/", ProjectDetailView.as_view()),
    # GET /api/projects/<pk>/metrics/ — метрики проекта
    path("projects/<int:project_id>/metrics/", ProjectMetricsView.as_view()),
    # GET /api/projects/<pk>/products/ — список изделий проекта
    path("projects/<int:pk>/products/", ProjectProductListView.as_view()),
    # POST /api/projects/<pk>/products/create/ — создание изделия
    path("projects/<int:pk>/products/create/", ProjectProductCreateView.as_view()),
    # PUT/DELETE /api/projects/<pk>/products/<pid>/ — операции с изделием
    path("projects/<int:pk>/products/<int:pid>/", ProjectProductDetailView.as_view()),
    # ── Проекты ПП ──────────────────────────────────────────────────────
    # GET /api/pp_projects/ — список проектов производственного плана
    path("pp_projects/", PPProjectListView.as_view()),
    # POST /api/pp_projects/create/ — создание проекта ПП (admin)
    path("pp_projects/create/", PPProjectCreateView.as_view()),
    # PUT/DELETE /api/pp_projects/<pk>/ — обновление/удаление проекта ПП (admin)
    path("pp_projects/<int:pk>/", PPProjectDetailView.as_view()),
    # GET /api/pp_projects/<pk>/cross_stages/ — этапы сквозного графика
    path("pp_projects/<int:pk>/cross_stages/", PPCrossStagesView.as_view()),
    # Этапы проекта (PPStage)
    path("projects/<int:pk>/stages/", PPStageListView.as_view()),
    path("projects/<int:pk>/stages/create/", PPStageCreateView.as_view()),
    path("projects/<int:pk>/stages/<int:stage_id>/", PPStageDetailView.as_view()),
    # ── Отпуска ─────────────────────────────────────────────────────────
    # GET /api/vacations/ — список отпусков (с фильтрацией по роли)
    path("vacations/", VacationListView.as_view()),
    # POST /api/vacations/create/ — создание записи об отпуске
    path("vacations/create/", VacationCreateView.as_view()),
    # PUT/DELETE /api/vacations/<pk>/ — обновление/удаление записи об отпуске
    path("vacations/<int:pk>/", VacationDetailView.as_view()),
    # GET /api/check_vacation_conflict/ — проверка пересечений отпусков
    path("check_vacation_conflict/", VacationConflictView.as_view()),
    # POST /api/absence_overlaps/ — проверка пересечений отсутствий (отпуска + командировки)
    path("absence_overlaps/", AbsenceOverlapsView.as_view()),
    # ── Командировки ──────────────────────────────────────────────────
    path("business_trips/", BusinessTripListView.as_view()),
    path("business_trips/<int:pk>/", BusinessTripDetailView.as_view()),
    # ── Журнал извещений ────────────────────────────────────────────────
    # GET /api/journal/ — список записей журнала
    path("journal/", JournalListView.as_view()),
    # POST /api/journal/create/ — создание записи журнала
    path("journal/create/", JournalCreateView.as_view()),
    # GET /api/journal/facets/ — уникальные значения для мульти-фильтров
    path("journal/facets/", JournalFacetsView.as_view()),
    # PUT/DELETE /api/journal/<pk>/ — обновление/удаление записи журнала
    path("journal/<int:pk>/", JournalDetailView.as_view()),
    # ── Замечания и предложения ──────────────────────────────────────────────
    # GET/POST /api/feedback/ — список + создание
    path("feedback/", FeedbackListView.as_view()),
    # PUT/DELETE /api/feedback/<pk>/ — обновление/удаление
    path("feedback/<int:pk>/", FeedbackDetailView.as_view()),
    # DELETE /api/feedback/attachment/<pk>/ — удаление вложения
    path("feedback/attachment/<int:pk>/", FeedbackAttachmentDeleteView.as_view()),
    # ── Песочница (Наборы изменений) ──────────────────────────────────────
    # GET /api/changesets/ — список наборов
    path("changesets/", ChangesetListView.as_view()),
    # POST /api/changesets/create/ — создание набора
    path("changesets/create/", ChangesetCreateView.as_view()),
    # GET/PUT/DELETE /api/changesets/<pk>/ — детали, обновление, удаление
    path("changesets/<int:pk>/", ChangesetDetailView.as_view()),
    # POST /api/changesets/<pk>/items/ — добавление элемента
    path("changesets/<int:pk>/items/", ChangesetItemCreateView.as_view()),
    # POST /api/changesets/<pk>/submit/ — отправка на согласование
    path("changesets/<int:pk>/submit/", ChangesetSubmitView.as_view()),
    # POST /api/changesets/<pk>/approve/ — утверждение
    path("changesets/<int:pk>/approve/", ChangesetApproveView.as_view()),
    # POST /api/changesets/<pk>/reject/ — отклонение
    path("changesets/<int:pk>/reject/", ChangesetRejectView.as_view()),
    # GET /api/changesets/<pk>/diff/ — просмотр diff
    path("changesets/<int:pk>/diff/", ChangesetDiffView.as_view()),
    # POST /api/changesets/<pk>/reopen/ — переоткрытие
    path("changesets/<int:pk>/reopen/", ChangesetReopenView.as_view()),
    # PUT/DELETE /api/changeset_items/<pk>/ — операции с элементом
    path("changeset_items/<int:pk>/", ChangesetItemDetailView.as_view()),
    # ── Производственный календарь ───────────────────────────────────────
    # GET /api/work_calendar/ — список месячных норм рабочего времени
    path("work_calendar/", WorkCalendarListView.as_view()),
    # POST /api/work_calendar/create/ — создание/обновление записи календаря (admin)
    path("work_calendar/create/", WorkCalendarCreateView.as_view()),
    # PUT/DELETE /api/work_calendar/<pk>/ — операции с записью календаря (admin)
    path("work_calendar/<int:pk>/", WorkCalendarDetailView.as_view()),
    # ── Нерабочие дни (Holiday) ────────────────────────────────────────
    # GET/POST /api/holidays/ — список и создание нерабочих дней
    path("holidays/", HolidayListView.as_view()),
    # DELETE /api/holidays/<pk>/ — удаление нерабочего дня (admin)
    path("holidays/<int:pk>/", HolidayDetailView.as_view()),
    # ── Комментарии к задачам ────────────────────────────────────────────
    # GET /api/comments/?work_id=N — список комментариев к задаче
    # POST /api/comments/ — создание комментария
    path("comments/", CommentListView.as_view()),
    # DELETE /api/comments/<pk>/ — удаление комментария
    path("comments/<int:pk>/", CommentDetailView.as_view()),
    # ── Журнал аудита ──────────────────────────────────────────────────
    # GET /api/audit_log/ — список записей аудита (admin)
    path("audit_log/", AuditLogListView.as_view()),
    # ── Аналитика ────────────────────────────────────────────────────
    # GET /api/analytics/workload/ — загрузка по отделам, месяцам, дедлайны
    path("analytics/workload/", WorkloadAnalyticsView.as_view()),
    # GET /api/analytics/employee/ — персональная аналитика сотрудника
    path("analytics/employee/", EmployeeAnalyticsView.as_view()),
    # GET /api/analytics/pp/ — метрики производственного плана
    path("analytics/pp/", PPAnalyticsView.as_view()),
    # GET /api/analytics/plan/ — иерархическая аналитика личного плана (единая)
    path("analytics/plan/", PlanAnalyticsView.as_view()),
    # GET /api/analytics/reports/ — отчёты о выполнении плана
    path("analytics/reports/", ReportsAnalyticsView.as_view()),
    # ── Dashboard ─────────────────────────────────────────────────────
    # GET /api/dashboard/ — личный план + сводка для руководителя
    path("dashboard/", DashboardAPIView.as_view()),
    # GET /api/dashboard/scope/?type=tasks|debts|done_late — ленивая загрузка задач
    path("dashboard/scope/", DashboardScopeView.as_view()),
    # GET /api/dashboard/export/?type=debts|tasks|done_late — экспорт CSV
    path("dashboard/export/", DashboardExportView.as_view()),
    # GET /api/dashboard/employee/<pk>/ — задачи/долги сотрудника (ленивая загрузка)
    path("dashboard/employee/<int:pk>/", DashboardEmployeeView.as_view()),
    # ── Уведомления ────────────────────────────────────────────────────
    # GET /api/notifications/ — список последних 50 уведомлений
    path("notifications/", NotificationListView.as_view()),
    # POST /api/notifications/sync/ — генерация уведомлений о сроках
    path("notifications/sync/", NotificationSyncView.as_view()),
    # POST /api/notifications/<pk>/read/ — пометить как прочитанное
    path("notifications/<int:pk>/read/", NotificationReadView.as_view()),
    # POST /api/notifications/read_all/ — пометить все как прочитанные
    path("notifications/read_all/", NotificationReadAllView.as_view()),
    # GET /api/notifications/unread_count/ — количество непрочитанных
    path("notifications/unread_count/", NotificationUnreadCountView.as_view()),
]

# ── Seed-данные и дамп (только в DEBUG) ────────────────────────────────────
# Импортируем настройки Django для проверки режима DEBUG
from django.conf import settings

if settings.DEBUG:
    # Загрузка дампа данных (только в DEBUG-режиме!)
    from apps.api.views.load_dump import LoadDumpView

    urlpatterns += [
        path("load_dump/", LoadDumpView.as_view()),
    ]

    # В режиме отладки добавляем вспомогательные маршруты для заполнения БД данными
    urlpatterns += [
        # POST /api/seed/ — заполнение базы тестовыми задачами/проектами
        path("seed/", SeedDataView.as_view()),
        # POST /api/seed_executors/ — заполнение исполнителями
        path("seed_executors/", SeedExecutorsView.as_view()),
        # POST /api/seed_vacations/ — заполнение отпусками
        path("seed_vacations/", SeedVacationsView.as_view()),
        # POST /api/seed_analytics/ — отпуска + командировки + plan_hours
        path("seed_analytics/", SeedAnalyticsView.as_view()),
        # POST /api/fill_all/ — заполнение всеми тестовыми данными сразу
        path("fill_all/", FillAllView.as_view()),
        # POST /api/fill_dept/ — заполнение данными конкретного отдела
        path("fill_dept/", FillDeptView.as_view()),
    ]
