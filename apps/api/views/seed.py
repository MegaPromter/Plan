"""
API для генерации тестовых данных (seed).

Все эндпоинты требуют роль admin.
POST /api/seed              -- генерация случайных задач (Work show_in_plan=True)
POST /api/seed_executors    -- добавление исполнителей в справочник + назначение
POST /api/seed_vacations    -- генерация случайных отпусков
POST /api/fill_all          -- заполнение всех справочников + обновление задач
POST /api/fill_dept         -- заполнение отделов + назначение задачам
"""

import logging
import random
from datetime import date, timedelta

from django.db import transaction
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import AdminRequiredJsonMixin, parse_json_body
from apps.employees.models import BusinessTrip, Department, Employee, Sector, Vacation
from apps.works.models import Directory, PPProject, Work, WorkCalendar

logger = logging.getLogger(__name__)


# ── Константы для генерации тестовых данных ──────────────────────────────────

SEED_NTC_CENTERS = [
    "НТЦ-1Ц",
    "НТЦ-2Ц",
    "НТЦ-3Ц",
    "НТЦ-4Ц",
    "НТЦ-7Ц",
    "НТЦ-8Ц",
    "НТЦ-11Ц",
    "НТЦ-13Ц",
    "НТЦ-14Ц",
]

SEED_POSITIONS = [
    "техник-конструктор",
    "техник-конструктор 2 кат.",
    "техник-конструктор 1 кат.",
    "специалист",
    "специалист 2 кат.",
    "специалист 1 кат.",
    "инженер-конструктор 3 кат.",
    "инженер-конструктор 2 кат.",
    "инженер-конструктор 1 кат.",
    "ведущий инженер-конструктор",
    "начальник сектора",
    "зам. начальника отдела",
    "начальник отдела",
    "руководитель направления",
    "зам. руководителя НТЦ",
    "руководитель НТЦ",
    "техник",
]

SEED_TASK_TYPES = [
    "Разработка",
    "Выпуск нового документа",
    "Корректировка документа",
    "Сопровождение (ОКАН)",
]

SEED_WORK_NAMES = [
    "Разработка технического задания",
    "Тестирование модуля",
    "Проектирование общего вида",
    "Разработка деталировки",
    "Корректировка документации",
    "Выпуск спецификации",
    "Разработка сборочного чертежа",
    "Согласование ТУ",
    "Проведение расчётов",
    "Подготовка отчёта",
    "Выпуск электрической схемы",
    "Анализ аналогов",
    "Разработка монтажного чертежа",
    "Составление ведомости",
    "Оформление пояснительной записки",
    "Выпуск габаритного чертежа",
    "Техническое сопровождение",
    "Авторский надзор",
    "Входной контроль",
    "Разработка программы испытаний",
]

SEED_JUSTIFICATIONS = [
    "В соответствии с планом НИР на 2026 год",
    "По заданию руководителя НТЦ",
    "Согласно техническому заданию",
    "В рамках ОКР по договору",
    "По результатам анализа несоответствий",
    "Плановая корректировка КД",
    "По решению технического совета",
]

SEED_DEPTS = [
    "021",
    "022",
    "024",
    "027",
    "028",
    "029",
    "301",
    "082",
    "084",
    "086",
]

# Секторы для каждого отдела (суффиксы)
_SECTOR_SUFFIXES = ("010", "110", "120")

# Проекты / стадии для seed_data
_SEED_PROJECTS = [
    "Проект Альфа",
    "Проект Бета",
    "Проект Гамма",
    "Проект Дельта",
    "Система Омега",
    "ОКР-2025",
    "НИР-11",
]

_SEED_STAGES = {
    "Проект Альфа": ["Анализ", "Проектирование", "Разработка"],
    "Проект Бета": ["Разработка", "Тестирование"],
    "Проект Гамма": ["Тестирование", "Сдача"],
    "Проект Дельта": ["Анализ", "Разработка", "Сдача"],
    "Система Омега": ["Проектирование", "Разработка", "Внедрение"],
    "ОКР-2025": ["Этап 1", "Этап 2", "Этап 3", "Завершение"],
    "НИР-11": ["Предварительный", "Основной", "Заключительный"],
}

