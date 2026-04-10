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
from django.http import JsonResponse
from django.utils import timezone
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.api.utils import get_visibility_filter, safe_date, safe_decimal, safe_int
from apps.works.models import Notice, Work, WorkReport

logger = logging.getLogger(__name__)

NOTICE_TASK_TYPE = "Корректировка документа"

_URL_RE = re.compile(
    r"^https?://"  # http:// или https://
    r"[A-Za-z0-9]"  # домен начинается с буквы/цифры
    r"[A-Za-z0-9._-]*"  # остальная часть домена
    r"\."  # обязательная точка
    r"[A-Za-z]{2,}"  # TLD минимум 2 буквы
    r"[^\s]*$",  # путь/параметры (без пробелов)
    re.IGNORECASE,
)


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
    Возвращает строку ошибки или None (доступ разрешён)."""
    employee = getattr(user, "employee", None)
    if not employee:
        return "Нет профиля сотрудника"
    if employee.role in ("admin", "ntc_head", "ntc_deputy"):
        return None
    if not employee.department:
        return "Вашему профилю не назначен отдел"
    work = report.work
    if work and work.department_id and employee.department_id != work.department_id:
        return "Вы можете редактировать только отчёты своего отдела"
    return None


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
    }


# _safe_decimal / _safe_int / _safe_date → вынесены в apps.api.utils
_safe_decimal = safe_decimal
_safe_int = safe_int
_safe_date = safe_date


# ---------------------------------------------------------------------------
#  GET /api/reports/<task_id>
# ---------------------------------------------------------------------------


class ReportListView(LoginRequiredJsonMixin, View):
    """GET /api/reports/<task_id> — список отчётов по задаче."""

    def get(self, request, task_id):
        try:
            # Проверяем, что задача существует И видима для текущего пользователя
            vis_q = get_visibility_filter(request.user)
            if not Work.objects.filter(vis_q, pk=task_id).exists():
                return JsonResponse(
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
            return JsonResponse(result, safe=False)
        except (ValueError, TypeError) as e:
            logger.warning("ReportListView.get bad request: %s", e)
            return JsonResponse({"error": f"Некорректные параметры: {e}"}, status=400)
        except Exception as e:
            logger.error("ReportListView.get error: %s", e, exc_info=True)
            return JsonResponse(
                {"error": f"Внутренняя ошибка сервера: {e}"},
                status=500,
            )


# ---------------------------------------------------------------------------
#  POST /api/reports
# ---------------------------------------------------------------------------


class ReportCreateView(WriterRequiredJsonMixin, View):
    """POST /api/reports — создание отчёта."""

    def post(self, request):
        try:
            return self._create(request)
        except Exception as e:
            logger.error("ReportCreateView error: %s", e, exc_info=True)
            return JsonResponse(
                {"error": f"Внутренняя ошибка сервера: {e}"},
                status=500,
            )

    def _create(self, request):
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)
        if not d:
            return JsonResponse({"error": "Пустое тело запроса"}, status=400)

        task_id = d.get("task_id")
        if not task_id:
            return JsonResponse(
                {"error": "task_id обязателен"},
                status=400,
            )

        # Проверяем существование задачи
        try:
            work = Work.objects.select_related("department").get(pk=task_id)
        except Work.DoesNotExist:
            return JsonResponse({"error": "Задача не найдена"}, status=404)

        # Проверка доступа по отделу (создавать отчёт — только свой отдел)
        employee = getattr(request.user, "employee", None)
        if employee and employee.role not in ("admin", "ntc_head", "ntc_deputy"):
            if not employee.department_id:
                return JsonResponse(
                    {"error": "Вашему профилю не назначен отдел"}, status=403
                )
            if work.department_id and employee.department_id != work.department_id:
                return JsonResponse(
                    {
                        "error": "Вы можете создавать отчёты только для задач своего отдела"
                    },
                    status=403,
                )

        url_err = _validate_url(d.get("doc_link"))
        if url_err:
            return JsonResponse({"error": url_err}, status=400)

        # Валидация: дата выпуска не может быть позже сегодня
        da = _safe_date(d.get("date_accepted"))
        if da and da > timezone.now().date():
            return JsonResponse(
                {"error": "Дата выпуска не может быть позже текущей даты"}, status=400
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
            # Авто-создание записи ЖИ для «Корректировка документа»
            # Присваиваем кешированный объект work, чтобы _sync_notice_for_report
            # не делал лишний SQL-запрос через FK
            report.work = work
            _sync_notice_for_report(report)
        return JsonResponse({"id": report.id})


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/reports/<id>
# ---------------------------------------------------------------------------


class ReportDetailView(WriterRequiredJsonMixin, View):
    """PUT /api/reports/<id>; DELETE /api/reports/<id>."""

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except Exception as e:
            logger.error("ReportDetailView.put error: %s", e, exc_info=True)
            return JsonResponse(
                {"error": f"Внутренняя ошибка сервера: {e}"},
                status=500,
            )

    def delete(self, request, pk):
        try:
            try:
                report = WorkReport.objects.select_related("work").get(pk=pk)
            except WorkReport.DoesNotExist:
                return JsonResponse(
                    {"error": "Отчёт не найден"},
                    status=404,
                )
            # Проверка видимости задачи для текущего пользователя
            vis_q = get_visibility_filter(request.user)
            if not Work.objects.filter(pk=report.work_id).filter(vis_q).exists():
                return JsonResponse(
                    {"error": "Задача не найдена или нет доступа"},
                    status=403,
                )
            # Проверка доступа по отделу задачи
            err = _check_report_access(request.user, report)
            if err:
                return JsonResponse({"error": err}, status=403)
            report.delete()
            return JsonResponse({"ok": True})
        except Exception as e:
            logger.error("ReportDetailView.delete error: %s", e, exc_info=True)
            return JsonResponse(
                {"error": f"Внутренняя ошибка сервера: {e}"},
                status=500,
            )

    def _update(self, request, pk):
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)
        if not d:
            return JsonResponse({"error": "Пустое тело запроса"}, status=400)

        try:
            report = WorkReport.objects.select_related("work").get(pk=pk)
        except WorkReport.DoesNotExist:
            return JsonResponse({"error": "Отчёт не найден"}, status=404)

        # Проверка видимости задачи для текущего пользователя
        vis_q = get_visibility_filter(request.user)
        if not Work.objects.filter(pk=report.work_id).filter(vis_q).exists():
            return JsonResponse(
                {"error": "Задача не найдена или нет доступа"},
                status=403,
            )
        # Проверка доступа по отделу задачи
        err = _check_report_access(request.user, report)
        if err:
            return JsonResponse({"error": err}, status=403)

        if "doc_link" in d:
            url_err = _validate_url(d["doc_link"])
            if url_err:
                return JsonResponse({"error": url_err}, status=400)

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
                return JsonResponse(
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
            # Синхронизация ЖИ при обновлении отчёта
            _sync_notice_for_report(report)
        return JsonResponse({"ok": True})
