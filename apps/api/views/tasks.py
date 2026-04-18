"""
API задач (Work, show_in_plan=True).

Эндпоинты:
  GET    /api/tasks           — список задач с фильтрацией и пагинацией
  POST   /api/tasks           — создание задачи
  PUT    /api/tasks/<id>      — обновление задачи (+ оптимистичная блокировка, _mcc_finish)
  DELETE /api/tasks/<id>      — удаление задачи
  DELETE /api/tasks/all       — удаление ВСЕХ задач (admin)
  GET    /api/tasks/<id>/executors — список исполнителей задачи
"""

import logging
from datetime import date as dt_date

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.audit import log_action
from apps.api.drf_utils import IsAdminPermission, IsWriterPermission
from apps.api.utils import (
    generate_work_num,
    get_visibility_filter,
    mcc_finish_data,
    parse_json_hours,
    resolve_employee,
    short_name,
    validate_actions,
    validate_executors_list,
    validate_plan_hours,
    validate_task_type,
)
from apps.api.views.reports import _sync_notices_for_work
from apps.employees.models import Department, Employee, Sector
from apps.works.models import AuditLog, Project, TaskExecutor, Work, WorkReport

logger = logging.getLogger(__name__)

TASKS_MAX = 5000


# ---------------------------------------------------------------------------
#  Сериализация
# ---------------------------------------------------------------------------


def _build_pp_justification(work):
    """Формирует обоснование для ПП-записи: «ПП-план; Этап X; Веха Y; Работа Z»."""
    pp_plan_name = (work.pp_project.name or "") if work.pp_project else ""
    parts = [pp_plan_name] if pp_plan_name else []
    if work.stage_num:
        parts.append(f"Этап {work.stage_num}")
    if work.work_num:
        parts.append(f"№ работы {work.work_num}")
    return "; ".join(parts)


def _serialize_task(work, executors_data=None, sector_heads=None):
    """
    Сериализует Work (show_in_plan=True) в плоский dict для JSON-ответа.
    Поля stage_num, work_num, work_designation — единые для ПП и СП.
    Для ПП-записей проект берётся из pp_project.up_project,
    обоснование формируется из ПП-полей, deadline = date_end.
    sector_heads — словарь {sector_code: short_name} для ФИО начальников секторов.
    """
    is_from_pp = work.show_in_pp

    # Проект: для ПП → pp_project.up_project, для чистых СП → project
    if is_from_pp:
        up_project = work.pp_project.up_project if work.pp_project else None
        project_name = (up_project.name if up_project else "") or ""
    else:
        project_name = (work.project.name if work.project else "") or ""

    # Трудоёмкость ПП (для справки)
    pp_labor_val = ""
    if is_from_pp and work.labor is not None:
        pp_labor_val = str(float(work.labor))

    # Сектор: всегда через FK
    sector_val = (work.sector.code if work.sector else "") or ""

    d = {
        "id": work.id,
        "row_code": (work.pp_stage.row_code if work.pp_stage else work.row_code) or "",
        "work_order": (work.pp_stage.work_order if work.pp_stage else work.work_order)
        or "",
        "task_type": (
            (work.task_type or "Выпуск нового документа")
            if is_from_pp
            else (work.task_type or "")
        ),
        "dept": (work.department.code if work.department else "") or "",
        "sector": sector_val,
        "project": project_name,
        "work_name": work.work_name or "",
        # Единые поля (и ПП, и СП пишут/читают одни и те же колонки)
        "work_number": work.work_num or "",
        "description": work.work_designation or "",
        "executor": (work.executor.full_name if work.executor else "") or "",
        "date_start": work.date_start.isoformat() if work.date_start else "",
        "date_end": work.date_end.isoformat() if work.date_end else "",
        "pp_date_start": work.pp_date_start.isoformat() if work.pp_date_start else "",
        "pp_date_end": work.pp_date_end.isoformat() if work.pp_date_end else "",
        # Приоритет: date_end (ПП) → deadline (СП)
        "deadline": (
            (work.date_end or work.deadline).isoformat()
            if (work.date_end or work.deadline)
            else ""
        ),
        "plan_hours": work.plan_hours or {},
        "created_by": work.created_by_id,
        "created_at": work.created_at.isoformat() if work.created_at else "",
        "updated_at": work.updated_at.isoformat() if work.updated_at else "",
        "center": (work.ntc_center.code if work.ntc_center else "") or "",
        # Единое поле этапа; обоснование для ПП формируется на лету
        "stage": work.stage_num or "",
        "justification": (
            _build_pp_justification(work) if is_from_pp else (work.justification or "")
        ),
        "actions": work.actions or {},
        "sector_head": (
            (sector_heads or {}).get(work.sector.code, "") if work.sector else ""
        ),
        "norm": float(work.norm) if work.norm is not None else None,
    }

    # Список исполнителей
    execs = executors_data or []
    d["executors_list"] = execs

    # Агрегация plan_hours по всем исполнителям
    ph_all = {}
    for ex in execs:
        for k, v in (ex.get("hours") or {}).items():
            try:
                ph_all[k] = ph_all.get(k, 0) + (float(v) if v else 0)
            except (ValueError, TypeError):
                pass
    d["plan_hours_all"] = ph_all

    d["pp_labor"] = pp_labor_val
    d["from_pp"] = is_from_pp
    d["predecessors_count"] = getattr(work, "_pred_count", 0) or 0
    d["has_reports"] = bool(getattr(work, "_has_reports", False))

    # Дата заполнения отчёта (для привязки статуса к периоду на клиенте)
    rca = getattr(work, "_report_created_at", None)
    d["report_created_at"] = rca.isoformat() if rca else ""

    # Индикатор просроченности: приоритет date_end (ПП) → deadline (СП)
    today = timezone.now().date()
    effective_deadline = work.date_end or work.deadline
    has_reports = d["has_reports"]
    d["is_overdue"] = bool(
        not has_reports and effective_deadline and effective_deadline < today
    )

    return d


