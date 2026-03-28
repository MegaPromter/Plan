"""
API версий (baseline) и сценариев (what-if).

POST   /api/enterprise/cross/<project_id>/baselines/     — создание снимка
GET    /api/enterprise/cross/<project_id>/baselines/     — список снимков
GET    /api/enterprise/baselines/<id>/                   — просмотр снимка
DELETE /api/enterprise/baselines/<id>/                   — удаление снимка

GET    /api/enterprise/scenarios/                         — список сценариев
POST   /api/enterprise/scenarios/                         — создание сценария
GET    /api/enterprise/scenarios/<id>/                    — просмотр сценария
PUT    /api/enterprise/scenarios/<id>/                    — обновление сценария
DELETE /api/enterprise/scenarios/<id>/                    — удаление сценария
POST   /api/enterprise/scenarios/<id>/entries/            — добавление записи
"""
import logging

from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.works.models import Work, Project
from apps.enterprise.models import (
    CrossSchedule, CrossStage,
    BaselineSnapshot, BaselineEntry,
    Scenario, ScenarioEntry,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Baseline (версии сквозного графика)
# ---------------------------------------------------------------------------

def _serialize_baseline(snapshot, include_entries=False):
    d = {
        'id': snapshot.id,
        'cross_schedule_id': snapshot.cross_schedule_id,
        'version': snapshot.version,
        'comment': snapshot.comment or '',
        'created_by': str(snapshot.created_by) if snapshot.created_by else '',
        'created_at': snapshot.created_at.isoformat(),
    }
    if include_entries:
        d['entries'] = [
            {
                'id': e.id,
                'work_id': e.work_id,
                'data': e.data,
            }
            for e in snapshot.entries.all()
        ]
    return d


class BaselineListView(LoginRequiredJsonMixin, View):
    """GET/POST /api/enterprise/cross/<project_id>/baselines/"""

    def get(self, request, project_id):
        try:
            cs = CrossSchedule.objects.get(project_id=project_id)
        except CrossSchedule.DoesNotExist:
            return JsonResponse({'error': 'Сквозной график не найден'}, status=404)

        snapshots = cs.baselines.select_related('created_by').order_by('-version')
        return JsonResponse({
            'baselines': [_serialize_baseline(s) for s in snapshots],
        })

    def post(self, request, project_id):
        """Создать снимок текущего состояния сквозного графика."""
        employee = getattr(request.user, 'employee', None)
        if not employee or not employee.is_writer:
            return JsonResponse({'error': 'Нет прав'}, status=403)

        data = parse_json_body(request) or {}

        with transaction.atomic():
            try:
                cs = CrossSchedule.objects.select_for_update().get(
                    project_id=project_id,
                )
            except CrossSchedule.DoesNotExist:
                return JsonResponse(
                    {'error': 'Сквозной график не найден'}, status=404,
                )

            # Атомарный инкремент версии
            last_version = cs.baselines.order_by('-version').values_list(
                'version', flat=True,
            ).first() or 0
            new_version = last_version + 1

            snapshot = BaselineSnapshot.objects.create(
                cross_schedule=cs,
                version=new_version,
                comment=(data.get('comment') or '').strip(),
                created_by=employee,
            )

            # Сохраняем данные работ, привязанных к этапам графика
            stage_ids = cs.stages.values_list('id', flat=True)
            works = Work.objects.filter(cross_stage_id__in=stage_ids)
            entries = []
            for w in works:
                entries.append(BaselineEntry(
                    snapshot=snapshot,
                    work=w,
                    data={
                        'name': w.name or '',
                        'labor': float(w.labor) if w.labor else None,
                        'date_start': str(w.date_start) if w.date_start else None,
                        'date_end': str(w.date_end) if w.date_end else None,
                        'cross_stage_id': w.cross_stage_id,
                        'status': w.status or '',
                    },
                ))
            if entries:
                BaselineEntry.objects.bulk_create(entries)

            cs.version = new_version
            cs.save(update_fields=['version'])

        return JsonResponse({
            'ok': True,
            'baseline': _serialize_baseline(snapshot),
        }, status=201)


class BaselineDetailView(LoginRequiredJsonMixin, View):
    """GET/DELETE /api/enterprise/baselines/<id>/"""

    def get(self, request, pk):
        try:
            snapshot = BaselineSnapshot.objects.select_related('created_by').get(pk=pk)
        except BaselineSnapshot.DoesNotExist:
            return JsonResponse({'error': 'Снимок не найден'}, status=404)
        return JsonResponse({
            'baseline': _serialize_baseline(snapshot, include_entries=True),
        })

    def delete(self, request, pk):
        employee = getattr(request.user, 'employee', None)
        if not employee or not employee.is_writer:
            return JsonResponse({'error': 'Нет прав'}, status=403)

        try:
            snapshot = BaselineSnapshot.objects.get(pk=pk)
        except BaselineSnapshot.DoesNotExist:
            return JsonResponse({'error': 'Снимок не найден'}, status=404)
        snapshot.delete()
        return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
#  Scenarios (что-если)
# ---------------------------------------------------------------------------

def _serialize_scenario(sc, include_entries=False):
    d = {
        'id': sc.id,
        'name': sc.name,
        'project_id': sc.project_id,
        'status': sc.status,
        'created_by': str(sc.created_by) if sc.created_by else '',
        'created_at': sc.created_at.isoformat(),
        'updated_at': sc.updated_at.isoformat(),
    }
    if include_entries:
        d['entries'] = [
            {
                'id': e.id,
                'work_id': e.work_id,
                'data': e.data,
            }
            for e in sc.entries.all()
        ]
    return d


class ScenarioListView(LoginRequiredJsonMixin, View):
    """GET/POST /api/enterprise/scenarios/"""

    def get(self, request):
        qs = Scenario.objects.select_related('project', 'created_by').order_by('-created_at')

        project_id = request.GET.get('project_id')
        if project_id:
            qs = qs.filter(project_id=project_id)

        status = request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        return JsonResponse({
            'scenarios': [_serialize_scenario(s) for s in qs],
        })

    def post(self, request):
        employee = getattr(request.user, 'employee', None)
        if not employee or not employee.is_writer:
            return JsonResponse({'error': 'Нет прав'}, status=403)

        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        name = (data.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'Название обязательно'}, status=400)

        project_id = data.get('project_id')
        if project_id and not Project.objects.filter(pk=project_id).exists():
            return JsonResponse({'error': 'Проект не найден'}, status=404)

        sc = Scenario.objects.create(
            name=name,
            project_id=project_id,
            created_by=employee,
            status=data.get('status', 'draft'),
        )
        return JsonResponse({
            'ok': True,
            'scenario': _serialize_scenario(sc),
        }, status=201)


