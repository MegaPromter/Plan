"""
API производственного плана (Work show_in_pp=True).

Аналог Flask-эндпоинтов:
  GET    /api/production_plan        — список записей ПП
  POST   /api/production_plan        — создание записи ПП
  PUT    /api/production_plan/<id>   — обновление записи ПП (inline single-field)
  DELETE /api/production_plan/<id>   — удаление записи ПП
  POST   /api/production_plan/sync   — синхронизация ПП → задачи
"""

import logging

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.audit import log_action
from apps.api.drf_utils import IsWriterPermission
from apps.api.utils import (
    PRODUCTION_ALLOWED_FIELDS,
    generate_work_num,
    resolve_employee,
    safe_date,
    safe_decimal,
    validate_task_type,
)
from apps.api.views.reports import _sync_notices_for_work
from apps.employees.models import Department, NTCCenter, Sector
from apps.works.models import AuditLog, Work, WorkReport

logger = logging.getLogger(__name__)

TASKS_MAX = 5000


def _get_pp_scope_filter(user):
    """
    Q-фильтр видимости ПП по роли пользователя.

    - admin              → все строки
    - ntc_head/deputy    → строки своего НТЦ
    - dept_head/deputy   → строки своего отдела
    - sector_head        → строки своего отдела
    - user               → строки своего сектора
    """
    employee = getattr(user, "employee", None)
    if not employee:
        return Q(pk__isnull=True)

    role = employee.role
    if role == "admin":
        return Q()

    if role in ("ntc_head", "ntc_deputy"):
        if employee.ntc_center:
            return Q(ntc_center=employee.ntc_center)
        return Q(pk__isnull=True)

    if role in ("dept_head", "dept_deputy", "sector_head"):
        if employee.department:
            return Q(department=employee.department)
        return Q(pk__isnull=True)

    # user — только свой сектор
    if employee.sector:
        return Q(sector=employee.sector)
    if employee.department:
        return Q(department=employee.department)
    return Q(executor=employee) | Q(created_by=employee)


# ---------------------------------------------------------------------------
#  Вспомогательные функции
# ---------------------------------------------------------------------------


def _round_labor(val):
    """Возвращает целое если значение целое, иначе округляет до 2 знаков."""
    f = float(val)
    i = int(f)
    return i if f == i else round(f, 2)


# _safe_decimal / _safe_date → вынесены в apps.api.utils (safe_decimal / safe_date)
_safe_decimal = safe_decimal
_safe_date = safe_date


# ---------------------------------------------------------------------------
#  Сериализация
# ---------------------------------------------------------------------------


def _serialize_pp(work, today=None):
    """Сериализует Work (show_in_pp=True) в плоский dict для JSON-ответа."""
    if today is None:
        today = timezone.now().date()
    has_reports = getattr(work, "_has_reports", False)
    is_overdue = bool(work.date_end and work.date_end < today and not has_reports)
    return {
        "id": work.id,
        "work_name": work.work_name or "",
        "date_start": work.date_start.isoformat() if work.date_start else "",
        "date_end": work.date_end.isoformat() if work.date_end else "",
        "dept": (work.department.code if work.department else "") or "",
        "center": (
            work.ntc_center.code
            if work.ntc_center
            else (
                work.department.ntc_center.code
                if work.department and work.department.ntc_center
                else ""
            )
        )
        or "",
        "executor": (work.executor.full_name if work.executor else "") or "",
        "created_by": work.created_by_id,
        "created_at": work.created_at.isoformat() if work.created_at else "",
        "updated_at": work.updated_at.isoformat() if work.updated_at else "",
        # PP-поля: row_code и work_order читаются из PPStage (ЕТБД)
        "row_code": (work.pp_stage.row_code if work.pp_stage else work.row_code) or "",
        "work_order": (work.pp_stage.work_order if work.pp_stage else work.work_order)
        or "",
        "stage_num": work.stage_num or "",
        "work_num": work.work_num or "",
        "work_designation": work.work_designation or "",
        "sheets_a4": float(work.sheets_a4) if work.sheets_a4 is not None else "",
        "norm": float(work.norm) if work.norm is not None else "",
        "coeff": float(work.coeff) if work.coeff is not None else "",
        "total_2d": _round_labor(work.total_2d) if work.total_2d is not None else "",
        "total_3d": _round_labor(work.total_3d) if work.total_3d is not None else "",
        "labor": _round_labor(work.labor) if work.labor is not None else "",
        "sector_head": (work.sector.name or work.sector.code if work.sector else "")
        or "",
        "task_type": work.task_type or "",
        "cross_stage_id": work.cross_stage_id,
        "cross_stage_name": (work.cross_stage.name if work.cross_stage else "") or "",
        "pp_stage_id": work.pp_stage_id,
        "pp_stage_name": (work.pp_stage.name if work.pp_stage else "") or "",
        "project_id": work.pp_project_id,
        "predecessors_count": getattr(work, "_pred_count", 0) or 0,
        "has_reports": has_reports,
        "is_overdue": is_overdue,
    }