_SEED_SECTORS = {
    "021": ["021-110", "021-120", "021-130"],
    "022": ["022-100", "022-200"],
    "024": ["024-010", "024-110"],
    "027": ["027-010", "027-110"],
    "028": ["028-010", "028-110"],
    "029": ["029-010", "029-110"],
    "301": ["301-010", "301-110"],
    "082": ["082-010", "082-110"],
    "084": ["084-010", "084-110"],
    "086": ["086-010", "086-110"],
}

_SEED_EXECUTORS = [
    "Иванов И.И.",
    "Петров П.П.",
    "Сидорова А.В.",
    "Козлов М.С.",
    "Новикова Е.А.",
    "Морозов Д.В.",
    "Лебедева О.Н.",
    "Соколов А.П.",
    "Попова Т.И.",
    "Волков К.Ю.",
]


# ── Утилиты ──────────────────────────────────────────────────────────────────


def _rand_plan_hours(ds, de):
    """Генерирует случайное распределение часов по месяцам между ds и de."""
    keys = []
    cur = date(ds.year, ds.month, 1)
    end_d = date(de.year, de.month, 1)
    while cur <= end_d:
        keys.append(f"{cur.year}-{cur.month:02d}")
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    if not keys:
        return {}
    total = random.randint(10, 200)
    ph = {}
    remaining = total
    for i, k in enumerate(keys):
        if i == len(keys) - 1:
            ph[k] = max(1, remaining)
        else:
            val = random.randint(1, max(1, remaining - (len(keys) - i - 1)))
            ph[k] = val
            remaining -= val
    return ph


def _get_or_create_dept(code):
    """Получить или создать Department по коду."""
    dept, _ = Department.objects.get_or_create(code=code, defaults={"name": ""})
    return dept


def _get_or_create_sector(dept, sector_code):
    """Получить или создать Sector по коду и отделу."""
    sector, _ = Sector.objects.get_or_create(
        department=dept,
        code=sector_code,
        defaults={"name": ""},
    )
    return sector


# ── POST /api/seed ──────────────────────────────────────────────────────────


