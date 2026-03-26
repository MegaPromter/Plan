"""
API наборов изменений (Changeset / Песочница).

Подразделение собирает правки в changeset, затем отправляет на согласование.
После утверждения изменения применяются атомарно к основной таблице Work.

Эндпоинты:
  GET    /api/changesets/                  — список наборов
  POST   /api/changesets/create/           — создание нового набора
  GET    /api/changesets/<pk>/             — детали набора
  PUT    /api/changesets/<pk>/             — обновление title/description
  DELETE /api/changesets/<pk>/             — удаление (только черновик)
  POST   /api/changesets/<pk>/items/       — добавление элемента
  PUT    /api/changeset_items/<pk>/        — обновление элемента
  DELETE /api/changeset_items/<pk>/        — удаление элемента
  POST   /api/changesets/<pk>/submit/      — отправка на согласование
  POST   /api/changesets/<pk>/approve/     — утверждение (атомарное применение)
  POST   /api/changesets/<pk>/reject/      — отклонение
  POST   /api/changesets/<pk>/reopen/      — переоткрытие (rejected → draft)
  GET    /api/changesets/<pk>/diff/        — просмотр изменений (diff)
"""
import logging
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.api.audit import log_action
from apps.api.utils import (
    PRODUCTION_ALLOWED_FIELDS, generate_row_code,
    safe_date, safe_decimal, resolve_employee,
)
from apps.works.models import (
    Work, PPProject, AuditLog, Changeset, ChangesetItem,
)
from apps.employees.models import Employee, Department, NTCCenter, Sector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Сериализация
# ---------------------------------------------------------------------------

def _serialize_changeset(cs, include_items=False):
    """Сериализует Changeset в dict."""
    data = {
        'id': cs.id,
        'pp_project_id': cs.pp_project_id,
        'pp_project_name': cs.pp_project.name if cs.pp_project else '',
        'department_id': cs.department_id,
        'department_name': cs.department.name if cs.department else '',
        'author_id': cs.author_id,
        'author_name': cs.author.get_full_name() if cs.author else '',
        'title': cs.title,
        'description': cs.description,
        'status': cs.status,
        'status_display': cs.get_status_display(),
        'reject_comment': cs.reject_comment,
        'items_count': cs.items.count(),
        'created_at': cs.created_at.isoformat() if cs.created_at else '',
        'updated_at': cs.updated_at.isoformat() if cs.updated_at else '',
        'submitted_at': cs.submitted_at.isoformat() if cs.submitted_at else '',
        'reviewed_by_name': cs.reviewed_by.get_full_name() if cs.reviewed_by else '',
        'reviewed_at': cs.reviewed_at.isoformat() if cs.reviewed_at else '',
        'published_at': cs.published_at.isoformat() if cs.published_at else '',
    }
    if include_items:
        data['items'] = [_serialize_item(item) for item in cs.items.all()]
    return data


def _serialize_item(item):
    """Сериализует ChangesetItem в dict."""
    return {
        'id': item.id,
        'changeset_id': item.changeset_id,
        'target_row_id': item.target_row_id,
        'action': item.action,
        'action_display': item.get_action_display(),
        'field_changes': item.field_changes,
        'original_data': item.original_data,
        'order': item.order,
        'created_at': item.created_at.isoformat() if item.created_at else '',
        'updated_at': item.updated_at.isoformat() if item.updated_at else '',
    }


def _snapshot_work(work):
    """Снимок текущего состояния Work-записи для original_data."""
    return {
        'id': work.id,
        'work_name': work.work_name or '',
        'row_code': work.row_code or '',
        'work_order': work.work_order or '',
        'stage_num': work.stage_num or '',
        'milestone_num': work.milestone_num or '',
        'work_num': work.work_num or '',
        'work_designation': work.work_designation or '',
        'task_type': work.task_type or '',
        'sheets_a4': float(work.sheets_a4) if work.sheets_a4 is not None else None,
        'norm': float(work.norm) if work.norm is not None else None,
        'coeff': float(work.coeff) if work.coeff is not None else None,
        'total_2d': float(work.total_2d) if work.total_2d is not None else None,
        'total_3d': float(work.total_3d) if work.total_3d is not None else None,
        'labor': float(work.labor) if work.labor is not None else None,
        'date_start': work.date_start.isoformat() if work.date_start else None,
        'date_end': work.date_end.isoformat() if work.date_end else None,
        'executor_id': work.executor_id,
        'department_id': work.department_id,
        'sector_id': work.sector_id,
        'ntc_center_id': work.ntc_center_id,
    }