# ---------------------------------------------------------------------------
#  GET / POST  /api/tasks
# ---------------------------------------------------------------------------


class TaskListView(APIView):
    permission_classes = [IsAuthenticated]

    """GET — список задач."""

    def get(self, request):
        try:
            return self._get_tasks(request)
        except (ValueError, TypeError) as e:
            logger.warning("TaskListView.get bad request: %s", e)
            return Response({"error": f"Некорректные параметры: {e}"}, status=400)
        except Exception as e:
            logger.error("TaskListView.get error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def _get_tasks(self, request):
        try:
            limit = int(request.GET.get("limit", 0)) or TASKS_MAX
        except (ValueError, TypeError):
            limit = TASKS_MAX
        limit = min(limit, TASKS_MAX)

        try:
            offset = max(int(request.GET.get("offset", 0)), 0)
        except (ValueError, TypeError):
            offset = 0

        year = request.GET.get("year")
        month = request.GET.get("month")
        if request.GET.get("all") == "1":
            year = None
            month = None
        search = request.GET.get("search", "").strip().lower()

        # Только задачи (не строки ПП)
        # СП — общий документ, видимый всем (аналогично ПП)
        qs = Work.objects.filter(show_in_plan=True)

        # Фильтр по периоду
        if year and month:
            try:
                yr = int(year)
                mn = int(month)
                if not (1 <= mn <= 12) or not (1900 <= yr <= 2100):
                    raise ValueError(f"Недопустимый период: {yr}-{mn}")
                from datetime import date

                sel_start = date(yr, mn, 1)
                sel_end = date(yr, mn + 1, 1) if mn < 12 else date(yr + 1, 1, 1)
                today = timezone.now().date()
                qs = qs.filter(
                    Q(
                        date_start__isnull=True,
                        date_end__isnull=True,
                        deadline__isnull=True,
                    )
                    | Q(date_start__lt=sel_end, date_end__gte=sel_start)
                    | Q(
                        date_start__lt=sel_end,
                        date_end__isnull=True,
                        deadline__gte=sel_start,
                    )
                    | Q(
                        date_start__lt=sel_end,
                        date_end__isnull=True,
                        deadline__isnull=True,
                    )
                    | Q(date_end__gte=sel_start, date_start__isnull=True)
                    | Q(
                        date_end__isnull=True,
                        deadline__gte=sel_start,
                        date_start__isnull=True,
                    )
                    # Просроченные: date_end прошёл, отчёта нет — тянутся до текущего месяца
                    | (
                        Q(date_end__lt=min(sel_start, today))
                        & ~Exists(WorkReport.objects.filter(work_id=OuterRef("pk")))
                        if sel_start <= today
                        else Q()
                    )
                    # Долги, закрытые в выбранном месяце: дедлайн был до месяца,
                    # но отчёт сдан именно в этом месяце. Нужно, чтобы клик по
                    # «Закрыто в этом месяце» в снимке показывал те же задачи.
                    | (
                        Q(date_end__lt=sel_start)
                        & Exists(
                            WorkReport.objects.filter(
                                work_id=OuterRef("pk"),
                                created_at__gte=sel_start,
                                created_at__lt=sel_end,
                            )
                        )
                    )
                )
                # Исключить задачи с отчётом, заполненным до начала выбранного месяца
                qs = qs.exclude(
                    Exists(
                        WorkReport.objects.filter(
                            work_id=OuterRef("pk"),
                            created_at__lt=sel_start,
                        )
                    )
                )
            except (ValueError, TypeError):
                pass
        elif year:
            try:
                yr = int(year)
                if not (1900 <= yr <= 2100):
                    raise ValueError(f"Недопустимый год: {yr}")
                from datetime import date

                yr_start = date(yr, 1, 1)
                yr_end = date(yr + 1, 1, 1)
                qs = qs.filter(
                    Q(
                        date_start__isnull=True,
                        date_end__isnull=True,
                        deadline__isnull=True,
                    )
                    | Q(date_start__lt=yr_end, date_end__gte=yr_start)
                    | Q(
                        date_start__lt=yr_end,
                        date_end__isnull=True,
                        deadline__gte=yr_start,
                    )
                    | Q(
                        date_start__lt=yr_end,
                        date_end__isnull=True,
                        deadline__isnull=True,
                    )
                    | Q(date_end__gte=yr_start, date_start__isnull=True)
                    | Q(
                        date_end__isnull=True,
                        deadline__gte=yr_start,
                        date_start__isnull=True,
                    )
                )
                # Исключить задачи с отчётом, заполненным до начала года
                qs = qs.exclude(
                    Exists(
                        WorkReport.objects.filter(
                            work_id=OuterRef("pk"),
                            created_at__lt=yr_start,
                        )
                    )
                )
            except (ValueError, TypeError):
                pass

        # Полнотекстовый поиск
        if search:
            s = search
            qs = qs.filter(
                Q(work_name__icontains=s)
                | Q(executor__last_name__icontains=s)
                | Q(executor__first_name__icontains=s)
                | Q(department__code__icontains=s)
                | Q(work_designation__icontains=s)
                | Q(project__name_short__icontains=s)
                | Q(project__name_full__icontains=s)
                | Q(pp_project__up_project__name_short__icontains=s)
                | Q(pp_project__up_project__name_full__icontains=s)
                | Q(task_type__icontains=s)
                | Q(work_num__icontains=s)
            )

        total_count = qs.count()

        qs = (
            qs.defer(
                "executors_list",
            )
            .annotate(
                _pred_count=Count("predecessor_links"),
                _has_reports=Exists(WorkReport.objects.filter(work_id=OuterRef("pk"))),
                _report_created_at=Subquery(
                    WorkReport.objects.filter(work_id=OuterRef("pk"))
                    .order_by("created_at")
                    .values("created_at")[:1]
                ),
            )
            .select_related(
                "department",
                "sector",
                "project",
                "executor",
                "ntc_center",
                "created_by",
                "pp_project",
                "pp_project__up_project",
                "pp_stage",
            )
            .prefetch_related(
                "task_executors",
                "task_executors__executor",
            )
            .order_by("-id")
        )
        qs = qs[offset : offset + limit]

        works = list(qs)

        # Собираем исполнителей из prefetch-кэша
        executors_data = {}
        for w in works:
            execs = []
            for te in w.task_executors.all():
                execs.append(
                    {
                        "name": (
                            te.executor.full_name if te.executor else te.executor_name
                        ),
                        "hours": parse_json_hours(te.plan_hours),
                    }
                )
            if execs:
                executors_data[w.id] = execs

        # Ключ месяца для plan_hours_month
        month_key = None
        if year and month:
            try:
                month_key = f"{int(year)}-{int(month):02d}"
            except (ValueError, TypeError):
                month_key = None

        # Словарь ФИО начальников секторов: {sector_code: "Фамилия И.О."}
        # Кешируется на 1 час (статичные справочные данные)
        sector_heads = cache.get("sector_heads_map")
        if sector_heads is None:
            sector_heads = {}
            for emp in Employee.objects.filter(
                role=Employee.ROLE_SECTOR_HEAD
            ).select_related("sector"):
                if emp.sector:
                    sector_heads[emp.sector.code] = short_name(emp.full_name)
            cache.set("sector_heads_map", sector_heads, 3600)

        result = []
        for w in works:
            execs = executors_data.get(w.id, [])
            d = _serialize_task(w, executors_data=execs, sector_heads=sector_heads)
            d["plan_hours_month"] = (
                d["plan_hours_all"].get(month_key, "") if month_key else ""
            )
            result.append(d)

        response = Response(result)
        response["X-Total-Count"] = total_count
        response["X-Has-More"] = "true" if (offset + limit) < total_count else "false"
        response["Cache-Control"] = "private, max-age=5"
        return response


class TaskCreateView(APIView):
    permission_classes = [IsWriterPermission]

    """POST /api/tasks — создание задачи."""

    def post(self, request):
        try:
            return self._create(request)
        except (ValueError, TypeError) as e:
            logger.warning("TaskCreateView bad request: %s", e)
            return Response({"error": f"Некорректные данные: {e}"}, status=400)
        except Exception as e:
            logger.error("TaskCreateView error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def _create(self, request):
        d = request.data
        if not isinstance(d, dict):
            return Response({"error": "Невалидный JSON"}, status=400)
        if not d:
            return Response({"error": "Пустое тело запроса"}, status=400)

        employee = getattr(request.user, "employee", None)

        # Проверка прав по роли
        if employee and employee.role in ("dept_head", "dept_deputy"):
            if not employee.department:
                return Response(
                    {"error": "Вашему профилю не назначен отдел"}, status=403
                )
            dept_val = (d.get("dept") or "").strip()
            if dept_val and dept_val != employee.department.code:
                return Response(
                    {"error": "Вы можете создавать задачи только для своего отдела"},
                    status=403,
                )

        if employee and employee.role == "sector_head":
            if not employee.department:
                return Response(
                    {"error": "Вашему профилю не назначен отдел"}, status=403
                )
            dept_val = (d.get("dept") or "").strip()
            if dept_val and dept_val != employee.department.code:
                return Response(
                    {"error": "Вы можете создавать задачи только для своего отдела"},
                    status=403,
                )
            sector_val = (d.get("sector") or "").strip()
            if sector_val and employee.sector:
                own_sector_values = {employee.sector.code, employee.sector.name}
                if sector_val not in own_sector_values:
                    return Response(
                        {
                            "error": "Вы можете создавать задачи только для своего сектора"
                        },
                        status=403,
                    )

        ph, ph_err = validate_plan_hours(d.get("plan_hours"))
        if ph_err:
            return Response({"error": ph_err}, status=400)

        executors_list, el_err = validate_executors_list(d.get("executors_list"))
        if el_err:
            return Response({"error": el_err}, status=400)

        actions, act_err = validate_actions(d.get("actions"))
        if act_err:
            return Response({"error": act_err}, status=400)

        with transaction.atomic():
            work = Work(
                show_in_plan=True,
                work_name=d.get("work_name") or "",
                work_num="",  # авто-генерация ниже
                work_designation=d.get("description") or "",
                plan_hours=ph,
                stage_num=d.get("stage") or "",
                justification=d.get("justification") or "",
                actions=actions,
                created_by=employee,
            )

            if "task_type" in d:
                tt_val, tt_err = validate_task_type(d["task_type"])
                if tt_err:
                    return Response({"error": tt_err}, status=400)
                d["task_type"] = tt_val

            _set_work_fk_fields(work, d, request)
            try:
                _set_date_fields(work, d)
            except ValueError as exc:
                return Response({"error": str(exc)}, status=400)

            # Если deadline не задан — подставляем date_end
            if not work.deadline and work.date_end:
                work.deadline = work.date_end

            # Автогенерация номера работы
            if not work.work_num and work.project:
                work.work_num = generate_work_num(work.project)

            work.save()

            if executors_list:
                _save_executors(work, executors_list)

        log_action(
            request,
            AuditLog.ACTION_TASK_CREATE,
            object_id=work.id,
            object_repr=work.work_name,
        )
        return Response({"id": work.id})


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/tasks/<id>
# ---------------------------------------------------------------------------


class TaskDetailView(APIView):
    permission_classes = [IsWriterPermission]

    """PUT /api/tasks/<id>; DELETE /api/tasks/<id>."""

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except (ValueError, TypeError) as e:
            logger.warning("TaskDetailView.put bad request: %s", e)
            return Response({"error": f"Некорректные данные: {e}"}, status=400)
        except Exception as e:
            logger.error("TaskDetailView.put error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def delete(self, request, pk):
        try:
            vis_q = get_visibility_filter(request.user)
            with transaction.atomic():
                # select_for_update: блокируем строку от конкурентных изменений
                work = (
                    Work.objects.select_for_update()
                    .filter(pk=pk, show_in_plan=True)
                    .filter(vis_q)
                    .first()
                )
                if not work:
                    return Response({"error": "Задача не найдена"}, status=404)
                log_action(
                    request,
                    AuditLog.ACTION_TASK_DELETE,
                    object_id=work.id,
                    object_repr=work.work_name,
                )
                if work.show_in_pp:
                    # Запись видна и в ПП — только убираем из СП, не удаляя
                    work.show_in_plan = False
                    work.actions = {}
                    work.save(update_fields=["show_in_plan", "actions"])
                else:
                    work.delete()
            return Response({"ok": True})
        except Exception as e:
            logger.error("TaskDetailView.delete error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def _update(self, request, pk):
        d = request.data
        if not isinstance(d, dict):
            return Response({"error": "Невалидный JSON"}, status=400)
        if not d:
            return Response({"error": "Пустое тело запроса"}, status=400)

        vis_q = get_visibility_filter(request.user)

        with transaction.atomic():
            work = (
                Work.objects.select_for_update(of=("self",))
                .filter(pk=pk, show_in_plan=True)
                .filter(vis_q)
                .first()
            )
            if not work:
                return Response({"error": "Задача не найдена"}, status=404)

            if d.get("_mcc_finish"):
                return self._mcc_finish(work)

            # Optimistic locking: нормализуем оба timestamp до YYYY-MM-DDTHH:MM:SS
            # (отбрасываем микросекунды и TZ-суффикс для надёжного сравнения)
            if "updated_at" in d and d["updated_at"] is not None:
                server_ts = (
                    work.updated_at.strftime("%Y-%m-%dT%H:%M:%S")
                    if work.updated_at
                    else ""
                )
                raw = str(d["updated_at"]).replace(" ", "T")
                # Обрезаем микросекунды (.123456) и TZ-суффикс (+00:00 / Z)
                client_ts = raw[:19] if len(raw) >= 19 else raw
                if server_ts != client_ts:
                    return Response(
                        {
                            "error": "conflict",
                            "message": "Запись была изменена другим пользователем. "
                            "Перезагрузите страницу.",
                        },
                        status=409,
                    )

            # from_pp: запись из ПП — ПП-поля заблокированы для редактирования в СП
            is_from_pp = work.show_in_pp
            _PP_LOCKED_FIELDS = frozenset(
                (
                    "work_name",
                    "work_number",
                    "description",
                    "task_type",
                    "dept",
                    "sector",
                    "project",
                    "stage",
                    "justification",
                )
            )
            if is_from_pp and not d.get("_mcc_finish"):
                # Определяем какие заблокированные поля клиент пытался изменить
                attempted_locked = [lf for lf in _PP_LOCKED_FIELDS if lf in d]
                if attempted_locked:
                    # Проверяем, остаются ли разрешённые поля
                    non_service = {
                        k for k in d if not k.startswith("_") and k != "updated_at"
                    }
                    remaining = non_service - _PP_LOCKED_FIELDS
                    if not remaining:
                        # Все переданные поля заблокированы — отклоняем
                        return Response(
                            {
                                "error": "Запись из ПП: редактирование заблокированных полей запрещено",
                                "locked_fields": attempted_locked,
                            },
                            status=403,
                        )
                    # Есть и разрешённые поля — тихо убираем заблокированные, добавим warning
                    for lf in attempted_locked:
                        d.pop(lf, None)
                    logger.info(
                        "PP lock: task %d — ignored locked fields %s",
                        pk,
                        attempted_locked,
                    )
            if "plan_hours_update" in d:
                ph_upd, ph_err = validate_plan_hours(d["plan_hours_update"])
                if ph_err:
                    return Response({"error": ph_err}, status=400)
                existing = parse_json_hours(work.plan_hours)
                existing.update(ph_upd)
                work.plan_hours = existing
                work.save(update_fields=["plan_hours", "updated_at"])
            else:
                if "plan_hours" in d:
                    ph, ph_err = validate_plan_hours(d.get("plan_hours"))
                    if ph_err:
                        return Response({"error": ph_err}, status=400)
                else:
                    ph = work.plan_hours
                if not is_from_pp:
                    work.work_name = d.get("work_name", work.work_name) or ""
                    # work_num — read-only, авто-генерация при создании
                    work.work_designation = (
                        d.get("description", work.work_designation) or ""
                    )
                work.plan_hours = ph

                if "task_type" in d:
                    tt_val, tt_err = validate_task_type(d["task_type"])
                    if tt_err:
                        return Response({"error": tt_err}, status=400)
                    d["task_type"] = tt_val

                _set_work_fk_fields(work, d, request)
                try:
                    _set_date_fields(work, d)
                except ValueError as exc:
                    return Response({"error": str(exc)}, status=400)

                if "stage" in d and not is_from_pp:
                    work.stage_num = d["stage"] or ""
                if "justification" in d and not is_from_pp:
                    work.justification = d["justification"] or ""
                if "actions" in d:
                    actions, act_err = validate_actions(d["actions"])
                    if act_err:
                        return Response({"error": act_err}, status=400)
                    work.actions = actions

                work.save()

                # Синхронизация ЖИ при смене task_type
                if "task_type" in d:
                    _sync_notices_for_work(work)

            # Обновление списка исполнителей
            if "executors_list" in d:
                executors_list, el_err = validate_executors_list(d["executors_list"])
                if el_err:
                    return Response({"error": el_err}, status=400)
                TaskExecutor.objects.filter(work=work).delete()
                if executors_list:
                    _save_executors(work, executors_list)

        log_action(
            request,
            AuditLog.ACTION_TASK_UPDATE,
            object_id=work.id,
            object_repr=work.work_name,
        )
        # Возвращаем свежий updated_at для оптимистичной блокировки
        work.refresh_from_db(fields=["updated_at"])
        return Response(
            {
                "ok": True,
                "updated_at": (work.updated_at.isoformat() if work.updated_at else ""),
            }
        )

    def _mcc_finish(self, work):
        """Закрытие задачи: date_end = последний день прошлого месяца."""
        last_day, cutoff = mcc_finish_data()
        ph = parse_json_hours(work.plan_hours)
        ph = {k: v for k, v in ph.items() if k < cutoff}
        work.date_end = last_day
        work.plan_hours = ph
        work.save(update_fields=["date_end", "plan_hours", "updated_at"])
        return Response(
            {
                "ok": True,
                "updated_at": (work.updated_at.isoformat() if work.updated_at else ""),
            }
        )


# ---------------------------------------------------------------------------
#  DELETE /api/tasks/all (admin)
# ---------------------------------------------------------------------------


class TaskDeleteAllView(APIView):
    permission_classes = [IsAdminPermission]

    """DELETE /api/tasks/all — удаление всех задач (только admin)."""

    def delete(self, request):
        try:
            with transaction.atomic():
                # Записи, видимые и в ПП — только снимаем флаг СП
                Work.objects.filter(
                    show_in_plan=True,
                    show_in_pp=True,
                ).update(show_in_plan=False, actions={})
                # Чистые СП-записи — удаляем
                Work.objects.filter(
                    show_in_plan=True,
                    show_in_pp=False,
                ).delete()
            logger.info("Администратор очистил все задачи: user=%s", request.user.pk)
            return Response({"ok": True})
        except Exception as e:
            logger.error("TaskDeleteAllView error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)


# ---------------------------------------------------------------------------
#  POST /api/tasks/bulk_delete (writer)
# ---------------------------------------------------------------------------


class TaskBulkDeleteView(APIView):
    permission_classes = [IsWriterPermission]

    """POST /api/tasks/bulk_delete — удаление нескольких задач по списку ID."""

    def post(self, request):
        data = request.data
        if not isinstance(data, dict):
            return Response({"error": "Невалидный JSON"}, status=400)

        ids = data.get("ids", [])
        if not ids or not isinstance(ids, list):
            return Response({"error": "Не указаны ID задач"}, status=400)

        # Ограничиваем до 100 за раз
        ids = [int(i) for i in ids[:100] if str(i).isdigit()]
        if not ids:
            return Response({"error": "Нет валидных ID"}, status=400)

        try:
            vis_q = get_visibility_filter(request.user)
            with transaction.atomic():
                works = list(
                    Work.objects.select_for_update()
                    .filter(pk__in=ids, show_in_plan=True)
                    .filter(vis_q)
                )
                deleted = 0
                for work in works:
                    log_action(
                        request,
                        AuditLog.ACTION_TASK_DELETE,
                        object_id=work.id,
                        object_repr=work.work_name,
                    )
                    if work.show_in_pp:
                        work.show_in_plan = False
                        work.actions = {}
                        work.save(update_fields=["show_in_plan", "actions"])
                    else:
                        work.delete()
                    deleted += 1

            return Response({"ok": True, "deleted": deleted})
        except Exception as e:
            logger.error("TaskBulkDeleteView error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)


# ---------------------------------------------------------------------------
#  GET /api/tasks/<id>/executors
# ---------------------------------------------------------------------------


class TaskExecutorsView(APIView):
    permission_classes = [IsAuthenticated]

    """GET /api/tasks/<id>/executors — список исполнителей задачи."""

    def get(self, request, pk):
        try:
            vis_q = get_visibility_filter(request.user)
            if not Work.objects.filter(pk=pk, show_in_plan=True).filter(vis_q).exists():
                return Response({"error": "Задача не найдена"}, status=403)
            executors = TaskExecutor.objects.filter(work_id=pk).select_related(
                "executor"
            )
            result = [
                {
                    "name": te.executor.full_name if te.executor else te.executor_name,
                    "hours": parse_json_hours(te.plan_hours),
                }
                for te in executors
            ]
            return Response(result)
        except Exception as e:
            logger.error("TaskExecutorsView error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)


# ---------------------------------------------------------------------------
#  Вспомогательные функции
# ---------------------------------------------------------------------------


def _set_work_fk_fields(work, d, request):
    """Устанавливает FK-поля Work по текстовым значениям из запроса."""
    # task_type — CharField (тип задачи хранится строкой: "Выпуск…"/"Корректировка…")
    task_type = d.get("task_type", "")
    if task_type:
        work.task_type = task_type

    # department / dept
    dept = d.get("dept", "")
    if dept:
        try:
            dep_obj = Department.objects.get(code=dept)
            work.department = dep_obj
        except Department.DoesNotExist:
            pass

    # sector
    sector = d.get("sector", "")
    if sector:
        if work.department:
            sec_obj = Sector.objects.filter(
                code=sector,
                department=work.department,
            ).first()
            if sec_obj:
                work.sector = sec_obj
            else:
                logger.warning(
                    "Сектор '%s' не найден для отдела '%s'",
                    sector,
                    work.department.code,
                )
        else:
            # Без отдела — ищем по коду, но только если результат однозначный
            candidates = Sector.objects.filter(code=sector)
            if candidates.count() == 1:
                work.sector = candidates.first()
            else:
                logger.warning(
                    "Сектор '%s' не привязан: отдел не задан, найдено %d совпадений",
                    sector,
                    candidates.count(),
                )

    # project — УП-проект по названию
    project = d.get("project", "")
    if project:
        proj_obj = Project.objects.filter(
            Q(name_short=project) | Q(name_full=project)
        ).first()
        if proj_obj:
            work.project = proj_obj

    # pp_stage — привязка этапа ПП (ЕТБД) по stage_number + project
    stage_val = d.get("stage", "")
    if stage_val and work.project:
        from apps.works.models import PPStage

        pp_stg = PPStage.objects.filter(
            project=work.project,
            stage_number=stage_val,
        ).first()
        if pp_stg:
            work.pp_stage = pp_stg
    elif not stage_val:
        work.pp_stage = None

    # executor — строгий поиск по ФИО (только при точном совпадении)
    executor_name = d.get("executor", "")
    if executor_name:
        emp, _ = resolve_employee(executor_name)
        work.executor = emp

    # center — из профиля пользователя (только при создании, чтобы не
    # перезаписывать НТЦ при обновлении чужим пользователем)
    if not work.pk:
        employee = getattr(request.user, "employee", None)
        effective_ntc = employee.effective_ntc_center if employee else None
        if effective_ntc:
            work.ntc_center = effective_ntc


def _set_date_fields(work, d):
    """Устанавливает поля дат из строковых значений."""
    for field_name, attr in [
        ("date_start", "date_start"),
        ("date_end", "date_end"),
        ("deadline", "deadline"),
    ]:
        val = d.get(field_name)
        if val is not None:
            if val == "":
                setattr(work, attr, None)
            else:
                try:
                    setattr(work, attr, dt_date.fromisoformat(str(val)))
                except (ValueError, TypeError):
                    setattr(work, attr, None)
    # Валидация: date_start не может быть позже date_end
    if work.date_start and work.date_end and work.date_start > work.date_end:
        raise ValueError("Дата начала не может быть позже даты окончания")
    # Валидация: максимальная длительность работы — 5 лет
    # (страховка от опечаток в году, напр. 2099 вместо 2029)
    if work.date_start and work.date_end:
        delta = (work.date_end - work.date_start).days
        if delta > 5 * 366:  # с запасом на високосные годы
            raise ValueError("Длительность работы не может превышать 5 лет")


# Локальный алиас для обратной совместимости (реализация в utils.py)
_resolve_employee = resolve_employee


def _save_executors(work, executors):
    """Сохраняет список исполнителей задачи."""
    objs = []
    for ex in executors:
        hours = ex.get("hours", {})
        if isinstance(hours, str):
            hours = parse_json_hours(hours)
        emp, name = _resolve_employee(ex.get("name", ""))
        objs.append(
            TaskExecutor(
                work=work,
                executor=emp,
                executor_name=name,
                plan_hours=hours if isinstance(hours, dict) else {},
            )
        )
    if objs:
        TaskExecutor.objects.bulk_create(objs)