class SeedDataView(AdminRequiredJsonMixin, View):
    """
    Генерация случайных задач (Work show_in_plan=True).
    Body: {count: 1-10000}
    """

    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)
        count = min(int(data.get("count", 1000)), 10_000)

        employee = getattr(request.user, "employee", None)
        # Кэшируем сотрудников для назначения executor FK
        employees = list(Employee.objects.all()[:200])

        created = 0
        with transaction.atomic():
            for _ in range(count):
                dept_code = random.choice(SEED_DEPTS)
                sectors = _SEED_SECTORS.get(dept_code, [f"{dept_code}-010"])
                sector_code = random.choice(sectors)
                project = random.choice(_SEED_PROJECTS)
                stage = random.choice(_SEED_STAGES.get(project, ["Этап 1"]))
                task_type_name = random.choice(SEED_TASK_TYPES)
                work_name = random.choice(SEED_WORK_NAMES)
                work_number = f"{random.randint(1, 99):02d}-{random.randint(100, 999)}"
                justification = random.choice(SEED_JUSTIFICATIONS)
                description = f"Описание: {work_name.lower()}"

                yr = random.choice([2025, 2026])
                ds = date(yr, 1, 1) + timedelta(days=random.randint(0, 330))
                de = ds + timedelta(days=random.randint(7, 90))
                deadline = de + timedelta(days=random.randint(0, 30))
                ph = _rand_plan_hours(ds, de)

                dept_obj = _get_or_create_dept(dept_code)
                sector_obj = _get_or_create_sector(dept_obj, sector_code)

                Work.objects.create(
                    show_in_plan=True,
                    task_type=task_type_name,
                    department=dept_obj,
                    sector=sector_obj,
                    executor=random.choice(employees) if employees else None,
                    work_name=work_name,
                    work_num=work_number,
                    work_designation=description,
                    date_start=ds,
                    date_end=de,
                    deadline=deadline,
                    plan_hours=ph,
                    stage_num=stage,
                    justification=justification,
                    created_by=employee,
                )

                created += 1

            # ── ПП-записи (show_in_pp=True) ──────────────────────────────
            pp_projects = list(PPProject.objects.all()[:100])
            pp_count = min(count // 2, 500)  # половина от SP, макс 500
            if pp_projects:
                for idx in range(pp_count):
                    dept_code = random.choice(SEED_DEPTS)
                    sectors = _SEED_SECTORS.get(dept_code, [f"{dept_code}-010"])
                    sector_code = random.choice(sectors)
                    task_type_name = random.choice(SEED_TASK_TYPES)
                    work_name = random.choice(SEED_WORK_NAMES)
                    work_number = (
                        f"{random.randint(1, 99):02d}-{random.randint(100, 999)}"
                    )

                    dept_obj = _get_or_create_dept(dept_code)
                    sector_obj = _get_or_create_sector(dept_obj, sector_code)

                    sheets = random.randint(1, 50)
                    norm_val = round(random.uniform(0.5, 5.0), 2)
                    coeff_val = round(random.uniform(0.8, 1.5), 3)

                    Work.objects.create(
                        show_in_pp=True,
                        pp_project=random.choice(pp_projects),
                        task_type=task_type_name,
                        department=dept_obj,
                        sector=sector_obj,
                        executor=random.choice(employees) if employees else None,
                        work_name=work_name,
                        work_num=work_number,
                        work_designation=f"АБВГ.{random.randint(100000, 999999)}.{random.randint(1, 99):03d}",
                        row_code=f"РС-{idx + 1:03d}",
                        stage_num=f"Этап {random.randint(1, 5)}",
                        sheets_a4=sheets,
                        norm=norm_val,
                        coeff=coeff_val,
                        labor=round(sheets * norm_val * coeff_val, 2),
                        created_by=employee,
                    )
                    created += 1

        return JsonResponse({"inserted": created})


# ── POST /api/seed_executors ────────────────────────────────────────────────


class SeedExecutorsView(AdminRequiredJsonMixin, View):
    """
    Добавление исполнителей в Directory(dir_type='executor')
    и назначение случайных исполнителей существующим задачам.
    Body: {executors: ["Иванов И.И.", ...]} (опционально)
    """

    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)
        executors_input = data.get("executors", _SEED_EXECUTORS)

        with transaction.atomic():
            existing = set(
                Directory.objects.filter(dir_type="executor").values_list(
                    "value", flat=True
                )
            )

            new_names = [n for n in executors_input if n not in existing]
            if new_names:
                Directory.objects.bulk_create(
                    [Directory(dir_type="executor", value=name) for name in new_names]
                )

            all_exec = sorted(existing | set(new_names))

            if not all_exec:
                return JsonResponse(
                    {
                        "added_executors": 0,
                        "total_executors": 0,
                        "tasks_updated": 0,
                    }
                )

            # Назначаем случайных сотрудников (Employee FK) существующим задачам
            employees = list(Employee.objects.all()[:200])
            task_works = list(Work.objects.filter(show_in_plan=True)[:10_000])

            updated = 0
            if employees:
                for work in task_works:
                    work.executor = random.choice(employees)
                    updated += 1

                Work.objects.bulk_update(
                    task_works,
                    ["executor"],
                    batch_size=1000,
                )

        return JsonResponse(
            {
                "added_executors": len(new_names),
                "total_executors": len(all_exec),
                "tasks_updated": updated,
            }
        )


# ── POST /api/seed_vacations ────────────────────────────────────────────────


