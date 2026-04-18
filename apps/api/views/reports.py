"""
API отчётных документов (WorkReport).

Аналог Flask-эндпоинтов:
  GET    /api/reports/<task_id>  — список отчётов по задаче
  POST   /api/reports           — создание отчёта
  PUT    /api/reports/<id>      — обновление отчёта
  DELETE /api/reports/<id>      — удаление отчёта
"""

import logging
import re

from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.utils import get_visibility_filter, safe_date, safe_decimal, safe_int
from apps.works.models import Notice, Work, WorkReport

logger = logging.getLogger(__name__)

NOTICE_TASK_TYPE = "Корректировка документа"

_URL_RE = re.compile(
    r"^https?://" r"[A-Za-z0-9]" r"[A-Za-z0-9._-]*" r"\." r"[A-Za-z]{2,}" r"[^\s]*$",
    re.IGNORECASE,
)


def _zero_future_plan_hours(work, report_created_at):
    """Обнулить plan_hours во всех месяцах после месяца заполнения отчёта.

    Вызывается при создании WorkReport.
    report_created_at — datetime заполнения отчёта (created_at).
    Обнуляет часы у Work и у всех TaskExecutor.
    """
    from apps.works.models import TaskExecutor

    report_month = f"{report_created_at.year}-{report_created_at.month:02d}"

    # Обнулить в Work.plan_hours
    ph = work.plan_hours or {}
    changed = False
    for key in list(ph.keys()):
        if key > report_month:
            ph[key] = 0
            changed = True
    if changed:
        work.plan_hours = ph
        work.save(update_fields=["plan_hours", "updated_at"])

    # Обнулить в TaskExecutor.plan_hours
    for te in TaskExecutor.objects.filter(work=work):
        te_ph = te.plan_hours or {}
        te_changed = False
        for key in list(te_ph.keys()):
            if key > report_month:
                te_ph[key] = 0
                te_changed = True
        if te_changed:
            te.plan_hours = te_ph
            te.save(update_fields=["plan_hours"])


def _validate_url(value):
    """Вернуть строку ошибки если value не пустой и не похож на URL, иначе None."""
    if not value:
        return None
    if not _URL_RE.match(value.strip()):
        return "Поле «Ссылка» должно содержать корректный URL (начинающийся с http:// или https://)"
    return None


def _sync_notice_for_report(report):
    """Создать/удалить Notice при сохранении отчёта.
    Notice создаётся если task_type работы = 'Корректировка документа'.
    """
    work = report.work
    if not work:
        return
    if work.task_type == NOTICE_TASK_TYPE:
        Notice.objects.get_or_create(
            work_report=report,
            defaults={"status": Notice.STATUS_ACTIVE},
        )
    else:
        Notice.objects.filter(work_report=report).delete()


def _sync_notices_for_work(work):
    """Пересинхронизировать Notice для всех отчётов работы.
    Вызывать при смене task_type.
    """
    for report in work.reports.all():
        _sync_notice_for_report(report)


def _check_report_access(user, report):
    """Проверка: writer может менять отчёт только для задачи своего отдела.
    admin / ntc_head / ntc_deputy — без ограничений.
    Рядовой исполнитель (user) — только по своим задачам (где он назначен).
    Возвращает строку ошибки или None (доступ разрешён)."""
    employee = getattr(user, "employee", None)
    if not employee:
        return "Нет профиля сотрудника"
    if employee.role in ("admin", "ntc_head", "ntc_deputy"):
        return None
    work = report.work
    # Рядовой исполнитель: только если он сам назначен на задачу
    if not employee.is_writer:
        if _is_task_executor(work, employee):
            return None
        return "Вы можете менять отчёты только по задачам, где назначены исполнителем"
    # Writer: в рамках своего отдела
    if not employee.department:
        return "Вашему профилю не назначен отдел"
    if work and work.department_id and employee.department_id != work.department_id:
        return "Вы можете редактировать только отчёты своего отдела"
    return None


def _is_task_executor(work, employee):
    """True, если сотрудник назначен исполнителем этой работы
    (как основной executor либо в TaskExecutor)."""
    if not work or not employee:
        return False
    if work.executor_id == employee.pk:
        return True
    from apps.works.models import TaskExecutor

    return TaskExecutor.objects.filter(work=work, executor=employee).exists()


def _future_plan_months(work, report_created_at):
    """Список месяцев (в формате 'YYYY-MM') с ненулевыми plan_hours,
    которые БУДУТ обнулены при создании отчёта (строго после месяца отчёта).

    Нужно, чтобы фронт мог показать подтверждение досрочного выполнения.
    """
    report_month = f"{report_created_at.year}-{report_created_at.month:02d}"
    ph = work.plan_hours or {}
    result = []
    for key, hours in ph.items():
        if key > report_month:
            try:
                if float(hours or 0) > 0:
                    result.append(key)
            except (TypeError, ValueError):
                continue
    result.sort()
    return result


