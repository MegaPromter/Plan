"""
API для журнала извещений (Notice).

CRUD-операции над таблицей Notice.
GET     /api/journal          -- список записей журнала
POST    /api/journal/create   -- создание записи (writer, ручной ввод)
PUT     /api/journal/<id>     -- обновление записи (writer)
DELETE  /api/journal/<id>     -- удаление записи (writer, только ручные)
"""

import logging
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.api.utils import resolve_employee_loose, safe_date
from apps.employees.models import Department, Sector
from apps.works.models import Notice

logger = logging.getLogger(__name__)


def _check_journal_access(user, notice):
    """Проверка: writer может менять только записи своего отдела.
    admin / ntc_head / ntc_deputy — без ограничений.
    Возвращает строку ошибки или None (доступ разрешён)."""
    employee = getattr(user, "employee", None)
    if not employee:
        return "Нет профиля сотрудника"
    if employee.role in ("admin", "ntc_head", "ntc_deputy"):
        return None
    if not employee.department:
        return "Вашему профилю не назначен отдел"
    # Определяем отдел записи
    if notice.is_auto:
        work = notice.work_report.work if notice.work_report else None
        dept_id = work.department_id if work else None
    else:
        dept_id = notice.department_id
    if not dept_id:
        return "Не удалось определить отдел записи"
    if employee.department_id != dept_id:
        return "Вы можете редактировать только записи своего отдела"
    return None


# _safe_date → вынесена в apps.api.utils (safe_date)
_safe_date = safe_date


def _serialize_notice(n):
    """Гибридная сериализация: автоматические записи читают из WorkReport/Work,
    ручные — из собственных полей Notice."""
    if n.work_report_id:
        wr = n.work_report
        w = wr.work if wr else None
        ii_pi = (wr.ii_pi or "") if wr else ""
        notice_number = (wr.doc_number or "") if wr else ""
        date_issued = (
            (wr.date_accepted.isoformat() if wr.date_accepted else "") if wr else ""
        )
        date_expires = (
            (wr.date_expires.isoformat() if wr.date_expires else "") if wr else ""
        )
        subject = w.work_name if w else ""
        doc_designation = w.work_designation if w else ""
        dept = w.department.code if w and w.department else ""
        dept_name = w.department.name if w and w.department else ""
        sector = w.sector.name or w.sector.code if w and w.sector else ""
        executor = w.executor.full_name if w and w.executor else ""
    else:
        ii_pi = n.ii_pi or ""
        notice_number = n.notice_number or ""
        date_issued = n.date_issued.isoformat() if n.date_issued else ""
        date_expires = n.date_expires.isoformat() if n.date_expires else ""
        subject = n.subject or ""
        doc_designation = n.doc_designation or ""
        dept = n.department.code if n.department else ""
        dept_name = n.department.name if n.department else ""
        sector = (n.sector.name or n.sector.code) if n.sector else ""
        executor = n.executor.full_name if n.executor else ""

    # Определяем связанную задачу (work_id)
    if n.work_report_id:
        wr_local = n.work_report
        w_local = wr_local.work if wr_local else None
        work_id = w_local.pk if w_local else None
    else:
        work_id = None

    return {
        "id": n.pk,
        "is_auto": n.is_auto,
        "work_id": work_id,
        "task_id": work_id,  # алиас для совместимости
        "ii_pi": ii_pi,
        "notice_number": notice_number,
        "date_issued": date_issued,
        "date_expires": date_expires,
        "subject": subject,
        "doc_designation": doc_designation,
        "dept": dept,
        "dept_name": dept_name,
        "sector": sector,
        "executor": executor,
        "description": n.description or "",
        "status": n.computed_status,
        "status_raw": n.status,
        # Реквизиты погашения
        "closure_notice_number": n.closure_notice_number or "",
        "closure_date_issued": (
            n.closure_date_issued.isoformat() if n.closure_date_issued else ""
        ),
        "closure_executor": n.closure_executor or "",
    }


# Максимальное количество записей
JOURNAL_MAX = 5000

# Маппинг сортировки (ключ из JS → ORM-поле)
_SORT_MAP = {
    "ii_pi": "ii_pi",
    "notice_number": "notice_number",
    "subject": "subject",
    "doc_designation": "doc_designation",
    "date_issued": "effective_date",
    "date_expires": "date_expires",
    "dept": "dept_code_ann",
    "sector": "sector_name_ann",
    "executor": "executor_name_ann",
    "status": "status",
}