def _is_approver(user):
    """Проверяет, может ли пользователь утверждать/отклонять наборы."""
    if user.is_superuser:
        return True
    emp = getattr(user, 'employee', None)
    if emp and emp.role in ('admin', 'ntc_head', 'ntc_deputy'):
        return True
    return False


# ---------------------------------------------------------------------------
#  GET /api/changesets/
# ---------------------------------------------------------------------------

class ChangesetListView(LoginRequiredJsonMixin, View):
    """Список наборов изменений. Фильтры: pp_project_id, status, department_id."""

    def get(self, request):
        qs = Changeset.objects.select_related(
            'pp_project', 'department', 'author', 'reviewed_by',
        )

        pp_id = request.GET.get('pp_project_id')
        if pp_id:
            qs = qs.filter(pp_project_id=pp_id)

        status = request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        dept_id = request.GET.get('department_id')
        if dept_id:
            qs = qs.filter(department_id=dept_id)

        data = [_serialize_changeset(cs) for cs in qs[:200]]
        return JsonResponse({'items': data})


# ---------------------------------------------------------------------------
#  POST /api/changesets/create/
# ---------------------------------------------------------------------------

class ChangesetCreateView(WriterRequiredJsonMixin, View):
    """Создание нового набора изменений (черновик)."""

    def post(self, request):
        body = parse_json_body(request)
        if isinstance(body, JsonResponse):
            return body

        pp_project_id = body.get('pp_project_id')
        if not pp_project_id:
            return JsonResponse({'error': 'pp_project_id обязателен'}, status=400)

        try:
            pp_project = PPProject.objects.get(pk=pp_project_id)
        except PPProject.DoesNotExist:
            return JsonResponse({'error': 'Проект ПП не найден'}, status=404)

        title = (body.get('title') or '').strip()
        if not title:
            return JsonResponse({'error': 'Название обязательно'}, status=400)

        emp = getattr(request.user, 'employee', None)

        cs = Changeset.objects.create(
            pp_project=pp_project,
            department=emp.department if emp else None,
            author=request.user,
            title=title,
            description=(body.get('description') or '').strip(),
        )

        log_action(
            request, AuditLog.ACTION_CS_CREATE,
            object_id=cs.id,
            object_repr=f'Набор изменений: {cs.title}',
            details={'pp_project_id': pp_project_id},
        )

        return JsonResponse(_serialize_changeset(cs), status=201)


# ---------------------------------------------------------------------------
#  GET/PUT/DELETE /api/changesets/<pk>/
# ---------------------------------------------------------------------------

class ChangesetDetailView(LoginRequiredJsonMixin, View):
    """Детали, обновление, удаление набора изменений."""

    def get(self, request, pk):
        try:
            cs = Changeset.objects.select_related(
                'pp_project', 'department', 'author', 'reviewed_by',
            ).prefetch_related('items').get(pk=pk)
        except Changeset.DoesNotExist:
            return JsonResponse({'error': 'Набор не найден'}, status=404)
        return JsonResponse(_serialize_changeset(cs, include_items=True))

    def put(self, request, pk):
        body = parse_json_body(request)
        if isinstance(body, JsonResponse):
            return body

        try:
            cs = Changeset.objects.get(pk=pk)
        except Changeset.DoesNotExist:
            return JsonResponse({'error': 'Набор не найден'}, status=404)

        if cs.status != Changeset.STATUS_DRAFT:
            return JsonResponse({'error': 'Редактирование возможно только для черновика'}, status=400)

        if 'title' in body:
            cs.title = (body['title'] or '').strip() or cs.title
        if 'description' in body:
            cs.description = (body['description'] or '').strip()
        cs.save(update_fields=['title', 'description', 'updated_at'])

        return JsonResponse(_serialize_changeset(cs))

    def delete(self, request, pk):
        try:
            cs = Changeset.objects.get(pk=pk)
        except Changeset.DoesNotExist:
            return JsonResponse({'error': 'Набор не найден'}, status=404)

        if cs.status != Changeset.STATUS_DRAFT:
            return JsonResponse({'error': 'Удаление возможно только для черновика'}, status=400)

        # Только автор или admin
        if cs.author_id != request.user.id and not _is_approver(request.user):
            return JsonResponse({'error': 'Нет прав'}, status=403)

        cs.delete()
        return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
