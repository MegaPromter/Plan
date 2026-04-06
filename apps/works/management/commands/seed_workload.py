"""
Management command: создаёт задачи для проектов ЗМ, ЛО, РО с распределением нагрузки.
- 4 отдела перегружены (>100%)
- 3 отдела недогружены (<80%)
- остальные 11 в норме (80-100%)
- ~50 сотрудников перегружены (101-135%)
- ~30 сотрудников недогружены (10-75%)
Ориентир: production calendar (hours_norm за апрель-июнь 2026).

Использование: python manage.py seed_workload
Идемпотентен: удаляет старые seed-задачи перед созданием.
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.employees.models import Department, Employee, Sector
from apps.works.models import PPProject, Work, WorkCalendar


# Месяцы для распределения задач
MONTHS = [
    (2026, 4),  # апрель
    (2026, 5),  # май
    (2026, 6),  # июнь
]

# Названия работ по тематике
WORK_NAMES = [
    'Разработка КД корпуса', 'Расчёт прочности обечайки', 'Проектирование фланцевого соединения',
    'Моделирование термонагрузки', 'Разработка схемы электропитания', 'Проектирование кабельной сети',
    'Расчёт теплового режима', 'Разработка чертежей кронштейнов', 'Проектирование системы вентиляции',
    'Расчёт вибрационной стойкости', 'Разработка компоновки приборного отсека',
    'Проектирование стыковочного узла', 'Расчёт герметичности', 'Разработка КД панели управления',
    'Проектирование системы охлаждения', 'Разработка монтажного чертежа', 'Расчёт массы изделия',
    'Разработка КД корпуса приборного блока', 'Проектирование токосъёмника',
    'Расчёт режимов электропитания', 'Разработка принципиальной схемы', 'Проектирование датчиков',
    'Расчёт надёжности системы', 'Разработка технологического процесса', 'Проектирование жгутов',
    'Разработка КД блока электроники', 'Расчёт электромагнитной совместимости',
    'Проектирование защитного кожуха', 'Разработка сборочного чертежа', 'Расчёт ресурса изделия',
]

_SEED_TAG = 'SEED_WORKLOAD'  # тег в work_designation для идентификации seed-задач


class Command(BaseCommand):
    help = 'Создаёт задачи с распределением нагрузки по отделам и сотрудникам'

    def handle(self, *args, **options):
        # Получаем нормы часов по месяцам
        norms = {}
        for year, month in MONTHS:
            wc = WorkCalendar.objects.filter(year=year, month=month).first()
            norms[(year, month)] = float(wc.hours_norm) if wc else 176.0

        # Получаем ПП-проекты для ЗМ, ЛО, РО
        pp_projects = list(PPProject.objects.filter(
            up_project__name_short__in=['ЗМ', 'ЛО', 'РО']
        ).select_related('up_project'))
        if not pp_projects:
            self.stderr.write('Нет ПП-проектов для ЗМ/ЛО/РО')
            return

        # Получаем отделы и сотрудников
        depts = list(Department.objects.all().order_by('code'))
        if len(depts) < 7:
            self.stderr.write('Недостаточно отделов')
            return

        random.seed(42)  # воспроизводимость
        random.shuffle(depts)

        # Распределяем отделы: 4 перегружены, 3 недогружены, остальные норма
        overloaded_depts = depts[:4]    # 101-130% от нормы отдела
        underloaded_depts = depts[4:7]  # 40-75% от нормы отдела
        normal_depts = depts[7:]        # 85-100% от нормы отдела

        self.stdout.write(f'Перегружены: {[d.code for d in overloaded_depts]}')
        self.stdout.write(f'Недогружены: {[d.code for d in underloaded_depts]}')
        self.stdout.write(f'В норме: {[d.code for d in normal_depts]}')

        # Удаляем старые seed-задачи
        deleted, _ = Work.objects.filter(work_designation=_SEED_TAG).delete()
        if deleted:
            self.stdout.write(f'Удалено старых seed-задач: {deleted}')

        all_employees = list(Employee.objects.filter(
            department__isnull=False, role__in=['user', 'sector_head']
        ).select_related('department', 'sector'))

        # Собираем сотрудников по отделам
        dept_employees = {}
        for emp in all_employees:
            dept_employees.setdefault(emp.department_id, []).append(emp)

        # Выбираем сотрудников для индивидуального перегруза/недогруза
        eligible = [e for e in all_employees if e.department_id in {d.id for d in normal_depts}]
        random.shuffle(eligible)
        overloaded_employees = set()  # id сотрудников с перегрузом
        underloaded_employees = set()  # id сотрудников с недогрузом

        # Из нормальных отделов: 50 перегруженных, 30 недогруженных
        for emp in eligible[:50]:
            overloaded_employees.add(emp.id)
        for emp in eligible[50:80]:
            underloaded_employees.add(emp.id)

        works_to_create = []
        total_norm = sum(norms.values())  # сумма норм за 3 месяца

        def make_works(emp, target_hours, pp_proj):
            """Генерирует задачи для сотрудника на целевое количество часов."""
            remaining = target_hours
            while remaining > 4:
                hours = min(random.uniform(8, 40), remaining)
                hours = round(hours, 1)
                remaining -= hours

                year, month = random.choice(MONTHS)
                day_start = random.randint(1, 20)
                d_start = date(year, month, day_start)
                d_end = d_start + timedelta(days=random.randint(5, 25))

                work = Work(
                    work_name=random.choice(WORK_NAMES),
                    work_designation=_SEED_TAG,
                    pp_project=pp_proj,
                    project=pp_proj.up_project,
                    show_in_plan=True,
                    show_in_pp=True,
                    date_start=d_start,
                    date_end=d_end,
                    pp_date_start=d_start,
                    pp_date_end=d_end,
                    labor=hours,
                    executor=emp,
                    dept=emp.department.code if emp.department else '',
                    sector_head=emp.sector.code if emp.sector else '',
                )
                works_to_create.append(work)

        for dept in depts:
            emps = dept_employees.get(dept.id, [])
            if not emps:
                continue

            for emp in emps:
                pp_proj = random.choice(pp_projects)

                if dept in overloaded_depts:
                    # Отдел перегружен: каждый сотрудник 100-125%
                    pct = random.uniform(1.00, 1.25)
                elif dept in underloaded_depts:
                    # Отдел недогружен: каждый сотрудник 30-70%
                    pct = random.uniform(0.30, 0.70)
                else:
                    # Нормальный отдел: базово 85-100%
                    if emp.id in overloaded_employees:
                        pct = random.uniform(1.01, 1.35)
                    elif emp.id in underloaded_employees:
                        pct = random.uniform(0.10, 0.75)
                    else:
                        pct = random.uniform(0.85, 1.00)

                target = total_norm * pct
                make_works(emp, target, pp_proj)

        with transaction.atomic():
            Work.objects.bulk_create(works_to_create, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f'Создано {len(works_to_create)} задач для {len(dept_employees)} отделов'
        ))