# ---------------------------------------------------------------------------
#  Числовые поля (decimal) в Work для ПП
# ---------------------------------------------------------------------------

_PP_DECIMAL_FIELDS = {"sheets_a4", "norm", "coeff", "total_2d", "total_3d", "labor"}

# Поля трудоёмкости, которые должны быть СТРОГО больше нуля
# (если клиент прислал их и значение распарсилось — запрещаем <= 0).
# Пустое значение допустимо — означает «не задано».
_PP_STRICT_POSITIVE_FIELDS = {"labor"}


# ---------------------------------------------------------------------------
#  GET / POST  /api/production_plan
# ---------------------------------------------------------------------------


class ProductionPlanListView(APIView):
    permission_classes = [IsAuthenticated]

    """GET — список записей ПП."""

    def get(self, request):
        try:
            return self._get_list(request)
        except Exception as e:
            logger.error("ProductionPlanListView.get error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def _get_list(self, request):
        try:
            limit = int(request.GET.get("limit", 0)) or TASKS_MAX
        except (ValueError, TypeError):
            limit = TASKS_MAX
        limit = min(limit, TASKS_MAX)

        try:
            offset = max(int(request.GET.get("offset", 0)), 0)
        except (ValueError, TypeError):
            offset = 0

        try:
            project_id = int(request.GET.get("project_id", 0)) or None
        except (ValueError, TypeError):
            project_id = None

        qs = Work.objects.filter(show_in_pp=True)

        if project_id:
            qs = qs.filter(pp_project_id=project_id)

        # Фильтрация по роли: каждый видит свой уровень,
        # scope=all снимает фильтр (дозагрузка при нажатии «Все»)
        scope = request.GET.get("scope", "")
        if scope != "all":
            qs = qs.filter(_get_pp_scope_filter(request.user))

        qs = (
            qs.defer(
                "plan_hours",
                "executors_list",
                "actions",
                "justification",
            )
            .annotate(
                _pred_count=Count("predecessor_links"),
                _has_reports=Exists(WorkReport.objects.filter(work_id=OuterRef("pk"))),
            )
            .select_related(
                "department",
                "department__ntc_center",
                "ntc_center",
                "executor",
                "sector",
                "pp_project",
                "cross_stage",
                "pp_stage",
            )
            .order_by("id")
        )

        # Общее количество (до пагинации) — для клиента
        total_count = qs.count()

        qs = qs[offset : offset + limit]
        works = list(qs)
        today = timezone.now().date()

        resp = Response([_serialize_pp(w, today) for w in works])
        resp["X-Total-Count"] = total_count
        resp["X-Has-More"] = "true" if (offset + limit) < total_count else "false"
        resp["X-Scope"] = scope if scope == "all" else "role"
        resp["Cache-Control"] = "private, max-age=5"
        return resp


class ProductionPlanCreateView(APIView):
    permission_classes = [IsWriterPermission]

    """POST /api/production_plan — создание записи ПП."""

    def post(self, request):
        try:
            return self._create(request)
        except Exception as e:
            logger.error("ProductionPlanCreateView error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def _create(self, request):
        d = request.data
        if not isinstance(d, dict):
            return Response({"error": "Невалидный JSON"}, status=400)
        project_id = d.get("project_id") or None
        if not project_id:
            return Response(
                {"error": "Необходимо выбрать проект ПП перед добавлением строки"},
                status=400,
            )
        employee = getattr(request.user, "employee", None)

        # Проверка прав на отдел/сектор
        if employee and employee.role in ("dept_head", "dept_deputy"):
            if not employee.department:
                return Response(
                    {"error": "Вашему профилю не назначен отдел"}, status=403
                )
            dept_code = d.get("dept", "") or ""
            if dept_code and dept_code != employee.department.code:
                return Response(
                    {"error": "Вы можете создавать задачи только для своего отдела"},
                    status=403,
                )
        elif employee and employee.role == "sector_head":
            if not employee.department:
                return Response(
                    {"error": "Вашему профилю не назначен отдел"}, status=403
                )
            dept_code = d.get("dept", "") or ""
            if dept_code and dept_code != employee.department.code:
                return Response(
                    {"error": "Вы можете создавать задачи только для своего отдела"},
                    status=403,
                )
            sector_head_val = (d.get("sector_head") or "").strip()
            if sector_head_val and employee.sector:
                own_sector_values = {employee.sector.code, employee.sector.name}
                if sector_head_val not in own_sector_values:
                    return Response(
                        {
                            "error": "Вы можете создавать задачи только для своего сектора"
                        },
                        status=403,
                    )

        ntc_center = employee.effective_ntc_center if employee else None

        dept_obj = None
        if employee and employee.role in ("dept_head", "dept_deputy", "sector_head"):
            dept_obj = employee.department
        elif d.get("dept"):
            try:
                dept_obj = Department.objects.get(code=d["dept"])
            except Department.DoesNotExist:
                dept_obj = None

        _validated_tt, tt_err = validate_task_type(d.get("task_type", ""))
        if tt_err:
            return Response({"error": tt_err}, status=400)
        if not _validated_tt:
            _validated_tt = "Выпуск нового документа"

        with transaction.atomic():
            work = Work.objects.create(
                show_in_pp=True,
                work_name=d.get("work_name", "") or "",
                task_type=_validated_tt,
                pp_project_id=project_id,
                ntc_center=ntc_center,
                department=dept_obj,
                created_by=employee,
            )

            # Применяем остальные поля без промежуточных save()
            detail_view = ProductionPlanDetailView()
            changed = False
            validation_error = None
            for field in PRODUCTION_ALLOWED_FIELDS:
                if field in ("work_name", "task_type"):
                    continue
                value = d.get(field)
                if value is None or value == "":
                    continue
                try:
                    detail_view._update_field(
                        work, field, value, save=False, skip_date_check=True
                    )
                except ValueError as exc:
                    validation_error = str(exc)
                    break
                changed = True
            if validation_error:
                # Внутри transaction.atomic() — вызываем set_rollback
                transaction.set_rollback(True)
                return Response({"error": validation_error}, status=400)
            # Проверка дат после установки всех полей
            if work.date_start and work.date_end and work.date_start > work.date_end:
                work.delete()
                return Response(
                    {"error": "Дата начала не может быть позже даты окончания"},
                    status=400,
                )
            # Максимальная длительность работы — 5 лет
            if work.date_start and work.date_end:
                if (work.date_end - work.date_start).days > 5 * 366:
                    work.delete()
                    return Response(
                        {"error": "Длительность работы не может превышать 5 лет"},
                        status=400,
                    )

            # Автогенерация номера работы (если проект УП привязан)
            if not work.work_num:
                up_project = work.pp_project.up_project if work.pp_project else None
                if up_project:
                    work.work_num = generate_work_num(up_project)
                    changed = True

            if changed:
                work.save()

            # Синхронизация ЖИ при создании с task_type «Корректировка документа»
            _sync_notices_for_work(work)

        log_action(
            request,
            AuditLog.ACTION_PP_CREATE,
            object_id=work.pk,
            object_repr=work.work_name or str(work.pk),
            details={"task_type": work.task_type},
        )

        work_data = _serialize_pp(
            Work.objects.annotate(
                _pred_count=Count("predecessor_links"),
                _has_reports=Exists(WorkReport.objects.filter(work_id=OuterRef("pk"))),
            )
            .select_related(
                "department",
                "ntc_center",
                "executor",
                "sector",
                "pp_project",
                "cross_stage",
                "pp_stage",
            )
            .get(pk=work.pk)
        )
        return Response({"id": work.id, "work": work_data})


# ---------------------------------------------------------------------------
#  Вспомогательная проверка прав на редактирование записи ПП
# ---------------------------------------------------------------------------


def _check_dept_access(user, work):
    """
    Проверяет, может ли пользователь редактировать/удалять запись ПП.
    Admin — может всё. Остальные — только записи своего отдела.
    Возвращает строку с ошибкой или None если доступ разрешён.
    """
    employee = getattr(user, "employee", None)
    if not employee:
        return "Нет профиля сотрудника"
    # Администратор и руководство НТЦ редактируют любые записи
    if employee.role in ("admin", "ntc_head", "ntc_deputy"):
        return None
    # Начальники отделов/секторов — только свой отдел
    if not employee.department:
        return "Вашему профилю не назначен отдел"
    if work.department and employee.department_id != work.department_id:
        return "Вы можете редактировать только записи своего отдела"
    return None


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/production_plan/<id>
# ---------------------------------------------------------------------------


class ProductionPlanDetailView(APIView):
    permission_classes = [IsWriterPermission]

    """PUT /api/production_plan/<id>; DELETE /api/production_plan/<id>."""

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except Exception as e:
            logger.error("ProductionPlanDetailView.put error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def delete(self, request, pk):
        try:
            with transaction.atomic():
                work = (
                    Work.objects.select_for_update(of=("self",))
                    .filter(pk=pk, show_in_pp=True)
                    .select_related("department")
                    .first()
                )
                if not work:
                    return Response({"error": "Запись ПП не найдена"}, status=404)
                # Проверка: не-admin может удалять только записи своего отдела
                err = _check_dept_access(request.user, work)
                if err:
                    return Response({"error": err}, status=403)
                work_repr = f"{work.work_name} (id={work.pk})"
                if work.show_in_plan:
                    # Запись также видна в СП — не удаляем, а убираем из ПП
                    work.show_in_pp = False
                    work.pp_project = None
                    work.save(update_fields=["show_in_pp", "pp_project"])
                else:
                    work.delete()
                log_action(
                    request,
                    AuditLog.ACTION_PP_DELETE,
                    object_id=pk,
                    object_repr=work_repr,
                )
            return Response({"ok": True})
        except Exception as e:
            logger.error("ProductionPlanDetailView.delete error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def _update(self, request, pk):
        """Inline single-field update."""
        field = request.GET.get("field")
        d = request.data
        if not isinstance(d, dict):
            return Response({"error": "Невалидный JSON"}, status=400)
        value = d.get("value", "")

        if not field:
            return Response({"error": "field parameter required"}, status=400)
        if field not in PRODUCTION_ALLOWED_FIELDS:
            return Response({"error": f"Недопустимое поле: {field}"}, status=400)

        if field == "task_type":
            value, tt_err = validate_task_type(value)
            if tt_err:
                return Response({"error": tt_err}, status=400)
            if not value:
                value = "Выпуск нового документа"

        with transaction.atomic():
            work = (
                Work.objects.select_for_update(of=("self",))
                .filter(pk=pk, show_in_pp=True)
                .select_related(
                    "department", "ntc_center", "executor", "sector", "cross_stage"
                )
                .first()
            )
            if not work:
                return Response({"error": "Запись ПП не найдена"}, status=404)

            # Проверка: не-admin может редактировать только записи своего отдела
            err = _check_dept_access(request.user, work)
            if err:
                return Response({"error": err}, status=403)

            # Optimistic locking — нормализуем оба timestamp до YYYY-MM-DDTHH:MM:SS
            client_updated_at = d.get("updated_at")
            if client_updated_at is not None:
                server_ts = (
                    work.updated_at.strftime("%Y-%m-%dT%H:%M:%S")
                    if work.updated_at
                    else ""
                )
                raw = str(client_updated_at).replace(" ", "T")
                client_ts = raw[:19] if len(raw) >= 19 else raw
                if server_ts != client_ts:
                    return Response(
                        {
                            "error": "conflict",
                            "message": "Запись была изменена другим пользователем. "
                            "Перезагрузите данные.",
                        },
                        status=409,
                    )

            try:
                self._update_field(work, field, value)
            except ValueError as exc:
                return Response({"error": str(exc)}, status=400)
            log_action(
                request,
                AuditLog.ACTION_PP_UPDATE,
                object_id=work.pk,
                object_repr=work.work_name or str(work.pk),
                details={"field": field, "value": str(value)[:200]},
            )

        return Response({"ok": True})

    def _update_field(self, work, field, value, save=True, skip_date_check=False):
        """Обновляет одно поле в Work."""
        if field == "work_name":
            work.work_name = value or ""
        elif field == "date_start":
            parsed = _safe_date(value)
            if (
                not skip_date_check
                and parsed
                and work.date_end
                and parsed > work.date_end
            ):
                raise ValueError("Дата начала не может быть позже даты окончания")
            if (
                not skip_date_check
                and parsed
                and work.date_end
                and (work.date_end - parsed).days > 5 * 366
            ):
                raise ValueError("Длительность работы не может превышать 5 лет")
            work.date_start = parsed
            work.pp_date_start = parsed
        elif field == "date_end":
            parsed = _safe_date(value)
            if (
                not skip_date_check
                and parsed
                and work.date_start
                and parsed < work.date_start
            ):
                raise ValueError("Дата окончания не может быть раньше даты начала")
            if (
                not skip_date_check
                and parsed
                and work.date_start
                and (parsed - work.date_start).days > 5 * 366
            ):
                raise ValueError("Длительность работы не может превышать 5 лет")
            work.date_end = parsed
            work.pp_date_end = parsed
        elif field == "executor":
            # Строгий поиск по ФИО — назначаем только при точном совпадении
            if value:
                emp, _ = resolve_employee(value)
                work.executor = emp
            else:
                work.executor = None
        elif field == "dept":
            if value:
                try:
                    dep = Department.objects.get(code=value)
                except Department.DoesNotExist:
                    dep = None
                work.department = dep
            else:
                work.department = None
        elif field == "center":
            if value:
                try:
                    center = NTCCenter.objects.get(code=value)
                except NTCCenter.DoesNotExist:
                    center = None
                work.ntc_center = center
            else:
                work.ntc_center = None
        elif field in _PP_DECIMAL_FIELDS:
            parsed = _safe_decimal(value)
            # Строгая проверка «> 0» для трудоёмкости (labor и т.п.)
            if (
                field in _PP_STRICT_POSITIVE_FIELDS
                and parsed is not None
                and parsed <= 0
            ):
                raise ValueError(f"Поле «{field}» должно быть больше нуля")
            setattr(work, field, parsed)
        elif field == "sector_head":
            # sector_head устанавливается через FK sector (только в рамках отдела)
            if value:
                if not work.department:
                    raise ValueError("Нельзя назначить сектор без указанного отдела")
                sec = Sector.objects.filter(
                    Q(code=value) | Q(name=value),
                    department=work.department,
                ).first()
                work.sector = sec
            else:
                work.sector = None
        elif field == "task_type":
            work.task_type = value or ""
        elif field == "cross_stage":
            if value:
                from apps.enterprise.models import CrossStage

                try:
                    cs = CrossStage.objects.get(pk=int(value))
                    work.cross_stage = cs
                except (CrossStage.DoesNotExist, ValueError, TypeError):
                    work.cross_stage = None
            else:
                work.cross_stage = None
        elif field == "pp_stage":
            if value:
                from apps.works.models import PPStage

                try:
                    ps = PPStage.objects.get(pk=int(value))
                    work.pp_stage = ps
                    work.stage_num = ps.stage_number or ""
                except (PPStage.DoesNotExist, ValueError, TypeError):
                    work.pp_stage = None
            else:
                work.pp_stage = None
                work.stage_num = ""
        else:
            # row_code, work_order, stage_num, work_num, work_designation
            setattr(work, field, value or "")
        if save:
            work.save()
            # Синхронизация ЖИ при смене task_type
            if field == "task_type":
                _sync_notices_for_work(work)


# ---------------------------------------------------------------------------
#  POST /api/production_plan/sync
# ---------------------------------------------------------------------------


class ProductionPlanSyncView(APIView):
    permission_classes = [IsWriterPermission]

    """POST /api/production_plan/sync — синхронизация ПП → СП.

    Никаких копий/дублей: просто включает show_in_plan=True на записях ПП,
    чтобы они стали видны в модуле «План/отчёт».
    Сериализатор _serialize_task сам маппит ПП-поля в СП-колонки.
    """

    def post(self, request):
        try:
            return self._sync(request)
        except Exception as e:
            logger.error("ProductionPlanSyncView error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def _sync(self, request):
        d = request.data
        if not isinstance(d, dict):
            return Response({"error": "Невалидный JSON"}, status=400)
        filter_project_id = d.get("project_id") or None
        if not filter_project_id:
            return Response(
                {"error": "Необходимо указать project_id для синхронизации"},
                status=400,
            )

        # Проверка прав: только admin/ntc_head/ntc_deputy или writer своего отдела
        employee = getattr(request.user, "employee", None)
        if not employee:
            return Response({"error": "Нет профиля сотрудника"}, status=403)

        # Непустые ПП-записи проекта, ещё не показанные в СП
        qs = Work.objects.filter(
            show_in_pp=True,
            show_in_plan=False,
            pp_project_id=filter_project_id,
        )

        # Ограничение по отделу: не-admin/ntc видят только свой отдел
        if employee.role not in ("admin", "ntc_head", "ntc_deputy"):
            if not employee.department:
                return Response(
                    {"error": "Вашему профилю не назначен отдел"}, status=403
                )
            qs = qs.filter(department=employee.department)

        # Если переданы конкретные ids (отфильтрованные на клиенте) — синхронизируем только их
        ids = d.get("ids")
        if ids and isinstance(ids, list):
            qs = qs.filter(pk__in=ids)

        # Включаем show_in_plan + копируем даты ПП
        from django.db.models import F

        synced = qs.update(
            show_in_plan=True,
            pp_date_start=F("date_start"),
            pp_date_end=F("date_end"),
        )

        log_action(request, AuditLog.ACTION_PP_SYNC, details={"synced": synced})
        return Response({"synced": synced})


# ---------------------------------------------------------------------------
#  GET /api/pp_projects/<pk>/cross_stages — этапы сквозного графика
# ---------------------------------------------------------------------------


class PPCrossStagesView(APIView):
    permission_classes = [IsAuthenticated]

    """GET /api/pp_projects/<pk>/cross_stages/ — этапы сквозного графика для ПП-проекта."""

    def get(self, request, pk):
        from apps.works.models import PPProject

        pp = PPProject.objects.select_related("up_project").filter(pk=pk).first()
        if not pp or not pp.up_project_id:
            return Response([])
        from apps.enterprise.models import CrossSchedule

        cross = CrossSchedule.objects.filter(project=pp.up_project).first()
        if not cross:
            return Response([])
        stages_qs = (
            cross.stages.select_related("parent_item")
            .filter(
                parent_item__isnull=False,
            )
            .order_by("parent_item__order", "order", "id")
        )
        result = []
        for s in stages_qs:
            if s.parent_item:
                num = "%s.%s" % (s.parent_item.order, s.order)
            else:
                num = str(s.order) if s.order else ""
            result.append(
                {
                    "id": s.id,
                    "num": num,
                    "name": s.name or "",
                    "date_start": s.date_start.isoformat() if s.date_start else "",
                    "date_end": s.date_end.isoformat() if s.date_end else "",
                }
            )
        return Response(result)
