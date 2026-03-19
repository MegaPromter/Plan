# Импорт функции для объявления URL-маршрутов
from django.urls import path
# Импорт всех view-классов из текущего пакета
from . import views

# Пространство имён приложения — используется в reverse() и {% url %}
app_name = 'works'

urlpatterns = [
    # ── SPA-страницы (одностраничные приложения на JS) ─────────────────────────

    # Управление проектами SPA (модуль 1)
    path('projects/',           views.ProjectsSPAView.as_view(),        name='projects'),
    # План/Отчёт SPA (главная рабочая страница)
    path('plan/',               views.PlanSPAView.as_view(),            name='plan'),
    # Производственный план SPA (оба варианта URL)
    path('production-plan/',    views.ProductionPlanSPAView.as_view(),  name='production_plan'),
    # Дополнительный алиас с нижним подчёркиванием (для совместимости)
    path('production_plan/',    views.ProductionPlanSPAView.as_view(),  name='production_plan_alt'),
    # Производственный календарь (только admin)
    path('work-calendar/',      views.WorkCalendarSPAView.as_view(),    name='work_calendar'),
    # План командировок
    path('business-trips/',     views.BusinessTripsSPAView.as_view(),   name='business_trips'),
    # Журнал аудита (только admin)
    path('audit-log/',          views.AuditLogSPAView.as_view(),        name='audit_log'),
    # Аналитика: загрузка сотрудников
    path('analytics-workload/', views.AnalyticsWorkloadSPAView.as_view(), name='analytics_workload'),
    # Аналитика: доска сотрудника
    path('analytics-employee/', views.AnalyticsEmployeeSPAView.as_view(), name='analytics_employee'),
    # Аналитика: отчёты ПП
    path('analytics-pp/', views.AnalyticsPPSPAView.as_view(), name='analytics_pp'),
    # Аналитика: единая страница (новая)
    path('analytics/', views.AnalyticsSPAView.as_view(), name='analytics'),

    # ── Стандартные CRUD-маршруты для работ ────────────────────────────────────

    # Список работ (с фильтрацией по видимости пользователя)
    path('',                    views.WorkListView.as_view(),    name='list'),
    # Детальная страница одной работы
    path('<int:pk>/',           views.WorkDetailView.as_view(),  name='detail'),
    # Форма создания новой работы
    path('create/',             views.WorkCreateView.as_view(),  name='create'),
    # Форма редактирования существующей работы
    path('<int:pk>/edit/',      views.WorkUpdateView.as_view(),  name='edit'),
    # Подтверждение и выполнение удаления работы
    path('<int:pk>/delete/',    views.WorkDeleteView.as_view(),  name='delete'),

    # ── Отчётные документы к работам ───────────────────────────────────────────

    # Добавление нового отчётного документа к работе
    path('<int:work_pk>/reports/add/',       views.ReportCreateView.as_view(), name='report_add'),
    # Редактирование существующего отчётного документа
    path('reports/<int:pk>/edit/',           views.ReportUpdateView.as_view(), name='report_edit'),
    # Удаление отчётного документа
    path('reports/<int:pk>/delete/',         views.ReportDeleteView.as_view(), name='report_delete'),

    # ── Журнал корректирующих извещений ────────────────────────────────────────

    # Список всех извещений
    path('notices/',             views.NoticeListView.as_view(),   name='notice_list'),
    # Создание нового извещения
    path('notices/add/',         views.NoticeCreateView.as_view(), name='notice_add'),
    # Детальная страница извещения
    path('notices/<int:pk>/',    views.NoticeDetailView.as_view(), name='notice_detail'),
    # Редактирование извещения
    path('notices/<int:pk>/edit/', views.NoticeUpdateView.as_view(), name='notice_edit'),
]

# ── Демо-страницы для показа улучшений дизайна (только DEBUG) ────────────
from django.conf import settings as django_settings
if django_settings.DEBUG:
    urlpatterns += [
        path('demo/density/',  views.DemoDensityView.as_view(),  name='demo_density'),
        path('demo/skeleton/', views.DemoSkeletonView.as_view(), name='demo_skeleton'),
        path('demo/slideout/', views.DemoSlideoutView.as_view(), name='demo_slideout'),
        path('demo/trips/<int:num>/', views.DemoTripsView.as_view(), name='demo_trips'),
        path('demo/pp-filter/<int:num>/', views.DemoPPFilterView.as_view(), name='demo_pp_filter'),
    ]