def _serialize_report(r):
    """Сериализует WorkReport в dict для JSON-ответа."""
    return {
        "id": r.id,
        "task_id": r.work_id,
        "doc_name": r.doc_name or "",
        "doc_designation": r.doc_designation or "",
        "ii_pi": r.ii_pi or "",
        "doc_number": r.doc_number or "",
        "inventory_num": r.inventory_num or "",
        "date_accepted": (r.date_accepted.isoformat() if r.date_accepted else ""),
        "date_expires": (r.date_expires.isoformat() if r.date_expires else ""),
        "doc_type": r.doc_type or "",
        "doc_class": r.doc_class or "",
        "sheets_a4": r.sheets_a4,
        "norm": float(r.norm) if r.norm is not None else None,
        "coeff": float(r.coeff) if r.coeff is not None else None,
        "bvd_hours": float(r.bvd_hours) if r.bvd_hours is not None else None,
        "norm_control": r.norm_control or "",
        "doc_link": r.doc_link or "",
        # Дата заполнения отчёта (created_at) — только для отображения,
        # на бэкенде auto_now_add, не редактируется.
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


_safe_decimal = safe_decimal
_safe_int = safe_int
_safe_date = safe_date


# ---------------------------------------------------------------------------
#  GET /api/reports/<task_id>
# ---------------------------------------------------------------------------


class ReportListView(APIView):
    """GET /api/reports/<task_id> — список отчётов по задаче."""

    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        try:
            vis_q = get_visibility_filter(request.user)
            if not Work.objects.filter(vis_q, pk=task_id).exists():
                return Response(
                    {"error": "Задача не найдена"},
                    status=404,
                )
            reports = (
                WorkReport.objects.filter(
                    work_id=task_id,
                )
                .select_related("work")
                .order_by("id")
            )
            result = [_serialize_report(r) for r in reports]
            return Response(result)
        except (ValueError, TypeError) as e:
            logger.warning("ReportListView.get bad request: %s", e)
            return Response({"error": f"Некорректные параметры: {e}"}, status=400)
        except Exception as e:
            logger.error("ReportListView.get error: %s", e, exc_info=True)
            return Response(
                {"error": f"Внутренняя ошибка сервера: {e}"},
                status=500,
            )


# ---------------------------------------------------------------------------
#  POST /api/reports
# ---------------------------------------------------------------------------


class ReportCreateView(APIView):
    """POST /api/reports — создание отчёта.

    Доступ:
      - admin / ntc_head / ntc_deputy — любую задачу;
      - writer (dept_head / dept_deputy / sector_head / ...) — задачи своего отдела;
      - рядовой user — только задачи, где он назначен исполнителем
        (work.executor или запись в TaskExecutor).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            return self._create(request)
        except Exception as e:
            logger.error("ReportCreateView error: %s", e, exc_info=True)
            return Response(
                {"error": f"Внутренняя ошибка сервера: {e}"},
                status=500,
            )

    def _create(self, request):
        d = request.data
        if not isinstance(d, dict):
            return Response({"error": "Невалидный JSON"}, status=400)
        if not d:
            return Response({"error": "Пустое тело запроса"}, status=400)

        task_id = d.get("task_id")
        if not task_id:
            return Response(
                {"error": "task_id обязателен"},
                status=400,
            )

        try:
            work = Work.objects.select_related("department").get(pk=task_id)
        except Work.DoesNotExist:
            return Response({"error": "Задача не найдена"}, status=404)

        employee = getattr(request.user, "employee", None)
        if not employee:
            return Response({"error": "Нет профиля сотрудника"}, status=403)

        # Доступ: админы/руководители НТЦ — без ограничений;
        # writers — свой отдел; рядовой user — только свои задачи.
        if employee.role not in ("admin", "ntc_head", "ntc_deputy"):
            if employee.is_writer:
                if not employee.department_id:
                    return Response(
                        {"error": "Вашему профилю не назначен отдел"}, status=403
                    )
                if work.department_id and employee.department_id != work.department_id:
                    return Response(
                        {
                            "error": "Вы можете создавать отчёты только для задач своего отдела"
                        },
                        status=403,
                    )
            else:
                # Рядовой исполнитель: разрешаем только по своим задачам
                if not _is_task_executor(work, employee):
                    return Response(
                        {
                            "error": "Вы можете заполнять отчёты только по задачам, где назначены исполнителем"
                        },
                        status=403,
                    )

        url_err = _validate_url(d.get("doc_link"))
        if url_err:
            return Response({"error": url_err}, status=400)

        da = _safe_date(d.get("date_accepted"))
        if da and da > timezone.now().date():
            return Response(
                {"error": "Дата выпуска не может быть позже текущей даты"}, status=400
            )

        # Досрочное выполнение: если есть план-часы в будущих месяцах, требуем
        # явное подтверждение пользователя (флаг confirm_zero_future=true).
        # Иначе возвращаем 409 + список месяцев, чтобы фронт мог спросить.
        future_months = _future_plan_months(work, timezone.now())
        if future_months and not d.get("confirm_zero_future"):
            return Response(
                {
                    "error": "confirm_zero_future_required",
                    "future_months": future_months,
                    "message": (
                        "У задачи запланированы часы в будущих месяцах. "
                        "Они будут обнулены. Подтвердите действие."
                    ),
                },
                status=409,
            )

        with transaction.atomic():
            report = WorkReport.objects.create(
                work_id=task_id,
                doc_name=d.get("doc_name") or "",
                doc_designation=d.get("doc_designation") or "",
                ii_pi=d.get("ii_pi") or "",
                doc_number=d.get("doc_number") or "",
                inventory_num=d.get("inventory_num") or "",
                date_accepted=da,
                date_expires=_safe_date(d.get("date_expires")),
                doc_type=d.get("doc_type") or "",
                doc_class=d.get("doc_class") or "",
                sheets_a4=_safe_int(d.get("sheets_a4")),
                norm=_safe_decimal(d.get("norm")),
                coeff=_safe_decimal(d.get("coeff")),
                bvd_hours=_safe_decimal(d.get("bvd_hours")),
                norm_control=d.get("norm_control") or "",
                doc_link=d.get("doc_link") or "",
            )
            report.work = work
            _sync_notice_for_report(report)
            # Обнулить часы в будущих месяцах (после месяца заполнения)
            _zero_future_plan_hours(work, report.created_at)
        return Response({"id": report.id})


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/reports/<id>
# ---------------------------------------------------------------------------


class ReportDetailView(APIView):
    """PUT /api/reports/<id>; DELETE /api/reports/<id>.

    Доступ уточняется в _check_report_access():
      - писатели — свой отдел; админы/руководство НТЦ — везде;
      - рядовые исполнители — только по задачам, где они назначены.
    """

    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except Exception as e:
            logger.error("ReportDetailView.put error: %s", e, exc_info=True)
            return Response(
                {"error": f"Внутренняя ошибка сервера: {e}"},
                status=500,
            )

    def delete(self, request, pk):
        try:
            try:
                report = WorkReport.objects.select_related("work").get(pk=pk)
            except WorkReport.DoesNotExist:
                return Response(
                    {"error": "Отчёт не найден"},
                    status=404,
                )
            vis_q = get_visibility_filter(request.user)
            if not Work.objects.filter(pk=report.work_id).filter(vis_q).exists():
                return Response(
                    {"error": "Задача не найдена или нет доступа"},
                    status=403,
                )
            err = _check_report_access(request.user, report)
            if err:
                return Response({"error": err}, status=403)
            report.delete()
            return Response({"ok": True})
        except Exception as e:
            logger.error("ReportDetailView.delete error: %s", e, exc_info=True)
            return Response(
                {"error": f"Внутренняя ошибка сервера: {e}"},
                status=500,
            )

    def _update(self, request, pk):
        d = request.data
        if not isinstance(d, dict):
            return Response({"error": "Невалидный JSON"}, status=400)
        if not d:
            return Response({"error": "Пустое тело запроса"}, status=400)

        try:
            report = WorkReport.objects.select_related("work").get(pk=pk)
        except WorkReport.DoesNotExist:
            return Response({"error": "Отчёт не найден"}, status=404)

        vis_q = get_visibility_filter(request.user)
        if not Work.objects.filter(pk=report.work_id).filter(vis_q).exists():
            return Response(
                {"error": "Задача не найдена или нет доступа"},
                status=403,
            )
        err = _check_report_access(request.user, report)
        if err:
            return Response({"error": err}, status=403)

        if "doc_link" in d:
            url_err = _validate_url(d["doc_link"])
            if url_err:
                return Response({"error": url_err}, status=400)

        report.doc_name = d.get("doc_name") or report.doc_name or ""
        report.doc_designation = (
            d.get("doc_designation") or report.doc_designation or ""
        )
        report.ii_pi = d.get("ii_pi") or report.ii_pi or ""
        report.doc_number = d.get("doc_number") or report.doc_number or ""
        report.inventory_num = d.get("inventory_num") or report.inventory_num or ""
        report.doc_type = d.get("doc_type") or report.doc_type or ""
        report.doc_class = d.get("doc_class") or report.doc_class or ""
        report.norm_control = d.get("norm_control") or report.norm_control or ""
        report.doc_link = d.get("doc_link") or report.doc_link or ""

        if "date_accepted" in d:
            da = _safe_date(d["date_accepted"])
            if da and da > timezone.now().date():
                return Response(
                    {"error": "Дата выпуска не может быть позже текущей даты"},
                    status=400,
                )
            report.date_accepted = da
        if "date_expires" in d:
            report.date_expires = _safe_date(d["date_expires"])
        if "sheets_a4" in d:
            report.sheets_a4 = _safe_int(d["sheets_a4"])
        if "norm" in d:
            report.norm = _safe_decimal(d["norm"])
        if "coeff" in d:
            report.coeff = _safe_decimal(d["coeff"])
        if "bvd_hours" in d:
            report.bvd_hours = _safe_decimal(d["bvd_hours"])

        with transaction.atomic():
            report.save()
            _sync_notice_for_report(report)
        return Response({"ok": True})