#  POST /api/changesets/<pk>/items/
# ---------------------------------------------------------------------------

class ChangesetItemCreateView(WriterRequiredJsonMixin, View):
    """Добавление элемента в набор изменений."""

    def post(self, request, pk):
        body = parse_json_body(request)
        if isinstance(body, JsonResponse):
            return body

        try:
            cs = Changeset.objects.get(pk=pk)
        except Changeset.DoesNotExist:
            return JsonResponse({'error': 'Набор не найден'}, status=404)

        if cs.status != Changeset.STATUS_DRAFT:
            return JsonResponse({'error': 'Добавление возможно только в черновик'}, status=400)

        action = body.get('action')
        if action not in ('create', 'update', 'delete'):
            return JsonResponse({'error': 'action должен быть create/update/delete'}, status=400)

        target_row_id = body.get('target_row_id')
        target_row = None
        original_data = {}

        if action in ('update', 'delete'):
            if not target_row_id:
                return JsonResponse({'error': 'target_row_id обязателен для update/delete'}, status=400)
            try:
                target_row = Work.objects.get(pk=target_row_id, show_in_pp=True)
            except Work.DoesNotExist:
                return JsonResponse({'error': 'Строка ПП не найдена'}, status=404)
            original_data = _snapshot_work(target_row)

            # Проверяем: нет ли уже такого же действия в этом наборе для этой строки
            existing = ChangesetItem.objects.filter(
                changeset=cs, target_row=target_row, action=action,
            ).first()
            if existing and action == 'delete':
                return JsonResponse({'error': 'Эта строка уже отмечена на удаление'}, status=400)
            # Для update — обновляем существующий item, а не создаём новый
            if existing and action == 'update':
                changes = existing.field_changes
                changes.update(body.get('field_changes', {}))
                existing.field_changes = changes
                existing.save(update_fields=['field_changes', 'updated_at'])
                return JsonResponse(_serialize_item(existing), status=200)

        field_changes = body.get('field_changes', {})
        if action == 'create' and not field_changes:
            return JsonResponse({'error': 'field_changes обязателен для create'}, status=400)

        # Определяем порядок
        max_order = cs.items.order_by('-order').values_list('order', flat=True).first() or 0

        item = ChangesetItem.objects.create(
            changeset=cs,
            target_row=target_row,
            action=action,
            field_changes=field_changes,
            original_data=original_data,
            order=max_order + 1,
        )

        return JsonResponse(_serialize_item(item), status=201)


# ---------------------------------------------------------------------------
#  PUT/DELETE /api/changeset_items/<pk>/
# ---------------------------------------------------------------------------

