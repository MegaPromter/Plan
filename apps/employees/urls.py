# Импорт функции для объявления URL-маршрутов
from django.urls import path
# Импорт всех view-классов из текущего пакета
from . import views

# Пространство имён приложения — используется в reverse() и {% url %}
app_name = 'employees'

urlpatterns = [
    # ── Сотрудники (CRUD) ──────────────────────────────────────────────────────

    # Список всех сотрудников (с поиском и фильтрацией по отделу)
    path('',                    views.EmployeeListView.as_view(),   name='list'),
    # Детальная страница конкретного сотрудника
    path('<int:pk>/',           views.EmployeeDetailView.as_view(), name='detail'),
    # Форма создания нового сотрудника (только для admin)
    path('create/',             views.EmployeeCreateView.as_view(), name='create'),
    # Форма редактирования сотрудника (для writer-ролей)
    path('<int:pk>/edit/',      views.EmployeeUpdateView.as_view(), name='edit'),

    # ── Глобальный план отпусков ────────────────────────────────────────────────

    # Все отпуска всех сотрудников (с фильтрацией по отделу, году, имени)
    path('vacations/',                           views.VacationPlanView.as_view(),   name='vacation_plan'),

    # ── Отпуска конкретного сотрудника ─────────────────────────────────────────

    # Список отпусков сотрудника (emp_pk — ID сотрудника в URL)
    path('<int:emp_pk>/vacations/',              views.VacationListView.as_view(),   name='vacation_list'),
    # Добавление нового отпуска сотруднику
    path('<int:emp_pk>/vacations/add/',          views.VacationCreateView.as_view(), name='vacation_add'),
    # Редактирование существующего отпуска
    path('vacations/<int:pk>/edit/',             views.VacationUpdateView.as_view(), name='vacation_edit'),
    # Удаление записи об отпуске
    path('vacations/<int:pk>/delete/',           views.VacationDeleteView.as_view(), name='vacation_delete'),

    # ── KPI сотрудника ─────────────────────────────────────────────────────────

    # Список всех KPI-записей сотрудника
    path('<int:emp_pk>/kpi/',                    views.KPIListView.as_view(),        name='kpi_list'),
    # Добавление новой KPI-записи за период
    path('<int:emp_pk>/kpi/add/',                views.KPICreateView.as_view(),      name='kpi_add'),
    # Редактирование существующей KPI-записи
    path('kpi/<int:pk>/edit/',                   views.KPIUpdateView.as_view(),      name='kpi_edit'),
]
