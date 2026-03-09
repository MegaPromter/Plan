"""
API отчётных документов (WorkReport).

Аналог Flask-эндпоинтов:
  GET    /api/reports/<task_id>  — список отчётов по задаче
  POST   /api/reports           — создание отчёта
  PUT    /api/reports/<id>      — обновление отчёта
  DELETE /api/reports/<id>      — удаление отчёта
"""
import logging
from datetime import date as dt_date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.works.models import Work, WorkReport

logger = logging.getLogger(__name__)


def _check_report_access(user, report):
    """Проверка: writer может менять отчёт только для задачи своего отдела.
    admin / ntc_head / ntc_deputy — без ограничений.
    Возвращает строку ошибки или None (доступ разрешён)."""
    employee = getattr(user, 'employee', None)
    if not employee:
        return 'Нет профиля сотрудника'
    if employee.role in ('admin', 'ntc_head', 'ntc_deputy'):
        return None
    if not employee.department:
        return 'Вашему профилю не назначен отдел'
    work = report.work
    if work and work.department_id and employee.department_id != work.department_id:
        return 'Вы можете редактировать только отчёты своего отдела'
    return None


def _serialize_report(r):
    """Сериализует WorkReport в dict для JSON-ответа."""
    return {
        'id': r.id,
        'task_id': r.work_id,
        'doc_name': r.doc_name or '',
        'doc_designation': r.doc_designation or '',
        'doc_number': r.doc_number or '',
        'inventory_num': r.inventory_num or '',
        'date_accepted': (r.date_accepted.isoformat()
                          if r.date_accepted else ''),
        'doc_type': r.doc_type or '',
        'doc_class': r.doc_class or '',
        'sheets_a4': r.sheets_a4,
        'norm': float(r.norm) if r.norm is not None else None,
        'coeff': float(r.coeff) if r.coeff is not None else None,
        'bvd_hours': float(r.bvd_hours) if r.bvd_hours is not None else None,
        'norm_control': r.norm_control or '',
        'doc_link': r.doc_link or '',
    }


def _safe_decimal(val):
    """Безопасное преобразование в Decimal или None."""
    if val is None or val == '':
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_int(val):
    """Безопасное преобразование в int или None."""
    if val is None or val == '':
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_date(val):
    """Безопасное преобразование строки в date или None."""
    if not val:
        return None
    try:
        return dt_date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
#  GET /api/reports/<task_id>
# ---------------------------------------------------------------------------

class ReportListView(LoginRequiredJsonMixin, View):
    """GET /api/reports/<task_id> — список отчётов по задаче."""

    def get(self, request, task_id):
        try:
            reports = WorkReport.objects.filter(work_id=task_id).order_by('id')
            result = [_serialize_report(r) for r in reports]
            return JsonResponse(result, safe=False)
        except Exception as e:
            logger.error("ReportListView.get error: %s", e, exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
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
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def _create(self, request):
        d = parse_json_body(request)
        if not d:
            return JsonResponse({'error': 'Пустое тело запроса'}, status=400)

        task_id = d.get('task_id')
        if not task_id:
            return JsonResponse(
                {'error': 'task_id обязателен'}, status=400,
            )

        # Проверяем существование задачи
        if not Work.objects.filter(pk=task_id).exists():
            return JsonResponse({'error': 'Задача не найдена'}, status=404)

        report = WorkReport.objects.create(
            work_id=task_id,
            doc_name=d.get('doc_name', ''),
            doc_designation=d.get('doc_designation', ''),
            doc_number=d.get('doc_number', ''),
            inventory_num=d.get('inventory_num', ''),
            date_accepted=_safe_date(d.get('date_accepted')),
            doc_type=d.get('doc_type', ''),
            doc_class=d.get('doc_class', ''),
            sheets_a4=_safe_int(d.get('sheets_a4')),
            norm=_safe_decimal(d.get('norm')),
            coeff=_safe_decimal(d.get('coeff')),
            bvd_hours=_safe_decimal(d.get('bvd_hours')),
            norm_control=d.get('norm_control', ''),
            doc_link=d.get('doc_link', ''),
        )
        return JsonResponse({'id': report.id})


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
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def delete(self, request, pk):
        try:
            report = WorkReport.objects.select_related('work').filter(pk=pk).first()
            if not report:
                return JsonResponse(
                    {'error': 'Отчёт не найден'}, status=404,
                )
            # Проверка доступа по отделу задачи
            err = _check_report_access(request.user, report)
            if err:
                return JsonResponse({'error': err}, status=403)
            report.delete()
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error("ReportDetailView.delete error: %s", e, exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def _update(self, request, pk):
        d = parse_json_body(request)
        if not d:
            return JsonResponse({'error': 'Пустое тело запроса'}, status=400)

        report = WorkReport.objects.select_related('work').filter(pk=pk).first()
        if not report:
            return JsonResponse({'error': 'Отчёт не найден'}, status=404)

        # Проверка доступа по отделу задачи
        err = _check_report_access(request.user, report)
        if err:
            return JsonResponse({'error': err}, status=403)

        report.doc_name = d.get('doc_name', report.doc_name)
        report.doc_designation = d.get('doc_designation', report.doc_designation)
        report.doc_number = d.get('doc_number', report.doc_number)
        report.inventory_num = d.get('inventory_num', report.inventory_num)
        report.doc_type = d.get('doc_type', report.doc_type)
        report.doc_class = d.get('doc_class', report.doc_class)
        report.norm_control = d.get('norm_control', report.norm_control)
        report.doc_link = d.get('doc_link', report.doc_link)

        if 'date_accepted' in d:
            report.date_accepted = _safe_date(d['date_accepted'])
        if 'sheets_a4' in d:
            report.sheets_a4 = _safe_int(d['sheets_a4'])
        if 'norm' in d:
            report.norm = _safe_decimal(d['norm'])
        if 'coeff' in d:
            report.coeff = _safe_decimal(d['coeff'])
        if 'bvd_hours' in d:
            report.bvd_hours = _safe_decimal(d['bvd_hours'])

        report.save()
        return JsonResponse({'ok': True})