class ChangesetItemDetailView(WriterRequiredJsonMixin, View):
    """Обновление и удаление элемента набора."""

    def put(self, request, pk):
        body = parse_json_body(request)
        if isinstance(body, JsonResponse):
            return body

        try:
            item = ChangesetItem.objects.select_related('changeset').get(pk=pk)
        except ChangesetItem.DoesNotExist:
            return JsonResponse({'error': 'Элемент не найден'}, status=404)

        if item.changeset.status != Changeset.STATUS_DRAFT:
            return JsonResponse({'error': 'Редактирование возможно только в черновике'}, status=400)

        if 'field_changes' in body:
            item.field_changes = body['field_changes']
        if 'order' in body:
            item.order = int(body['order'])
        item.save(update_fields=['field_changes', 'order', 'updated_at'])

        return JsonResponse(_serialize_item(item))

    def delete(self, request, pk):
        try:
            item = ChangesetItem.objects.select_related('changeset').get(pk=pk)
        except ChangesetItem.DoesNotExist:
            return JsonResponse({'error': 'Элемент не найден'}, status=404)

        if item.changeset.status != Changeset.STATUS_DRAFT:
            return JsonResponse({'error': 'Удаление возможно только из черновика'}, status=400)

        item.delete()
        return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
#  POST /api/changesets/<pk>/submit/
# ---------------------------------------------------------------------------

class ChangesetSubmitView(WriterRequiredJsonMixin, View):
    """Отправка набора на согласование (draft → review)."""

    def post(self, request, pk):
        try:
            cs = Changeset.objects.get(pk=pk)
        except Changeset.DoesNotExist:
            return JsonResponse({'error': 'Набор не найден'}, status=404)

        if cs.status != Changeset.STATUS_DRAFT:
            return JsonResponse({'error': 'Отправить можно только черновик'}, status=400)

        if not cs.items.exists():
            return JsonResponse({'error': 'Набор пуст — добавьте хотя бы одно изменение'}, status=400)

        cs.status = Changeset.STATUS_REVIEW
        cs.submitted_at = timezone.now()
        cs.save(update_fields=['status', 'submitted_at', 'updated_at'])

        log_action(
            request, AuditLog.ACTION_CS_SUBMIT,
            object_id=cs.id,
            object_repr=f'Набор изменений: {cs.title}',
            details={'items_count': cs.items.count()},
        )

        return JsonResponse(_serialize_changeset(cs))


# ---------------------------------------------------------------------------
#  POST /api/changesets/<pk>/approve/
# ---------------------------------------------------------------------------

