"""
API зависимостей задач (TaskDependency).

Endpoints:
  GET    /api/tasks/<id>/dependencies/   — список зависимостей задачи
  POST   /api/tasks/<id>/dependencies/   — создание зависимости
  PUT    /api/dependencies/<id>/         — обновление зависимости
  DELETE /api/dependencies/<id>/         — удаление зависимости
  GET    /api/dependencies/              — все зависимости (для Ганта)
  POST   /api/tasks/<id>/align_dates/    — выравнивание дат по зависимостям
"""

import logging
from collections import defaultdict, deque
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.audit import log_action
from apps.api.drf_utils import IsWriterPermission
from apps.api.utils import get_visibility_filter
from apps.works.models import AuditLog, Holiday, TaskDependency, Work

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _detect_cycle(successor_id, predecessor_id):
    """
    Определяет, создаст ли связь predecessor→successor цикл.
    BFS от successor_id через successor_links: если достигнем predecessor_id — цикл.
    Все рёбра загружаются одним запросом для O(1) доступа.
    """
    # Предзагрузка всего графа зависимостей одним запросом
    graph = defaultdict(list)
    for pred_id, succ_id in TaskDependency.objects.values_list(
        "predecessor_id", "successor_id"
    ):
        graph[pred_id].append(succ_id)

    visited = set()
    queue = deque([successor_id])
    while queue:
        current = queue.popleft()
        if current == predecessor_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        queue.extend(graph.get(current, []))
    return False


def _dep_has_conflict(dep, successor):
    """Проверяет конфликт дат для одной зависимости."""
    pred = dep.predecessor
    ref_date = _get_reference_date(dep, pred)
    if ref_date is None:
        return False
    required_date = _add_work_days(ref_date, dep.lag_days)
    if dep.dep_type in ("FS", "SS"):
        actual_date = successor.date_start
    else:
        actual_date = successor.date_end
    if actual_date is None:
        return False
    return actual_date < required_date


def _serialize_dep_predecessor(dep, successor=None):
    """Сериализует зависимость с точки зрения предшественника."""
    pred = dep.predecessor
    conflict = _dep_has_conflict(dep, successor) if successor else False
    return {
        "id": dep.id,
        "work_id": pred.id,
        "work_name": pred.work_name or "",
        "work_num": pred.work_num or "",
        "dep_type": dep.dep_type,
        "lag_days": dep.lag_days,
        "date_start": pred.date_start.isoformat() if pred.date_start else "",
        "date_end": pred.date_end.isoformat() if pred.date_end else "",
        "from_pp": pred.show_in_pp,
        "conflict": conflict,
    }


def _serialize_dep_successor(dep):
    """Сериализует зависимость с точки зрения последователя."""
    succ = dep.successor
    conflict = _dep_has_conflict(dep, succ)
    return {
        "id": dep.id,
        "work_id": succ.id,
        "work_name": succ.work_name or "",
        "work_num": succ.work_num or "",
        "dep_type": dep.dep_type,
        "lag_days": dep.lag_days,
        "date_start": succ.date_start.isoformat() if succ.date_start else "",
        "date_end": succ.date_end.isoformat() if succ.date_end else "",
        "from_pp": succ.show_in_pp,
        "conflict": conflict,
    }


def _get_reference_date(dep, pred):
    """Возвращает опорную дату предшественника по типу связи."""
    if dep.dep_type in ("FS", "FF"):
        return pred.date_end
    elif dep.dep_type in ("SS", "SF"):
        return pred.date_start
    return pred.date_end


_holiday_cache = None


def _get_holidays():
    """Возвращает set дат-праздников (кешируется на запрос)."""
    global _holiday_cache
    if _holiday_cache is None:
        _holiday_cache = set(Holiday.objects.values_list("date", flat=True))
    return _holiday_cache


def invalidate_holiday_cache():
    """Сбросить кеш праздников (вызывать при изменении Holiday)."""
    global _holiday_cache
    _holiday_cache = None


def _add_work_days(start_date, days):
    """
    Прибавляет N рабочих дней к дате.
    Рабочий день = пн-пт и не праздник (из таблицы work_holiday).
    Положительные days — вперёд, отрицательные — назад, 0 — та же дата.
    """
    if days == 0:
        return start_date
    holidays = _get_holidays()
    direction = 1 if days > 0 else -1
    remaining = abs(days)
    current = start_date
    while remaining > 0:
        current += timedelta(days=direction)
        # Пн=0 .. Вс=6; рабочие дни = 0..4 и не праздник
        if current.weekday() < 5 and current not in holidays:
            remaining -= 1
    return current