class SeedVacationsView(AdminRequiredJsonMixin, View):
    """
    Генерация случайных отпусков для существующих исполнителей.
    Берёт уникальных исполнителей из задач, создаёт Vacation.
    """

    def post(self, request):
        with transaction.atomic():
            # Берём сотрудников, назначенных исполнителями задач
            executor_ids = list(
                Work.objects.filter(show_in_plan=True, executor__isnull=False)
                .values_list("executor_id", flat=True)
                .distinct()[:200]
            )
            executor_names = (
                list(
                    Employee.objects.filter(pk__in=executor_ids).values_list(
                        "last_name", flat=True
                    )
                )
                if executor_ids
                else []
            )

            if not executor_names:
                executor_names = list(
                    Directory.objects.filter(dir_type="executor").values_list(
                        "value", flat=True
                    )[:200]
                )

            if not executor_names:
                return JsonResponse({"created": 0, "executors": 0})

            year = date.today().year
            created = 0

            for name in executor_names:
                parts = name.split()
                last_name = parts[0] if parts else name
                first_name = parts[1] if len(parts) > 1 else ""

                emp_qs = Employee.objects.filter(last_name__iexact=last_name)
                if first_name:
                    emp_qs = emp_qs.filter(first_name__istartswith=first_name[:1])
                emp = emp_qs.first()

                if not emp:
                    continue

                start_day = random.randint(1, 330)
                d_start = date(year, 1, 1) + timedelta(days=start_day)
                d_end = d_start + timedelta(days=random.randint(14, 28))

                Vacation.objects.create(
                    employee=emp,
                    vac_type=Vacation.TYPE_ANNUAL,
                    date_start=d_start,
                    date_end=d_end,
                    notes="Ежегодный оплачиваемый",
                )
                created += 1

        return JsonResponse(
            {
                "created": created,
                "executors": len(executor_names),
            }
        )


# ── POST /api/fill_all ──────────────────────────────────────────────────────