class ChangesetApproveView(LoginRequiredJsonMixin, View):
    """
    Утверждение набора (review → approved).
    Атомарно применяет все изменения к таблице Work.
    """

    def post(self, request, pk):
        if not _is_approver(request.user):
            return JsonResponse({'error': 'Нет прав на утверждение'}, status=403)

        try:
            with transaction.atomic():
                cs = Changeset.objects.select_for_update().get(pk=pk)

                if cs.status != Changeset.STATUS_REVIEW:
                    return JsonResponse(
                        {'error': 'Утвердить можно только набор на согласовании'},
                        status=400,
                    )

                items = list(cs.items.select_related('target_row').order_by('order'))
                conflicts = []
                applied = 0

                for item in items:
                    if item.action == ChangesetItem.ACTION_CREATE:
                        self._apply_create(item, cs, request)
                        applied += 1

                    elif item.action == ChangesetItem.ACTION_UPDATE:
                        conflict = self._apply_update(item)
                        if conflict:
                            conflicts.append(conflict)
                        else:
                            applied += 1

                    elif item.action == ChangesetItem.ACTION_DELETE:
                        self._apply_delete(item)
                        applied += 1

                if conflicts:
                    # Откатываем транзакцию — не применяем частично
                    raise _ConflictException(conflicts)

                cs.status = Changeset.STATUS_APPROVED
                cs.reviewed_by = request.user
                cs.reviewed_at = timezone.now()
                cs.published_at = timezone.now()
                cs.save(update_fields=[
                    'status', 'reviewed_by', 'reviewed_at', 'published_at', 'updated_at',
                ])

                log_action(
                    request, AuditLog.ACTION_CS_APPROVE,
                    object_id=cs.id,
                    object_repr=f'Набор изменений: {cs.title}',
                    details={'applied': applied},
                )

        except _ConflictException as e:
            return JsonResponse({
                'error': 'Обнаружены конфликты — данные изменились после создания набора',
                'conflicts': e.conflicts,
            }, status=409)

        return JsonResponse(_serialize_changeset(cs))

    def _apply_create(self, item, cs, request):
        """Создать новую строку Work из field_changes."""
        fc = item.field_changes
        emp = getattr(request.user, 'employee', None)
        work = Work(
            show_in_pp=True,
            pp_project=cs.pp_project,
            work_name=fc.get('work_name', 'Новая запись'),
            department=cs.department,
            created_by=emp,
        )
        # Применяем поля из field_changes
        self._set_fields(work, fc)
        # Генерируем row_code
        if not work.row_code and cs.pp_project and cs.pp_project.up_project:
            work.row_code = generate_row_code(cs.pp_project.up_project)
        work.save()

    def _apply_update(self, item):
        """Обновить существующую строку. Возвращает dict конфликта или None."""
        work = Work.objects.select_for_update().filter(pk=item.target_row_id).first()
        if not work:
            return {'item_id': item.id, 'error': 'Строка удалена'}

        # Проверяем конфликты: сравниваем original_data с текущим состоянием
        current = _snapshot_work(work)
        for field, orig_val in item.original_data.items():
            if field == 'id':
                continue
            cur_val = current.get(field)
            if str(orig_val) != str(cur_val):
                # Значение изменилось с момента создания item
                new_val = item.field_changes.get(field)
                if new_val is not None:
                    # Конфликт: мы хотим изменить поле, которое уже изменилось
                    return {
                        'item_id': item.id,
                        'target_row_id': item.target_row_id,
                        'field': field,
                        'expected': orig_val,
                        'actual': cur_val,
                        'wanted': new_val,
                    }

        # Конфликтов нет — применяем
        self._set_fields(work, item.field_changes)
        work.save()
        return None

    def _apply_delete(self, item):
        """Удалить строку (или скрыть из ПП если есть в СП)."""
        work = Work.objects.select_for_update().filter(pk=item.target_row_id).first()
        if not work:
            return  # уже удалена
        if work.show_in_plan:
            work.show_in_pp = False
            work.save(update_fields=['show_in_pp'])
        else:
            work.delete()

    def _set_fields(self, work, fc):
        """Устанавливает поля Work из dict field_changes."""
        text_fields = {
            'work_name', 'row_code', 'work_order', 'stage_num',
            'milestone_num', 'work_num', 'work_designation', 'task_type',
        }
        decimal_fields = {'sheets_a4', 'norm', 'coeff', 'total_2d', 'total_3d', 'labor'}
        date_fields = {'date_start', 'date_end'}
        fk_fields = {
            'executor_id': (Employee, 'executor'),
            'department_id': (Department, 'department'),
            'sector_id': (Sector, 'sector'),
            'ntc_center_id': (NTCCenter, 'ntc_center'),
        }

        for field, val in fc.items():
            if field in text_fields:
                setattr(work, field, val or '')
            elif field in decimal_fields:
                setattr(work, field, safe_decimal(val))
            elif field in date_fields:
                setattr(work, field, safe_date(val))
            elif field in fk_fields:
                model_cls, attr_name = fk_fields[field]
                if val:
                    try:
                        obj = model_cls.objects.get(pk=val)
                        setattr(work, attr_name, obj)
                    except model_cls.DoesNotExist:
                        pass
                else:
                    setattr(work, attr_name, None)


class _ConflictException(Exception):
    def __init__(self, conflicts):
        self.conflicts = conflicts


# ---------------------------------------------------------------------------
#  POST /api/changesets/<pk>/reject/
# ---------------------------------------------------------------------------