class ScenarioDetailView(LoginRequiredJsonMixin, View):
    """GET/PUT/DELETE /api/enterprise/scenarios/<id>/"""

    def get(self, request, pk):
        try:
            sc = Scenario.objects.select_related('project', 'created_by').get(pk=pk)
        except Scenario.DoesNotExist:
            return JsonResponse({'error': 'Сценарий не найден'}, status=404)
        return JsonResponse({
            'scenario': _serialize_scenario(sc, include_entries=True),
        })

    def put(self, request, pk):
        employee = getattr(request.user, 'employee', None)
        if not employee or not employee.is_writer:
            return JsonResponse({'error': 'Нет прав'}, status=403)

        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            sc = Scenario.objects.get(pk=pk)
        except Scenario.DoesNotExist:
            return JsonResponse({'error': 'Сценарий не найден'}, status=404)

        FIELDS = ('name', 'status', 'project_id')
        update_fields = []
        for f in FIELDS:
            if f in data:
                if f == 'status':
                    valid = [c[0] for c in Scenario.STATUS_CHOICES]
                    if data[f] not in valid:
                        return JsonResponse(
                            {'error': f'Недопустимый статус: {data[f]}'}, status=400,
                        )
                setattr(sc, f, data[f])
                update_fields.append(f)

        if update_fields:
            sc.save(update_fields=update_fields)

        return JsonResponse({'ok': True, 'scenario': _serialize_scenario(sc)})

    def delete(self, request, pk):
        employee = getattr(request.user, 'employee', None)
        if not employee or not employee.is_writer:
            return JsonResponse({'error': 'Нет прав'}, status=403)

        try:
            sc = Scenario.objects.get(pk=pk)
        except Scenario.DoesNotExist:
            return JsonResponse({'error': 'Сценарий не найден'}, status=404)
        sc.delete()
        return JsonResponse({'ok': True})


class ScenarioEntryCreateView(WriterRequiredJsonMixin, View):
    """POST /api/enterprise/scenarios/<id>/entries/"""

    def post(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            sc = Scenario.objects.get(pk=pk)
        except Scenario.DoesNotExist:
            return JsonResponse({'error': 'Сценарий не найден'}, status=404)

        entry_data = data.get('data', {})
        work_id = data.get('work_id')
        if work_id and not Work.objects.filter(pk=work_id).exists():
            return JsonResponse({'error': 'Работа не найдена'}, status=404)

        entry = ScenarioEntry.objects.create(
            scenario=sc,
            work_id=work_id,
            data=entry_data,
        )
        return JsonResponse({
            'ok': True,
            'entry': {
                'id': entry.id,
                'work_id': entry.work_id,
                'data': entry.data,
            },
        }, status=201)