def _check_date_conflict(successor, predecessors_qs):
    """
    Проверяет, есть ли конфликт дат текущей задачи (successor)
    с её предшественниками.

    Конфликт определяется по типу связи:
    - FS: successor.date_start < pred.date_end + lag (рабочих дней)
    - SS: successor.date_start < pred.date_start + lag
    - FF: successor.date_end   < pred.date_end + lag
    - SF: successor.date_end   < pred.date_start + lag

    Возвращает True если хотя бы одно ограничение нарушено.
    """
    for dep in predecessors_qs:
        pred = dep.predecessor
        ref_date = _get_reference_date(dep, pred)
        if ref_date is None:
            continue

        # Опорная дата предшественника + лаг (рабочие дни)
        required_date = _add_work_days(ref_date, dep.lag_days)

        # Дата текущей задачи для сравнения зависит от типа
        if dep.dep_type in ("FS", "SS"):
            actual_date = successor.date_start
        else:  # FF, SF
            actual_date = successor.date_end

        if actual_date is None:
            # Если дата не задана — считаем конфликтом
            continue

        if actual_date < required_date:
            return True

    return False


# ── Views ────────────────────────────────────────────────────────────────────


class TaskDependencyListView(APIView):
    """GET/POST /api/tasks/<pk>/dependencies/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """Список зависимостей задачи (предшественники + последователи)."""
        try:
            vis_q = get_visibility_filter(request.user)
            work = (
                Work.objects.filter(pk=pk)
                .filter(
                    Q(show_in_plan=True) | Q(show_in_pp=True),
                )
                .filter(vis_q)
                .first()
            )
            if not work:
                return Response({"error": "Задача не найдена"}, status=404)

            predecessors = TaskDependency.objects.filter(
                successor_id=pk,
            ).select_related("predecessor")
            successors = TaskDependency.objects.filter(
                predecessor_id=pk,
            ).select_related("successor")

            # Проверка конфликта дат (строгая, рабочие дни пн-пт)
            has_pred_conflict = _check_date_conflict(work, predecessors)
            pred_list = [
                _serialize_dep_predecessor(d, successor=work) for d in predecessors
            ]
            succ_list = [_serialize_dep_successor(d) for d in successors]
            has_succ_conflict = any(s["conflict"] for s in succ_list)

            return Response(
                {
                    "predecessors": pred_list,
                    "successors": succ_list,
                    "has_conflict": has_pred_conflict or has_succ_conflict,
                    "has_pred_conflict": has_pred_conflict,
                    "has_succ_conflict": has_succ_conflict,
                }
            )
        except Exception as e:
            logger.error("TaskDependencyListView.get error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def post(self, request, pk):
        """Создание зависимости. pk = successor_id."""
        # Проверка прав записи
        employee = getattr(request.user, "employee", None)
        if not employee or not employee.is_writer:
            return Response({"error": "Нет прав на изменение"}, status=403)

        try:
            d = request.data
            if not isinstance(d, dict):
                return Response({"error": "Невалидный JSON"}, status=400)
            if not d:
                return Response({"error": "Пустое тело запроса"}, status=400)

            predecessor_id = d.get("predecessor_id")
            dep_type = d.get("dep_type", "FS")
            lag_days = int(d.get("lag_days", 0))

            if not predecessor_id:
                return Response({"error": "predecessor_id обязателен"}, status=400)
            if dep_type not in ("FS", "SS", "FF", "SF"):
                return Response(
                    {"error": f"Недопустимый тип связи: {dep_type}"}, status=400
                )

            predecessor_id = int(predecessor_id)
            if predecessor_id == pk:
                return Response(
                    {"error": "Задача не может зависеть от самой себя"}, status=400
                )

            # Ограничение lag_days: -365..365 рабочих дней
            if lag_days < -365 or lag_days > 365:
                return Response(
                    {"error": "lag_days должен быть от -365 до 365"}, status=400
                )

            # Все проверки и создание внутри транзакции (TOCTOU защита)
            with transaction.atomic():
                # Проверка существования обеих задач
                plan_or_pp = Q(show_in_plan=True) | Q(show_in_pp=True)
                if not Work.objects.filter(pk=pk).filter(plan_or_pp).exists():
                    return Response(
                        {"error": "Задача-последователь не найдена"}, status=404
                    )
                if (
                    not Work.objects.filter(pk=predecessor_id)
                    .filter(plan_or_pp)
                    .exists()
                ):
                    return Response(
                        {"error": "Задача-предшественник не найдена"}, status=404
                    )

                # Проверка дубликата
                if TaskDependency.objects.filter(
                    predecessor_id=predecessor_id,
                    successor_id=pk,
                ).exists():
                    return Response(
                        {"error": "Такая зависимость уже существует"}, status=400
                    )

                # Проверка цикла
                if _detect_cycle(pk, predecessor_id):
                    return Response(
                        {"error": "Невозможно создать зависимость: обнаружен цикл"},
                        status=400,
                    )

                dep = TaskDependency.objects.create(
                    predecessor_id=predecessor_id,
                    successor_id=pk,
                    dep_type=dep_type,
                    lag_days=lag_days,
                )

            log_action(
                request,
                AuditLog.ACTION_DEP_CREATE,
                object_id=dep.id,
                object_repr=f"{predecessor_id} → {pk} ({dep_type})",
            )

            return Response({"id": dep.id})
        except (ValueError, TypeError) as e:
            return Response({"error": f"Некорректные данные: {e}"}, status=400)
        except Exception as e:
            logger.error("TaskDependencyListView.post error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)


class TaskDependencyDetailView(APIView):
    """PUT/DELETE /api/dependencies/<pk>/"""

    permission_classes = [IsWriterPermission]

    def put(self, request, pk):
        """Обновление зависимости (тип связи, лаг)."""
        try:
            d = request.data
            if not isinstance(d, dict):
                return Response({"error": "Невалидный JSON"}, status=400)
            try:
                dep = TaskDependency.objects.get(pk=pk)
            except TaskDependency.DoesNotExist:
                return Response({"error": "Зависимость не найдена"}, status=404)

            if "dep_type" in d:
                if d["dep_type"] not in ("FS", "SS", "FF", "SF"):
                    return Response({"error": "Недопустимый тип связи"}, status=400)
                dep.dep_type = d["dep_type"]
            if "lag_days" in d:
                try:
                    new_lag = int(d["lag_days"])
                except (ValueError, TypeError):
                    return Response(
                        {"error": "lag_days должен быть целым числом"}, status=400
                    )
                if new_lag < -365 or new_lag > 365:
                    return Response(
                        {"error": "lag_days должен быть от -365 до 365"}, status=400
                    )
                dep.lag_days = new_lag

            dep.save()

            log_action(
                request,
                AuditLog.ACTION_DEP_UPDATE,
                object_id=dep.id,
                object_repr=f"{dep.predecessor_id} → {dep.successor_id} ({dep.dep_type})",
            )

            return Response({"ok": True})
        except Exception as e:
            logger.error("TaskDependencyDetailView.put error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def delete(self, request, pk):
        """Удаление зависимости."""
        try:
            try:
                dep = TaskDependency.objects.get(pk=pk)
            except TaskDependency.DoesNotExist:
                return Response({"error": "Зависимость не найдена"}, status=404)

            log_action(
                request,
                AuditLog.ACTION_DEP_DELETE,
                object_id=dep.id,
                object_repr=f"{dep.predecessor_id} → {dep.successor_id}",
            )
            dep.delete()
            return Response({"ok": True})
        except Exception as e:
            logger.error("TaskDependencyDetailView.delete error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)


class AllDependenciesView(APIView):
    """GET /api/dependencies/ — все зависимости (для Ганта)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            context = request.GET.get("context", "plan")
            project_id = request.GET.get("project_id")
            if project_id:
                try:
                    project_id = int(project_id)
                except (ValueError, TypeError):
                    return Response(
                        {"error": "project_id должен быть числом"}, status=400
                    )

            if context == "pp" and project_id:
                work_ids = Work.objects.filter(
                    show_in_pp=True,
                    pp_project_id=project_id,
                ).values_list("id", flat=True)
            else:
                vis_q = get_visibility_filter(request.user)
                work_ids = (
                    Work.objects.filter(
                        show_in_plan=True,
                    )
                    .filter(vis_q)
                    .values_list("id", flat=True)
                )

            deps = TaskDependency.objects.filter(
                predecessor_id__in=work_ids,
                successor_id__in=work_ids,
            )

            return Response(
                [
                    {
                        "id": d.id,
                        "source": d.predecessor_id,
                        "target": d.successor_id,
                        "type": d.dep_type,
                        "lag": d.lag_days,
                    }
                    for d in deps
                ],
            )
        except Exception as e:
            logger.error("AllDependenciesView.get error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)


class AlignDatesView(APIView):
    """POST /api/tasks/<pk>/align_dates/ — каскадное выравнивание дат."""

    permission_classes = [IsWriterPermission]

    def post(self, request, pk):
        try:
            d = request.data if isinstance(request.data, dict) else {}
            cascade = d.get("cascade", False)

            vis_q = get_visibility_filter(request.user)
            work = Work.objects.filter(pk=pk).filter(vis_q).first()
            if not work:
                return Response({"error": "Задача не найдена"}, status=404)

            # PP-задачи нельзя выравнивать
            if work.show_in_pp and not work.show_in_plan:
                return Response(
                    {"error": "Нельзя выравнивать даты записи ПП"},
                    status=400,
                )

            predecessors = TaskDependency.objects.filter(
                successor_id=pk,
            ).select_related("predecessor")

            has_predecessors = predecessors.exists()

            # Если нет предшественников и не каскад — нечего выравнивать
            if not has_predecessors and not cascade:
                return Response(
                    {"error": "Нет предшественников для выравнивания"},
                    status=400,
                )

            # Если cascade=true но нет предшественников — только каскад
            # на последователей (текущую задачу не трогаем)
            if not has_predecessors and cascade:
                successors_exist = TaskDependency.objects.filter(
                    predecessor_id=pk,
                ).exists()
                if not successors_exist:
                    return Response(
                        {"error": "Нет связей для выравнивания"},
                        status=400,
                    )
                with transaction.atomic():
                    aligned_ids = self._cascade_align(request, pk)
                return Response(
                    {
                        "ok": True,
                        "new_date_start": (
                            work.date_start.isoformat() if work.date_start else ""
                        ),
                        "new_date_end": (
                            work.date_end.isoformat() if work.date_end else ""
                        ),
                        "aligned_count": len(aligned_ids),
                    }
                )

            # Определяем самую позднюю дату начала по всем предшественникам
            # (задача не может начаться раньше, чем завершится последний предшественник)
            latest_start = None
            for dep in predecessors:
                pred = dep.predecessor
                ref_date = _get_reference_date(dep, pred)
                if ref_date is None:
                    continue
                candidate = _add_work_days(ref_date, dep.lag_days)
                if latest_start is None or candidate > latest_start:
                    latest_start = candidate

            if latest_start is None:
                return Response(
                    {"error": "Невозможно определить дату: у предшественников нет дат"},
                    status=400,
                )

            with transaction.atomic():
                # Блокируем строку для предотвращения гонки при параллельных запросах
                work = Work.objects.select_for_update().get(pk=pk)
                changes = {"date_start": latest_start.isoformat()}
                if work.date_start and work.date_end:
                    duration = (work.date_end - work.date_start).days
                    new_end = latest_start + timedelta(days=duration)
                    changes["date_end"] = new_end.isoformat()
                    work.date_end = new_end
                work.date_start = latest_start
                work.save(update_fields=["date_start", "date_end", "updated_at"])

                log_action(
                    request,
                    AuditLog.ACTION_DEP_ALIGN,
                    object_id=work.id,
                    object_repr=work.work_name,
                    details=changes,
                )

                aligned_ids = [pk]
                if cascade:
                    aligned_ids.extend(
                        self._cascade_align(request, pk),
                    )

            return Response(
                {
                    "ok": True,
                    "new_date_start": (
                        work.date_start.isoformat() if work.date_start else ""
                    ),
                    "new_date_end": work.date_end.isoformat() if work.date_end else "",
                    "aligned_count": len(aligned_ids),
                }
            )
        except Exception as e:
            logger.error("AlignDatesView error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def _cascade_align(self, request, work_id, visited=None):
        """Рекурсивно выравнивает последователей."""
        if visited is None:
            visited = set()
        if work_id in visited:
            return []
        visited.add(work_id)

        aligned = []
        successors = TaskDependency.objects.filter(
            predecessor_id=work_id,
        ).select_related("successor")

        for dep in successors:
            succ = dep.successor

            all_pred_deps = TaskDependency.objects.filter(
                successor_id=succ.id,
            ).select_related("predecessor")

            earliest = None
            for pd in all_pred_deps:
                ref = _get_reference_date(pd, pd.predecessor)
                if ref is None:
                    continue
                candidate = _add_work_days(ref, pd.lag_days)
                if earliest is None or candidate > earliest:
                    earliest = candidate

            if earliest and succ.date_start != earliest:
                # Блокируем строку для предотвращения гонки
                succ = Work.objects.select_for_update().get(pk=succ.pk)
                if succ.date_start and succ.date_end:
                    duration = (succ.date_end - succ.date_start).days
                    succ.date_end = earliest + timedelta(days=duration)
                succ.date_start = earliest
                succ.save(update_fields=["date_start", "date_end", "updated_at"])

                log_action(
                    request,
                    AuditLog.ACTION_DEP_ALIGN,
                    object_id=succ.id,
                    object_repr=succ.work_name,
                    details={
                        "date_start": earliest.isoformat(),
                        "cascade": True,
                    },
                )

                aligned.append(succ.id)
                aligned.extend(self._cascade_align(request, succ.id, visited))

        return aligned