def _base_queryset():
    """Базовый queryset для журнала с аннотациями для сортировки."""
    from django.db.models import Value
    from django.db.models.functions import Coalesce

    return Notice.objects.select_related(
        "work_report",
        "work_report__work",
        "work_report__work__department",
        "work_report__work__sector",
        "work_report__work__executor",
        "department",
        "sector",
        "executor",
    ).annotate(
        effective_date=Coalesce(
            "date_issued",
            "work_report__date_accepted",
        ),
        # Аннотации для серверной сортировки (гибрид авто/ручных полей)
        dept_code_ann=Coalesce(
            "work_report__work__department__code",
            "department__code",
            Value(""),
        ),
        sector_name_ann=Coalesce(
            "work_report__work__sector__name",
            "work_report__work__sector__code",
            "sector__name",
            "sector__code",
            Value(""),
        ),
        executor_name_ann=Coalesce(
            "work_report__work__executor__last_name",
            "executor__last_name",
            Value(""),
        ),
    )


def _apply_mf_filters(qs, params):
    """Применяет мульти-фильтры из query string к queryset.
    Формат: mf_dept=021&mf_dept=022 → фильтр dept IN ('021','022')."""

    # ii_pi — гибрид (авто из work_report, ручное из notice)
    vals = params.getlist("mf_ii_pi")
    if vals:
        qs = qs.filter(
            Q(work_report__isnull=False, work_report__ii_pi__in=vals)
            | Q(work_report__isnull=True, ii_pi__in=vals)
        )

    # notice_number
    vals = params.getlist("mf_notice_number")
    if vals:
        qs = qs.filter(
            Q(work_report__isnull=False, work_report__doc_number__in=vals)
            | Q(work_report__isnull=True, notice_number__in=vals)
        )

    # subject
    vals = params.getlist("mf_subject")
    if vals:
        qs = qs.filter(
            Q(work_report__work__work_name__in=vals)
            | Q(work_report__isnull=True, subject__in=vals)
        )

    # doc_designation
    vals = params.getlist("mf_doc_designation")
    if vals:
        qs = qs.filter(
            Q(work_report__work__work_designation__in=vals)
            | Q(work_report__isnull=True, doc_designation__in=vals)
        )

    # dept
    vals = params.getlist("mf_dept")
    if vals:
        qs = qs.filter(
            Q(work_report__work__department__code__in=vals)
            | Q(work_report__isnull=True, department__code__in=vals)
        )

    # sector
    vals = params.getlist("mf_sector")
    if vals:
        qs = qs.filter(
            Q(work_report__work__sector__name__in=vals)
            | Q(work_report__work__sector__code__in=vals)
            | Q(work_report__isnull=True, sector__name__in=vals)
            | Q(work_report__isnull=True, sector__code__in=vals)
        )

    # executor
    vals = params.getlist("mf_executor")
    if vals:
        # executor — full_name (ФИО), фильтруем через аннотированное поле
        # Для точного совпадения нужно сравнивать с сериализованным именем
        # Простой подход: фильтр по last_name + icontains
        q = Q()
        for v in vals:
            q |= (
                (
                    Q(work_report__work__executor__last_name__startswith=v.split()[0])
                    | Q(executor__last_name__startswith=v.split()[0])
                )
                if " " in v
                else (
                    Q(work_report__work__executor__last_name=v)
                    | Q(executor__last_name=v)
                )
            )
        if q:
            qs = qs.filter(q)

    # date_issued (формат: YYYY-MM-DD или YYYY-MM)
    vals = params.getlist("mf_date_issued")
    if vals:
        q = Q()
        for v in vals:
            if len(v) == 7:  # YYYY-MM
                y, m = v.split("-")
                q |= Q(effective_date__year=int(y), effective_date__month=int(m))
            else:
                q |= Q(effective_date=v)
        qs = qs.filter(q)

    # date_expires
    vals = params.getlist("mf_date_expires")
    if vals:
        q = Q()
        for v in vals:
            if len(v) == 7:
                y, m = v.split("-")
                q |= Q(date_expires__year=int(y), date_expires__month=int(m))
            else:
                q |= Q(date_expires=v)
        qs = qs.filter(q)

    return qs