class ChangesetRejectView(LoginRequiredJsonMixin, View):
    """Отклонение набора (review → rejected) с комментарием."""

    def post(self, request, pk):
        if not _is_approver(request.user):
            return JsonResponse({'error': 'Нет прав на отклонение'}, status=403)

        body = parse_json_body(request)
        if isinstance(body, JsonResponse):
            return body

        try:
            cs = Changeset.objects.get(pk=pk)
        except Changeset.DoesNotExist:
            return JsonResponse({'error': 'Набор не найден'}, status=404)

        if cs.status != Changeset.STATUS_REVIEW:
            return JsonResponse({'error': 'Отклонить можно только набор на согласовании'}, status=400)

        comment = (body.get('reject_comment') or '').strip()
        if not comment:
            return JsonResponse({'error': 'Укажите причину отклонения'}, status=400)

        cs.status = Changeset.STATUS_REJECTED
        cs.reject_comment = comment
        cs.reviewed_by = request.user
        cs.reviewed_at = timezone.now()
        cs.save(update_fields=[
            'status', 'reject_comment', 'reviewed_by', 'reviewed_at', 'updated_at',
        ])

        log_action(
            request, AuditLog.ACTION_CS_REJECT,
            object_id=cs.id,
            object_repr=f'Набор изменений: {cs.title}',
            details={'reject_comment': comment},
        )

        return JsonResponse(_serialize_changeset(cs))


# ---------------------------------------------------------------------------
#  POST /api/changesets/<pk>/reopen/
# ---------------------------------------------------------------------------

class ChangesetReopenView(WriterRequiredJsonMixin, View):
    """Переоткрытие набора (rejected → draft)."""

    def post(self, request, pk):
        try:
            cs = Changeset.objects.get(pk=pk)
        except Changeset.DoesNotExist:
            return JsonResponse({'error': 'Набор не найден'}, status=404)

        if cs.status != Changeset.STATUS_REJECTED:
            return JsonResponse({'error': 'Переоткрыть можно только отклонённый набор'}, status=400)

        cs.status = Changeset.STATUS_DRAFT
        cs.reject_comment = ''
        cs.reviewed_by = None
        cs.reviewed_at = None
        cs.save(update_fields=[
            'status', 'reject_comment', 'reviewed_by', 'reviewed_at', 'updated_at',
        ])

        return JsonResponse(_serialize_changeset(cs))


# ---------------------------------------------------------------------------
#  GET /api/changesets/<pk>/diff/
# ---------------------------------------------------------------------------

class ChangesetDiffView(LoginRequiredJsonMixin, View):
    """Просмотр всех изменений набора в формате diff."""

    def get(self, request, pk):
        try:
            cs = Changeset.objects.select_related('pp_project', 'department', 'author').get(pk=pk)
        except Changeset.DoesNotExist:
            return JsonResponse({'error': 'Набор не найден'}, status=404)

        items = cs.items.select_related('target_row').order_by('order')
        diff_items = []

        for item in items:
            entry = {
                'id': item.id,
                'action': item.action,
                'action_display': item.get_action_display(),
                'target_row_id': item.target_row_id,
                'field_changes': item.field_changes,
                'original_data': item.original_data,
            }

            if item.action == ChangesetItem.ACTION_UPDATE and item.target_row:
                # Показываем текущее состояние для обнаружения конфликтов
                entry['current_data'] = _snapshot_work(item.target_row)
                # Построим per-field diff
                changes = []
                for field, new_val in item.field_changes.items():
                    old_val = item.original_data.get(field, '')
                    cur_val = entry['current_data'].get(field, '')
                    changes.append({
                        'field': field,
                        'old': old_val,
                        'new': new_val,
                        'conflict': str(old_val) != str(cur_val),
                    })
                entry['changes'] = changes

            elif item.action == ChangesetItem.ACTION_CREATE:
                entry['new_data'] = item.field_changes

            elif item.action == ChangesetItem.ACTION_DELETE:
                entry['deleted_data'] = item.original_data

            diff_items.append(entry)

        return JsonResponse({
            'changeset': _serialize_changeset(cs),
            'diff': diff_items,
            'summary': {
                'creates': sum(1 for i in diff_items if i['action'] == 'create'),
                'updates': sum(1 for i in diff_items if i['action'] == 'update'),
                'deletes': sum(1 for i in diff_items if i['action'] == 'delete'),
                'total': len(diff_items),
            },
        })
