"""
API для журнала извещений (Notice).

CRUD-операции над таблицей Notice (аналог Flask journal).
GET     /api/journal          -- список записей журнала
POST    /api/journal          -- создание записи (writer)
PUT     /api/journal/<id>     -- обновление записи (writer)
DELETE  /api/journal/<id>     -- удаление записи (writer)
"""
import logging
from datetime import date

from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.employees.models import Department, Employee
from apps.works.models import Notice

logger = logging.getLogger(__name__)


def _check_journal_access(user, notice):
    """Проверка: writer может менять только записи своего отдела.
    admin / ntc_head / ntc_deputy — без ограничений.
    Возвращает строку ошибки или None (доступ разрешён)."""
    employee = getattr(user, 'employee', None)
    if not employee:
        return 'Нет профиля сотрудника'
    if employee.role in ('admin', 'ntc_head', 'ntc_deputy'):
        return None
    if not employee.department:
        return 'Вашему профилю не назначен отдел'
    if notice.department_id and employee.department_id != notice.department_id:
        return 'Вы можете редактировать только записи своего отдела'
    return None

# Максимальное количество записей на странице
JOURNAL_MAX = 500

# Поля, допустимые для обновления
JOURNAL_ALLOWED_FIELDS = {
    'notice_type', 'dept', 'executor', 'date_issued',
    'subject', 'description', 'status',
}


# ── GET / POST /api/journal ─────────────────────────────────────────────────

class JournalListView(LoginRequiredJsonMixin, View):
    """
    GET  -- список записей журнала с фильтрами и пагинацией.
    """

    def get(self, request):
        # Пагинация
        try:
            per_page = int(request.GET.get('per_page', 0)) or JOURNAL_MAX
            page = int(request.GET.get('page', 1))
        except (ValueError, TypeError):
            per_page, page = JOURNAL_MAX, 1
        per_page = min(per_page, JOURNAL_MAX)
        page = max(page, 1)
        offset = (page - 1) * per_page

        qs = Notice.objects.select_related('department', 'executor')

        # Фильтр по статусу
        status = request.GET.get('status', '').strip()
        if status:
            qs = qs.filter(status=status)

        # Фильтр по отделу
        dept = request.GET.get('dept', '').strip()
        if dept:
            qs = qs.filter(department__code=dept)

        qs = qs.order_by('-created_at')

        rows = qs[offset:offset + per_page]
        result = []
        for n in rows:
            result.append({
                'id': n.pk,
                'notice_type': n.notice_type,
                'dept': n.department.code if n.department else '',
                'executor': n.executor.full_name if n.executor else '',
                'date_issued': n.date_issued.isoformat() if n.date_issued else '',
                'subject': n.subject,
                'description': n.description,
                'status': n.status,
            })

        return JsonResponse(result, safe=False)


class JournalCreateView(WriterRequiredJsonMixin, View):
    """POST -- создание записи журнала."""

    def post(self, request):
        data = parse_json_body(request)

        notice_type = data.get('notice_type', '')
        dept_code = data.get('dept', '').strip()
        executor_name = data.get('executor', '').strip()
        date_issued_str = data.get('date_issued', '')
        subject = data.get('subject', '')
        description = data.get('description', '')
        status = data.get('status', Notice.STATUS_ACTIVE)

        # Ищем отдел по коду
        department = None
        if dept_code:
            department = Department.objects.filter(code=dept_code).first()

        # Ищем исполнителя по имени
        executor = None
        if executor_name:
            parts = executor_name.split()
            qs = Employee.objects.all()
            if len(parts) >= 1:
                qs = qs.filter(last_name__iexact=parts[0])
            if len(parts) >= 2:
                qs = qs.filter(first_name__iexact=parts[1])
            if len(parts) >= 3:
                qs = qs.filter(patronymic__iexact=parts[2])
            executor = qs.first()

        # Парсим дату
        date_issued = None
        if date_issued_str:
            try:
                date_issued = date.fromisoformat(date_issued_str)
            except (ValueError, TypeError):
                pass

        # Валидация статуса
        if status not in (Notice.STATUS_ACTIVE, Notice.STATUS_CLOSED):
            status = Notice.STATUS_ACTIVE

        notice = Notice.objects.create(
            notice_type=notice_type,
            department=department,
            executor=executor,
            date_issued=date_issued,
            subject=subject,
            description=description,
            status=status,
        )

        return JsonResponse({'id': notice.pk}, status=201)


# ── PUT / DELETE /api/journal/<id> ──────────────────────────────────────────

class JournalDetailView(WriterRequiredJsonMixin, View):
    """
    PUT    -- обновление записи журнала.
    DELETE -- удаление записи журнала.
    """

    def put(self, request, pk):
        data = parse_json_body(request)
        if not data:
            return JsonResponse({'ok': True})

        try:
            notice = Notice.objects.select_related('department').get(pk=pk)
        except Notice.DoesNotExist:
            return JsonResponse({'error': 'Запись не найдена'}, status=404)

        # Проверка доступа по отделу
        err = _check_journal_access(request.user, notice)
        if err:
            return JsonResponse({'error': err}, status=403)

        # Фильтрация: принимаем только допустимые поля
        updates = {k: v for k, v in data.items() if k in JOURNAL_ALLOWED_FIELDS}
        if not updates:
            return JsonResponse({'ok': True})

        update_fields = []

        if 'notice_type' in updates:
            notice.notice_type = updates['notice_type']
            update_fields.append('notice_type')

        if 'dept' in updates:
            dept_code = updates['dept'].strip() if updates['dept'] else ''
            if dept_code:
                department = Department.objects.filter(code=dept_code).first()
                notice.department = department
            else:
                notice.department = None
            update_fields.append('department')

        if 'executor' in updates:
            executor_name = updates['executor'].strip() if updates['executor'] else ''
            if executor_name:
                parts = executor_name.split()
                qs = Employee.objects.all()
                if len(parts) >= 1:
                    qs = qs.filter(last_name__iexact=parts[0])
                if len(parts) >= 2:
                    qs = qs.filter(first_name__iexact=parts[1])
                if len(parts) >= 3:
                    qs = qs.filter(patronymic__iexact=parts[2])
                notice.executor = qs.first()
            else:
                notice.executor = None
            update_fields.append('executor')

        if 'date_issued' in updates:
            date_str = updates['date_issued']
            if date_str:
                try:
                    notice.date_issued = date.fromisoformat(date_str)
                except (ValueError, TypeError):
                    pass
            else:
                notice.date_issued = None
            update_fields.append('date_issued')

        if 'subject' in updates:
            notice.subject = updates['subject']
            update_fields.append('subject')

        if 'description' in updates:
            notice.description = updates['description']
            update_fields.append('description')

        if 'status' in updates:
            status_val = updates['status']
            if status_val in (Notice.STATUS_ACTIVE, Notice.STATUS_CLOSED):
                notice.status = status_val
                update_fields.append('status')

        if update_fields:
            notice.save(update_fields=update_fields + ['updated_at'])

        return JsonResponse({'ok': True})

    def delete(self, request, pk):
        try:
            notice = Notice.objects.select_related('department').get(pk=pk)
        except Notice.DoesNotExist:
            return JsonResponse({'error': 'Запись не найдена'}, status=404)

        # Проверка доступа по отделу
        err = _check_journal_access(request.user, notice)
        if err:
            return JsonResponse({'error': err}, status=403)

        notice.delete()
        return JsonResponse({'ok': True})