def _apply_status_filter(qs, status_filter):
    """Серверная фильтрация по статусу (включая computed_status)."""
    if not status_filter:
        return qs

    # Мульти-значения: status=active&status=expired
    if isinstance(status_filter, list):
        statuses = status_filter
    else:
        statuses = [status_filter]

    from django.utils import timezone

    today = timezone.now().date()

    q = Q()
    for s in statuses:
        if s in ("closed_yes", "closed_no"):
            q |= Q(status=s)
        elif s == "expired":
            q |= Q(status=Notice.STATUS_ACTIVE) & (
                Q(work_report__isnull=True, ii_pi="ПИ", date_expires__lt=today)
                | Q(
                    work_report__isnull=False,
                    work_report__ii_pi="ПИ",
                    work_report__date_expires__lt=today,
                )
            )
        elif s == "active":
            q |= Q(status=Notice.STATUS_ACTIVE) & ~(
                Q(work_report__isnull=True, ii_pi="ПИ", date_expires__lt=today)
                | Q(
                    work_report__isnull=False,
                    work_report__ii_pi="ПИ",
                    work_report__date_expires__lt=today,
                )
            )
    if q:
        qs = qs.filter(q)
    return qs


# ── GET /api/journal ──────────────────────────────────────────────────────────


class JournalListView(LoginRequiredJsonMixin, View):
    """GET -- список записей журнала с пагинацией, сортировкой и мульти-фильтрами."""

    def get(self, request):
        # Быстрая проверка существования по номеру и типу (для защиты от дублей)
        check_number = request.GET.get("check_number", "").strip()
        check_ii_pi = request.GET.get("check_ii_pi", "").strip()
        if check_number and check_ii_pi:
            exists = Notice.objects.filter(
                notice_number=check_number,
                ii_pi=check_ii_pi,
            ).exists()
            return JsonResponse({"exists": exists})

        # Пагинация
        try:
            limit = min(int(request.GET.get("limit", 50)), JOURNAL_MAX)
            offset = max(int(request.GET.get("offset", 0)), 0)
        except (ValueError, TypeError):
            limit, offset = 50, 0

        qs = _base_queryset()

        # Фильтр по отделу (базовый, из профиля)
        dept = request.GET.get("dept", "").strip()
        if dept:
            qs = qs.filter(
                Q(work_report__work__department__code=dept)
                | Q(work_report__isnull=True, department__code=dept)
            )

        # Мульти-фильтры
        qs = _apply_mf_filters(qs, request.GET)

        # Фильтр по статусу (поддерживает мульти-значения)
        status_vals = request.GET.getlist("mf_status")
        if status_vals:
            qs = _apply_status_filter(qs, status_vals)
        else:
            single_status = request.GET.get("status", "").strip()
            if single_status:
                qs = _apply_status_filter(qs, single_status)

        # Сортировка
        sort_param = request.GET.get("sort", "").strip()
        if sort_param:
            desc = sort_param.startswith("-")
            key = sort_param.lstrip("-")
            db_field = _SORT_MAP.get(key)
            if db_field:
                qs = qs.order_by(("-" + db_field) if desc else db_field)
            else:
                qs = qs.order_by("-effective_date", "-created_at")
        else:
            qs = qs.order_by("-effective_date", "-created_at")

        total = qs.count()
        result = [_serialize_notice(n) for n in qs[offset : offset + limit]]

        resp = JsonResponse(result, safe=False)
        resp["X-Total-Count"] = total
        resp["X-Has-More"] = "true" if (offset + limit) < total else "false"
        return resp


# ── GET /api/journal/facets ───────────────────────────────────────────────────


class JournalFacetsView(LoginRequiredJsonMixin, View):
    """GET -- уникальные значения для мульти-фильтров.
    Возвращает по каждой колонке список доступных значений."""

    def get(self, request):
        qs = _base_queryset()

        # Базовый фильтр по отделу
        dept = request.GET.get("dept", "").strip()
        if dept:
            qs = qs.filter(
                Q(work_report__work__department__code=dept)
                | Q(work_report__isnull=True, department__code=dept)
            )

        # Собираем уникальные значения через сериализацию
        # (для гибридных полей авто/ручных нужна Python-обработка)
        notices = list(qs[:JOURNAL_MAX])
        facets = {}
        for col in (
            "ii_pi",
            "notice_number",
            "subject",
            "doc_designation",
            "date_issued",
            "date_expires",
            "dept",
            "sector",
            "executor",
            "status",
        ):
            vals = set()
            for n in notices:
                s = _serialize_notice(n)
                v = s.get(col, "")
                if v:
                    vals.add(v)
            facets[col] = sorted(vals, key=lambda x: str(x))

        return JsonResponse(facets)