class FillAllView(AdminRequiredJsonMixin, View):
    """
    Заполнение всех справочников (Directory) и обновление существующих задач
    случайными данными из справочников.
    """

    def post(self, request):
        with transaction.atomic():
            # ── 1. Заполняем справочники ──────────────────────────────────────

            existing_depts = set(
                Directory.objects.filter(dir_type="dept").values_list(
                    "value", flat=True
                )
            )
            for d in SEED_DEPTS:
                if d not in existing_depts:
                    Directory.objects.create(dir_type="dept", value=d)

            dept_entries = {
                e.value: e for e in Directory.objects.filter(dir_type="dept")
            }

            existing_sectors = set(
                Directory.objects.filter(dir_type="sector").values_list(
                    "value", flat=True
                )
            )
            for dept_val, dept_entry in dept_entries.items():
                for suffix in _SECTOR_SUFFIXES:
                    sector_val = f"{dept_val}-{suffix}"
                    if sector_val not in existing_sectors:
                        Directory.objects.create(
                            dir_type="sector",
                            value=sector_val,
                            parent=dept_entry,
                        )

            existing_centers = set(
                Directory.objects.filter(dir_type="center").values_list(
                    "value", flat=True
                )
            )
            for c in SEED_NTC_CENTERS:
                if c not in existing_centers:
                    Directory.objects.create(dir_type="center", value=c)

            existing_positions = set(
                Directory.objects.filter(dir_type="position").values_list(
                    "value", flat=True
                )
            )
            for p in SEED_POSITIONS:
                if p not in existing_positions:
                    Directory.objects.create(dir_type="position", value=p)

            existing_task_types = set(
                Directory.objects.filter(dir_type="task_type").values_list(
                    "value", flat=True
                )
            )
            for tt in SEED_TASK_TYPES:
                if tt not in existing_task_types:
                    Directory.objects.create(dir_type="task_type", value=tt)

            # ── 2. Обновляем существующие задачи случайными данными ────────────

            depts = list(
                Directory.objects.filter(dir_type="dept").values_list(
                    "value", flat=True
                )
            )
            sector_qs = Directory.objects.filter(dir_type="sector").select_related(
                "parent"
            )
            sectors_by_parent = {}
            for s in sector_qs:
                if s.parent_id:
                    sectors_by_parent.setdefault(s.parent_id, []).append(s.value)

            dept_id_map = {
                e.value: e.pk for e in Directory.objects.filter(dir_type="dept")
            }

            # Кэшируем сотрудников для назначения executor FK
            employees = list(Employee.objects.all()[:200])

            works = list(Work.objects.filter(show_in_plan=True)[:10_000])

            for work in works:
                dept_val = random.choice(depts) if depts else None
                dept_dir_id = dept_id_map.get(dept_val)
                secs = sectors_by_parent.get(dept_dir_id, [])
                sector_val = random.choice(secs) if secs else None
                work_name_val = random.choice(SEED_WORK_NAMES)
                work_num_val = f"{random.randint(1, 99):02d}-{random.randint(100, 999)}"
                just_val = random.choice(SEED_JUSTIFICATIONS)
                stage_val = random.choice(
                    _SEED_STAGES.get(random.choice(_SEED_PROJECTS), ["Этап 1"])
                )
                desc_val = f"Описание: {work_name_val.lower()}"

                yr = random.choice([2025, 2026])
                ds = date(yr, 1, 1) + timedelta(days=random.randint(0, 330))
                de = ds + timedelta(days=random.randint(14, 120))
                deadline = de + timedelta(days=random.randint(0, 30))
                ph = _rand_plan_hours(ds, de)

                if dept_val:
                    dept_obj = _get_or_create_dept(dept_val)
                    work.department = dept_obj
                    if sector_val:
                        sector_obj = _get_or_create_sector(dept_obj, sector_val)
                        work.sector = sector_obj

                work.executor = random.choice(employees) if employees else None
                work.work_name = work_name_val
                work.work_num = work_num_val
                work.work_designation = desc_val
                work.date_start = ds
                work.date_end = de
                work.deadline = deadline
                work.plan_hours = ph
                work.justification = just_val
                work.stage_num = stage_val

            if works:
                Work.objects.bulk_update(
                    works,
                    [
                        "department",
                        "sector",
                        "executor",
                        "work_name",
                        "work_num",
                        "work_designation",
                        "date_start",
                        "date_end",
                        "deadline",
                        "plan_hours",
                        "justification",
                        "stage_num",
                    ],
                    batch_size=1000,
                )

        return JsonResponse({"updated": len(works)})


# ── POST /api/fill_dept ─────────────────────────────────────────────────────


class FillDeptView(AdminRequiredJsonMixin, View):
    """
    Заполнение справочника отделов + секторов и назначение отделов задачам.
    """

    def post(self, request):
        with transaction.atomic():
            existing_depts = set(
                Directory.objects.filter(dir_type="dept").values_list(
                    "value", flat=True
                )
            )
            for d in SEED_DEPTS:
                if d not in existing_depts:
                    Directory.objects.create(dir_type="dept", value=d)

            dept_entries = {
                e.value: e for e in Directory.objects.filter(dir_type="dept")
            }
            existing_sectors = set(
                Directory.objects.filter(dir_type="sector").values_list(
                    "value", flat=True
                )
            )
            for dept_val, dept_entry in dept_entries.items():
                for suffix in _SECTOR_SUFFIXES:
                    sector_val = f"{dept_val}-{suffix}"
                    if sector_val not in existing_sectors:
                        Directory.objects.create(
                            dir_type="sector",
                            value=sector_val,
                            parent=dept_entry,
                        )

            depts = list(dept_entries.keys())

            if not depts:
                return JsonResponse({"error": "Нет отделов в справочнике"}, status=400)

            works = list(Work.objects.filter(show_in_plan=True)[:10_000])

            for work in works:
                dept_code = random.choice(depts)
                dept_obj = _get_or_create_dept(dept_code)
                work.department = dept_obj

            if works:
                Work.objects.bulk_update(works, ["department"], batch_size=1000)

        return JsonResponse({"updated": len(works), "depts_used": depts})


