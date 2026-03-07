from django.urls import path
from . import views

app_name = 'works'

urlpatterns = [
    # Управление проектами SPA (модуль 1)
    path('projects/',           views.ProjectsSPAView.as_view(),        name='projects'),
    # План/Отчёт SPA (главная рабочая страница)
    path('plan/',               views.PlanSPAView.as_view(),            name='plan'),
    # Производственный план SPA (оба варианта URL)
    path('production-plan/',    views.ProductionPlanSPAView.as_view(),  name='production_plan'),
    path('production_plan/',    views.ProductionPlanSPAView.as_view(),  name='production_plan_alt'),
    # Производственный календарь (только admin)
    path('work-calendar/',      views.WorkCalendarSPAView.as_view(),    name='work_calendar'),

    # Список работ
    path('',                    views.WorkListView.as_view(),    name='list'),
    path('<int:pk>/',           views.WorkDetailView.as_view(),  name='detail'),
    path('create/',             views.WorkCreateView.as_view(),  name='create'),
    path('<int:pk>/edit/',      views.WorkUpdateView.as_view(),  name='edit'),
    path('<int:pk>/delete/',    views.WorkDeleteView.as_view(),  name='delete'),

    # Отчётные документы
    path('<int:work_pk>/reports/add/',       views.ReportCreateView.as_view(), name='report_add'),
    path('reports/<int:pk>/edit/',           views.ReportUpdateView.as_view(), name='report_edit'),
    path('reports/<int:pk>/delete/',         views.ReportDeleteView.as_view(), name='report_delete'),

    # Журнал извещений
    path('notices/',             views.NoticeListView.as_view(),   name='notice_list'),
    path('notices/add/',         views.NoticeCreateView.as_view(), name='notice_add'),
    path('notices/<int:pk>/',    views.NoticeDetailView.as_view(), name='notice_detail'),
    path('notices/<int:pk>/edit/', views.NoticeUpdateView.as_view(), name='notice_edit'),
]
