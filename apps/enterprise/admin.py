from django.contrib import admin

from .models import (
    GGTemplate, GGTemplateStage,
    GeneralSchedule, GGStage, GGMilestone, GGStageDependency,
    CrossSchedule, CrossScheduleDeptStatus, CrossStage, CrossMilestone,
    BaselineSnapshot, BaselineEntry,
    Scenario, ScenarioEntry,
    EnterpriseNotification,
)


# --- ГГ (Генеральный график) ------------------------------------------------

class GGTemplateStageInline(admin.TabularInline):
    model = GGTemplateStage
    extra = 1


@admin.register(GGTemplate)
class GGTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'created_at')
    inlines = [GGTemplateStageInline]


class GGStageInline(admin.TabularInline):
    model = GGStage
    extra = 0
    fields = ('name', 'date_start', 'date_end', 'labor', 'order', 'parent_stage')


class GGMilestoneInline(admin.TabularInline):
    model = GGMilestone
    extra = 0


@admin.register(GeneralSchedule)
class GeneralScheduleAdmin(admin.ModelAdmin):
    list_display = ('project', 'created_by', 'created_at', 'updated_at')
    inlines = [GGStageInline, GGMilestoneInline]


@admin.register(GGStageDependency)
class GGStageDependencyAdmin(admin.ModelAdmin):
    list_display = ('predecessor', 'successor', 'dep_type', 'lag_days')


# --- Сквозной график --------------------------------------------------------

class CrossStageInline(admin.TabularInline):
    model = CrossStage
    extra = 0
    fields = ('name', 'date_start', 'date_end', 'department', 'order', 'gg_stage')


class CrossMilestoneInline(admin.TabularInline):
    model = CrossMilestone
    extra = 0


class CrossScheduleDeptStatusInline(admin.TabularInline):
    model = CrossScheduleDeptStatus
    extra = 0


@admin.register(CrossSchedule)
class CrossScheduleAdmin(admin.ModelAdmin):
    list_display = ('project', 'version', 'edit_owner', 'granularity', 'created_at')
    list_filter = ('edit_owner', 'granularity')
    inlines = [CrossScheduleDeptStatusInline, CrossStageInline, CrossMilestoneInline]


# --- Версионирование --------------------------------------------------------

class BaselineEntryInline(admin.TabularInline):
    model = BaselineEntry
    extra = 0
    readonly_fields = ('data',)


@admin.register(BaselineSnapshot)
class BaselineSnapshotAdmin(admin.ModelAdmin):
    list_display = ('cross_schedule', 'version', 'created_by', 'created_at')
    inlines = [BaselineEntryInline]


# --- Сценарии ---------------------------------------------------------------

class ScenarioEntryInline(admin.TabularInline):
    model = ScenarioEntry
    extra = 0
    readonly_fields = ('data',)


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'status', 'created_by', 'created_at')
    list_filter = ('status',)
    inlines = [ScenarioEntryInline]


# --- Уведомления ------------------------------------------------------------

@admin.register(EnterpriseNotification)
class EnterpriseNotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('title', 'message')