# ── POST /api/journal/create ──────────────────────────────────────────────────


class JournalCreateView(WriterRequiredJsonMixin, View):
    """POST -- создание записи журнала (ручной ввод, work_report=NULL)."""

    def post(self, request):
        try:
            return self._create(request)
        except Exception as e:
            logger.error("JournalCreateView error: %s", e, exc_info=True)
            return JsonResponse(
                {"error": "Внутренняя ошибка сервера"},
                status=500,
            )

    def _create(self, request):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)
        if not data:
            return JsonResponse({"error": "Пустое тело запроса"}, status=400)

        dept_code = (data.get("dept") or "").strip()
        sector_name = (data.get("sector") or "").strip()
        executor_name = (data.get("executor") or "").strip()

        if dept_code:
            try:
                department = Department.objects.get(code=dept_code)
            except Department.DoesNotExist:
                department = None
        else:
            department = None
        sector = None
        if sector_name and department:
            sector = Sector.objects.filter(
                department=department, name=sector_name
            ).first()
            if not sector:
                sector = Sector.objects.filter(name=sector_name).first()

        # Нестрогий поиск исполнителя по ФИО (ручной ввод — точное совпадение не критично)
        executor = resolve_employee_loose(executor_name) if executor_name else None

        # Серверная проверка дублей по номеру+типу (атомарно для защиты от race condition)
        nn = data.get("notice_number", "") or ""
        iip = data.get("ii_pi", "") or ""

        valid_statuses = {c[0] for c in Notice.STATUS_CHOICES}
        status = data.get("status", Notice.STATUS_ACTIVE)
        if status not in valid_statuses:
            status = Notice.STATUS_ACTIVE

        # Валидация: дата выпуска не может быть позже сегодня
        di = _safe_date(data.get("date_issued"))
        if di and di > date.today():
            return JsonResponse(
                {"error": "Дата выпуска не может быть позже текущей даты"}, status=400
            )

        try:
            with transaction.atomic():
                if (
                    nn
                    and iip
                    and Notice.objects.filter(notice_number=nn, ii_pi=iip).exists()
                ):
                    return JsonResponse(
                        {"error": f"Извещение {iip} № {nn} уже существует"}, status=409
                    )

                notice = Notice.objects.create(
                    notice_number=data.get("notice_number", "") or "",
                    ii_pi=data.get("ii_pi", "") or "",
                    notice_type=data.get("notice_type", "") or "",
                    group=data.get("group", "") or "",
                    doc_designation=data.get("doc_designation", "") or "",
                    department=department,
                    sector=sector,
                    executor=executor,
                    date_issued=di,
                    date_expires=_safe_date(data.get("date_expires")),
                    subject=data.get("subject", "") or "",
                    description=data.get("description", "") or "",
                    status=status,
                )
        except IntegrityError:
            return JsonResponse(
                {"error": f"Извещение {iip} № {nn} уже существует"}, status=409
            )

        return JsonResponse(
            {
                "id": notice.pk,
                "notice": _serialize_notice(
                    Notice.objects.select_related(
                        "department",
                        "sector",
                        "executor",
                    ).get(pk=notice.pk)
                ),
            },
            status=201,
        )


# ── PUT / DELETE /api/journal/<id> ────────────────────────────────────────────


