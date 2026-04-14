# Импорт функции для объявления URL-маршрутов
from django.urls import path

# Импорт всех view-классов из текущего пакета
from . import views

# Пространство имён приложения — используется в reverse() и {% url %}
app_name = "works"

urlpatterns = [
    # ── SPA-страницы (одностраничные приложения на JS) ─────────────────────────
    # Управление проектами SPA (модуль 1)
    path("projects/", views.ProjectsSPAView.as_view(), name="projects"),
    # План/Отчёт SPA (главная рабочая страница)
    path("plan/", views.PlanSPAView.as_view(), name="plan"),
    # Производственный план SPA (оба варианта URL)
    path(
        "production-plan/",
        views.ProductionPlanSPAView.as_view(),
        name="production_plan",
    ),
    # Дополнительный алиас с нижним подчёркиванием (для совместимости)
    path(
        "production_plan/",
        views.ProductionPlanSPAView.as_view(),
        name="production_plan_alt",
    ),
    # Производственный календарь (только admin)
    path("work-calendar/", views.WorkCalendarSPAView.as_view(), name="work_calendar"),
    # План командировок
    path(
        "business-trips/", views.BusinessTripsSPAView.as_view(), name="business_trips"
    ),
    # Журнал аудита (только admin)
    path("audit-log/", views.AuditLogSPAView.as_view(), name="audit_log"),
    # Аналитика: загрузка сотрудников
    path(
        "analytics-workload/",
        views.AnalyticsWorkloadSPAView.as_view(),
        name="analytics_workload",
    ),
    # Аналитика: доска сотрудника
    path(
        "analytics-employee/",
        views.AnalyticsEmployeeSPAView.as_view(),
        name="analytics_employee",
    ),
    # Аналитика: отчёты ПП
    path("analytics-pp/", views.AnalyticsPPSPAView.as_view(), name="analytics_pp"),
    # Аналитика: единая страница (новая)
    path("analytics/", views.AnalyticsSPAView.as_view(), name="analytics"),
    # Отчёты: drill-down по оргструктуре
    path("reports/", views.ReportsSPAView.as_view(), name="reports"),
    # Замечания и предложения
    path("feedback/", views.FeedbackSPAView.as_view(), name="feedback"),
    # ER-диаграмма моделей
    path("er-diagram/", views.ERDiagramView.as_view(), name="er_diagram"),
    # Делегирование прав SPA
    path("delegations/", views.DelegationsSPAView.as_view(), name="delegations"),
    # Управление предприятием SPA
    path("enterprise/", views.EnterpriseSPAView.as_view(), name="enterprise"),
    # ── Журнал корректирующих извещений (SPA) ─────────────────────────────────
    # Список извещений (SPA-страница, CRUD — через API /api/journal/)
    path("notices/", views.NoticeListView.as_view(), name="notice_list"),
]

# ── Демо-страницы для показа улучшений дизайна (только DEBUG) ────────────
from django.conf import settings as django_settings

if django_settings.DEBUG:
    urlpatterns += [
        path("demo/density/", views.DemoDensityView.as_view(), name="demo_density"),
        path("demo/skeleton/", views.DemoSkeletonView.as_view(), name="demo_skeleton"),
        path("demo/slideout/", views.DemoSlideoutView.as_view(), name="demo_slideout"),
        path("demo/trips/<int:num>/", views.DemoTripsView.as_view(), name="demo_trips"),
        path(
            "demo/pp-filter/<int:num>/",
            views.DemoPPFilterView.as_view(),
            name="demo_pp_filter",
        ),
    ]
