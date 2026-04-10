"""
URL-маршрутизация API модуля «Управление предприятием».
Все маршруты подключаются как /api/enterprise/*.
"""

from django.urls import path

from .views.baseline import (
    BaselineDetailView,
    BaselineListView,
    ScenarioDetailView,
    ScenarioEntryCreateView,
    ScenarioListView,
)
from .views.capacity import CapacityView
from .views.cross_schedule import (
    CrossDeptStatusDetailView,
    CrossDeptStatusListView,
    CrossMilestoneCreateView,
    CrossMilestoneDetailView,
    CrossScheduleDetailView,
    CrossStageCreateView,
    CrossStageDetailView,
    CrossStageWorksView,
)
from .views.gg import (
    GGDetailView,
    GGMilestoneCreateView,
    GGMilestoneDetailView,
    GGStageCreateView,
    GGStageDependencyCreateView,
    GGStageDependencyDetailView,
    GGStageDetailView,
    GGTemplateDetailView,
    GGTemplateListView,
)
from .views.notifications import (
    EntNotificationListView,
    EntNotificationReadAllView,
    EntNotificationReadView,
    EntNotificationUnreadCountView,
)
from .views.portfolio import (
    PortfolioDetailView,
    PortfolioListView,
    PortfolioPriorityView,
)

app_name = "enterprise"

urlpatterns = [
    # ── Портфель проектов ─────────────────────────────────────────────────
    path("portfolio/", PortfolioListView.as_view()),
    path("portfolio/<int:pk>/", PortfolioDetailView.as_view()),
    path("portfolio/<int:pk>/priority/", PortfolioPriorityView.as_view()),
    # ── Генеральный график (ГГ) ───────────────────────────────────────────
    path("gg/<int:project_id>/", GGDetailView.as_view()),
    path("gg/<int:project_id>/stages/", GGStageCreateView.as_view()),
    path("gg/<int:project_id>/milestones/", GGMilestoneCreateView.as_view()),
    path("gg_stages/<int:pk>/", GGStageDetailView.as_view()),
    path("gg_milestones/<int:pk>/", GGMilestoneDetailView.as_view()),
    path("gg_stage_deps/", GGStageDependencyCreateView.as_view()),
    path("gg_stage_deps/<int:pk>/", GGStageDependencyDetailView.as_view()),
    # ── Шаблоны ГГ ────────────────────────────────────────────────────────
    path("gg_templates/", GGTemplateListView.as_view()),
    path("gg_templates/<int:pk>/", GGTemplateDetailView.as_view()),
    # ── Сквозной график ───────────────────────────────────────────────────
    path("cross/<int:project_id>/", CrossScheduleDetailView.as_view()),
    path("cross/<int:project_id>/stages/", CrossStageCreateView.as_view()),
    path("cross/<int:project_id>/milestones/", CrossMilestoneCreateView.as_view()),
    path("cross/<int:project_id>/dept_status/", CrossDeptStatusListView.as_view()),
    path("cross_stages/<int:pk>/", CrossStageDetailView.as_view()),
    path("cross_stages/<int:pk>/works/", CrossStageWorksView.as_view()),
    path("cross_milestones/<int:pk>/", CrossMilestoneDetailView.as_view()),
    path("cross_dept_status/<int:pk>/", CrossDeptStatusDetailView.as_view()),
    # ── Baseline (версии) ─────────────────────────────────────────────────
    path("cross/<int:project_id>/baselines/", BaselineListView.as_view()),
    path("baselines/<int:pk>/", BaselineDetailView.as_view()),
    # ── Сценарии (что-если) ───────────────────────────────────────────────
    path("scenarios/", ScenarioListView.as_view()),
    path("scenarios/<int:pk>/", ScenarioDetailView.as_view()),
    path("scenarios/<int:pk>/entries/", ScenarioEntryCreateView.as_view()),
    # ── Загрузка и мощность ───────────────────────────────────────────────
    path("capacity/", CapacityView.as_view()),
    # ── Уведомления ───────────────────────────────────────────────────────
    path("notifications/", EntNotificationListView.as_view()),
    path("notifications/<int:pk>/read/", EntNotificationReadView.as_view()),
    path("notifications/read_all/", EntNotificationReadAllView.as_view()),
    path("notifications/unread_count/", EntNotificationUnreadCountView.as_view()),
]