class JournalDetailView(WriterRequiredJsonMixin, View):
    """PUT / DELETE -- обновление/удаление записи журнала."""

    def _get_notice(self, pk):
        try:
            return Notice.objects.select_related(
                "work_report",
                "work_report__work",
                "work_report__work__department",
                "work_report__work__sector",
                "work_report__work__executor",
                "department",
                "sector",
                "executor",
            ).get(pk=pk)
        except Notice.DoesNotExist:
            return None

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except Exception as e:
            logger.error("JournalDetailView.put error: %s", e, exc_info=True)
            return JsonResponse(
                {"error": "Внутренняя ошибка сервера"},
                status=500,
            )

    def _update(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)
        if not data:
            return JsonResponse({"ok": True})

        notice = self._get_notice(pk)
        if not notice:
            return JsonResponse({"error": "Запись не найдена"}, status=404)

        err = _check_journal_access(request.user, notice)
        if err:
            return JsonResponse({"error": err}, status=403)

        update_fields = []

        # --- Валидация погашения ---
        new_status = data.get("status", notice.status)
        if new_status in ("closed_yes", "closed_no"):
            cn = data.get("closure_notice_number", notice.closure_notice_number or "")
            cd = data.get("closure_date_issued") or (
                notice.closure_date_issued.isoformat()
                if notice.closure_date_issued
                else ""
            )
            ce = data.get("closure_executor", notice.closure_executor or "")
            if not cn or not cd or not ce:
                return JsonResponse(
                    {
                        "error": "Для погашения необходимы: "
                        "№ документа, дата и исполнитель",
                    },
                    status=400,
                )

        # --- Поля, доступные для всех записей ---
        if "description" in data:
            notice.description = data["description"] or ""
            update_fields.append("description")

        if "status" in data:
            val = data["status"]
            if val in {c[0] for c in Notice.STATUS_CHOICES}:
                notice.status = val
                update_fields.append("status")

        for f in ("closure_notice_number", "closure_executor"):
            if f in data:
                setattr(notice, f, data[f] or "")
                update_fields.append(f)

        if "closure_date_issued" in data:
            notice.closure_date_issued = _safe_date(data["closure_date_issued"])
            update_fields.append("closure_date_issued")

        # --- Поля ручного ввода (только для не-авто записей) ---
        if not notice.is_auto:
            for f in (
                "notice_number",
                "ii_pi",
                "notice_type",
                "group",
                "doc_designation",
                "subject",
                "description",
            ):
                if f in data and f not in update_fields:
                    setattr(notice, f, data[f] or "")
                    update_fields.append(f)

            if "dept" in data:
                dept_code = (data["dept"] or "").strip()
                if dept_code:
                    try:
                        notice.department = Department.objects.get(code=dept_code)
                    except Department.DoesNotExist:
                        notice.department = None
                else:
                    notice.department = None
                update_fields.append("department")

            if "sector" in data:
                sector_name = (data["sector"] or "").strip()
                sector = None
                if sector_name:
                    if notice.department:
                        sector = Sector.objects.filter(
                            department=notice.department,
                            name=sector_name,
                        ).first()
                    if not sector:
                        sector = Sector.objects.filter(
                            name=sector_name,
                        ).first()
                notice.sector = sector
                update_fields.append("sector")

            if "executor" in data:
                executor_name = (data["executor"] or "").strip()
                notice.executor = (
                    resolve_employee_loose(executor_name) if executor_name else None
                )
                update_fields.append("executor")

            if "date_issued" in data:
                di = _safe_date(data["date_issued"])
                if di and di > date.today():
                    return JsonResponse(
                        {"error": "Дата выпуска не может быть позже текущей даты"},
                        status=400,
                    )
                notice.date_issued = di
                update_fields.append("date_issued")

            if "date_expires" in data:
                notice.date_expires = _safe_date(data["date_expires"])
                update_fields.append("date_expires")

        if update_fields:
            notice.save(update_fields=update_fields + ["updated_at"])

        return JsonResponse({"ok": True})

    def delete(self, request, pk):
        try:
            return self._delete(request, pk)
        except Exception as e:
            logger.error("JournalDetailView.delete error: %s", e, exc_info=True)
            return JsonResponse(
                {"error": "Внутренняя ошибка сервера"},
                status=500,
            )

    def _delete(self, request, pk):
        notice = self._get_notice(pk)
        if not notice:
            return JsonResponse({"error": "Запись не найдена"}, status=404)

        if notice.is_auto:
            return JsonResponse(
                {"error": "Автоматические записи нельзя удалить вручную"},
                status=400,
            )

        err = _check_journal_access(request.user, notice)
        if err:
            return JsonResponse({"error": err}, status=403)

        notice.delete()
        return JsonResponse({"ok": True})