# ── POST /api/seed_analytics ──────────────────────────────────────────────

_TRIP_LOCATIONS = [
    "СПб, Северная верфь",
    "Северодвинск, Севмаш",
    "Москва, головной офис",
    "Нижний Новгород, Красное Сормово",
    "Комсомольск-на-Амуре, АСЗ",
    "Калининград, Янтарь",
    "Мурманск, 35 СРЗ",
    "Владивосток, Звезда",
    "Севастополь, 13 СРЗ",
    "Астрахань, ЛСЗ",
]

_TRIP_PURPOSES = [
    "Авторский надзор",
    "Согласование КД",
    "Техническое сопровождение",
    "Приёмо-сдаточные испытания",
    "Согласование ТУ",
    "Входной контроль",
    "Корректировка документации",
    "Шеф-монтаж",
]


class SeedAnalyticsView(AdminRequiredJsonMixin, View):
    """
    Генерация данных для модуля аналитики:
    1. Отпуска для ВСЕХ сотрудников (ежегодный 14-28 дней)
    2. Командировки для 15% сотрудников (10-120 дней)
    3. Заполнение plan_hours для всех СП-задач с учётом загрузки:
       - 20% сотрудников — перегруз (110-140% нормы)
       - 15% сотрудников — недогруз (30-60% нормы)
       - 65% сотрудников — нормальная загрузка (70-100% нормы)
    """

    def post(self, request):
        year = date.today().year
        employees = list(Employee.objects.all())
        if not employees:
            return JsonResponse({"error": "Нет сотрудников в базе"}, status=400)

        # Загружаем нормы рабочего времени
        norms = {}
        for wc in WorkCalendar.objects.filter(year=year):
            norms[wc.month] = float(wc.hours_norm)
        annual_norm = sum(norms.values())  # полный годовой фонд
        if annual_norm == 0:
            return JsonResponse(
                {"error": f"Нет данных WorkCalendar за {year} год"},
                status=400,
            )

        stats = {"vacations": 0, "trips": 0, "works_updated": 0}

        with transaction.atomic():
            # ── 1. Отпуска для всех сотрудников ───────────────────────────
            existing_vac_ids = set(
                Vacation.objects.filter(
                    employee__in=employees,
                    date_start__year=year,
                ).values_list("employee_id", flat=True)
            )
            vac_to_create = []
            for emp in employees:
                if emp.pk in existing_vac_ids:
                    continue
                # Летний отпуск (июнь-сентябрь, основной)
                summer_start_day = random.randint(152, 260)  # ~июнь-сентябрь
                d_start = date(year, 1, 1) + timedelta(days=summer_start_day)
                duration = random.randint(14, 28)
                d_end = d_start + timedelta(days=duration)
                vac_to_create.append(
                    Vacation(
                        employee=emp,
                        vac_type=Vacation.TYPE_ANNUAL,
                        date_start=d_start,
                        date_end=d_end,
                        notes="Ежегодный оплачиваемый отпуск",
                    )
                )
            if vac_to_create:
                Vacation.objects.bulk_create(vac_to_create, batch_size=500)
            stats["vacations"] = len(vac_to_create)

            # ── 2. Командировки для 15% сотрудников ─────────────────────
            existing_trip_ids = set(
                BusinessTrip.objects.filter(
                    employee__in=employees,
                    date_start__year=year,
                ).values_list("employee_id", flat=True)
            )
            trip_count = max(1, int(len(employees) * 0.15))
            trip_employees = random.sample(employees, min(trip_count, len(employees)))
            trips_to_create = []
            for emp in trip_employees:
                if emp.pk in existing_trip_ids:
                    continue
                start_day = random.randint(0, 300)
                d_start = date(year, 1, 1) + timedelta(days=start_day)
                duration = random.randint(10, 120)
                d_end = d_start + timedelta(days=duration)
                status = random.choice(
                    [
                        BusinessTrip.STATUS_PLAN,
                        BusinessTrip.STATUS_ACTIVE,
                        BusinessTrip.STATUS_DONE,
                    ]
                )
                trips_to_create.append(
                    BusinessTrip(
                        employee=emp,
                        location=random.choice(_TRIP_LOCATIONS),
                        purpose=random.choice(_TRIP_PURPOSES),
                        date_start=d_start,
                        date_end=d_end,
                        status=status,
                    )
                )
            if trips_to_create:
                BusinessTrip.objects.bulk_create(trips_to_create, batch_size=500)
            stats["trips"] = len(trips_to_create)

            # ── 3. Заполнение plan_hours для СП-задач ─────────────────────
            # Распределяем сотрудников по категориям загрузки
            random.shuffle(employees)
            n_over = max(1, int(len(employees) * 0.20))  # 20% перегруз
            n_under = max(1, int(len(employees) * 0.15))  # 15% недогруз
            over_ids = set(e.pk for e in employees[:n_over])
            under_ids = set(e.pk for e in employees[n_over : n_over + n_under])
            # остальные — нормальная загрузка

            # Собираем задачи по исполнителям
            works = list(
                Work.objects.filter(
                    show_in_plan=True, executor__isnull=False
                ).select_related("executor")
            )
            works_by_emp = {}
            for w in works:
                works_by_emp.setdefault(w.executor_id, []).append(w)

            updated = []
            for emp_id, emp_works in works_by_emp.items():
                # Определяем целевую загрузку
                if emp_id in over_ids:
                    target_pct = random.uniform(1.10, 1.40)  # 110-140%
                elif emp_id in under_ids:
                    target_pct = random.uniform(0.30, 0.60)  # 30-60%
                else:
                    target_pct = random.uniform(0.70, 1.00)  # 70-100%

                target_hours = annual_norm * target_pct
                # Распределяем часы по задачам
                n_tasks = len(emp_works)
                if n_tasks == 0:
                    continue

                # Генерируем случайные веса для каждой задачи
                weights = [random.random() for _ in range(n_tasks)]
                total_w = sum(weights)
                if total_w == 0:
                    continue

                for i, w in enumerate(emp_works):
                    task_hours = target_hours * weights[i] / total_w
                    if task_hours < 1:
                        task_hours = 1

                    # Определяем месяцы по date_start/date_end
                    ds = w.date_start or date(year, 1, 1)
                    de = w.date_end or date(year, 12, 31)
                    months = []
                    cur = date(ds.year, ds.month, 1)
                    end_m = date(de.year, de.month, 1)
                    while cur <= end_m:
                        if cur.year == year:
                            months.append(cur.month)
                        if cur.month == 12:
                            cur = date(cur.year + 1, 1, 1)
                        else:
                            cur = date(cur.year, cur.month + 1, 1)

                    if not months:
                        months = [ds.month]

                    # Распределяем часы по месяцам задачи
                    ph = {}
                    remaining = round(task_hours, 1)
                    for j, m in enumerate(months):
                        if j == len(months) - 1:
                            val = max(1.0, round(remaining, 1))
                        else:
                            val = round(
                                remaining
                                / (len(months) - j)
                                * random.uniform(0.6, 1.4),
                                1,
                            )
                            val = max(1.0, min(val, remaining - (len(months) - j - 1)))
                        key = f"{year}-{m:02d}"
                        ph[key] = val
                        remaining -= val
                        if remaining <= 0:
                            break

                    w.plan_hours = ph
                    updated.append(w)

            if updated:
                Work.objects.bulk_update(updated, ["plan_hours"], batch_size=1000)
            stats["works_updated"] = len(updated)

        return JsonResponse(stats)
