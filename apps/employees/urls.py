from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    path('',                    views.EmployeeListView.as_view(),   name='list'),
    path('<int:pk>/',           views.EmployeeDetailView.as_view(), name='detail'),
    path('create/',             views.EmployeeCreateView.as_view(), name='create'),
    path('<int:pk>/edit/',      views.EmployeeUpdateView.as_view(), name='edit'),

    # Глобальный план отпусков
    path('vacations/',                           views.VacationPlanView.as_view(),   name='vacation_plan'),

    # Отпуска конкретного сотрудника
    path('<int:emp_pk>/vacations/',              views.VacationListView.as_view(),   name='vacation_list'),
    path('<int:emp_pk>/vacations/add/',          views.VacationCreateView.as_view(), name='vacation_add'),
    path('vacations/<int:pk>/edit/',             views.VacationUpdateView.as_view(), name='vacation_edit'),
    path('vacations/<int:pk>/delete/',           views.VacationDeleteView.as_view(), name='vacation_delete'),

    # KPI
    path('<int:emp_pk>/kpi/',                    views.KPIListView.as_view(),        name='kpi_list'),
    path('<int:emp_pk>/kpi/add/',                views.KPICreateView.as_view(),      name='kpi_add'),
    path('kpi/<int:pk>/edit/',                   views.KPIUpdateView.as_view(),      name='kpi_edit'),
]
