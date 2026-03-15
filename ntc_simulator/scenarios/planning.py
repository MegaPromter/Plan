"""
Module 2: Planning -- create UP projects, PP plans, PP rows, sync PP->SP.

v2: 6 projects, more PP plans, 80-150 rows per plan, distributed across 10 depts.
"""
import logging
from datetime import date, timedelta

logger = logging.getLogger('simulator')

# Названия проектов
PROJECT_TEMPLATES = [
    {'name_full': 'Проект "РОС" -- Разработка оптических систем', 'name_short': 'РОС', 'code': 'ПР-РОС-2026'},
    {'name_full': 'Проект "Персей" -- Перспективные системы единой ядерной', 'name_short': 'Персей', 'code': 'ПР-ПЕР-2026'},
    {'name_full': 'Проект "Орион" -- Опытная разработка интегрированных объектов навигации', 'name_short': 'Орион', 'code': 'ПР-ОРН-2026'},
    {'name_full': 'Проект "Каскад" -- Комплексная автоматизация систем контроля', 'name_short': 'Каскад', 'code': 'ПР-КСК-2026'},
    {'name_full': 'Проект "Гранит" -- Глобальная разработка навигационных технологий', 'name_short': 'Гранит', 'code': 'ПР-ГРН-2026'},
    {'name_full': 'Проект "Байкал" -- Базовые исследования конструкций аэрокосмических летательных', 'name_short': 'Байкал', 'code': 'ПР-БКЛ-2026'},
]

TASK_TYPES = [
    ('Выпуск нового документа', 0.60),
    ('Корректировка документа', 0.20),
    ('Техническое сопровождение', 0.15),
    ('Прочие работы', 0.05),
]

WORK_NAME_TEMPLATES = [
    'Чертёж общего вида {des}',
    'Сборочный чертёж {des}',
    'Спецификация {des}',
    'Габаритный чертёж {des}',
    'Схема электрическая {des}',
    'Пояснительная записка {des}',
    'Ведомость покупных изделий {des}',
    'Технические условия {des}',
    'Программа и методика испытаний {des}',
    'Расчёт прочности {des}',
    'Деталировка {des}',
    'Монтажный чертёж {des}',
    'Схема гидравлическая {des}',
    'Электромонтажный чертёж {des}',
    'Ведомость документов {des}',
    'Расчёт надёжности {des}',
    'Технологическая карта {des}',
    'Контрольный чертёж {des}',
]


def _gen_designation(rng):
    """Generates designation like АБВГ.ХХХХХХ.ХХХ."""
    letters = ''.join(rng.choices('АБВГДЕЖЗИК', k=4))
    nums = f"{rng.randint(100000, 999999)}"
    suffix = f"{rng.randint(100, 999)}"
    return f"{letters}.{nums}.{suffix}"


def _weighted_choice(rng, items):
    """Weighted random choice from (value, weight) list."""
    values, weights = zip(*items)
    return rng.choices(values, weights=weights, k=1)[0]


def create_projects(client, rng, config):
    """Creates UP projects."""
    count = config.get('projects', {}).get('count', 6)
    templates = rng.sample(PROJECT_TEMPLATES, min(count, len(PROJECT_TEMPLATES)))

    projects = []
    for tpl in templates:
        resp = client.post('/api/projects/create/', tpl)
        data = client.json_ok(resp)
        if data and data.get('id'):
            proj = {**tpl, 'id': data['id']}
            projects.append(proj)
            logger.info("UP project created: %s (id=%d)", tpl['name_short'], data['id'])
        else:
            logger.warning("Failed to create project: %s", tpl['name_short'])
    return projects


def create_pp_plans(client, rng, projects, config):
    """Creates PP plans for projects."""
    pp_range = config.get('projects', {}).get('pp_plans_per_project', [2, 3])
    pp_plans = []

    for proj in projects:
        nplans = rng.randint(*pp_range)
        for i in range(nplans):
            name = f"ПП-{proj['name_short']}-{i + 1}"
            resp = client.post('/api/pp_projects/create/', {
                'name': name,
                'up_project': proj['id'],
            })
            data = client.json_ok(resp)
            if data and data.get('id'):
                pp = {'id': data['id'], 'name': name, 'project': proj}
                pp_plans.append(pp)
                logger.info("PP plan created: %s (id=%d)", name, data['id'])
            else:
                logger.warning("Failed to create PP plan: %s", name)
    return pp_plans


def create_pp_rows(client, rng, pp_plans, org_data, config):
    """
    Creates PP rows. 80-150 rows per plan, evenly distributed across departments.
    Total: ~1000-2000+ PP rows.
    """
    rows_range = config.get('projects', {}).get('pp_rows_per_plan', [80, 150])
    departments = org_data['departments']
    employees = org_data['employees']

    # Group employees by dept/sector
    emp_by_sector = {}
    for emp in employees:
        if emp['sector']:
            key = (emp['dept'], emp['sector'])
            emp_by_sector.setdefault(key, []).append(emp)

    all_rows = []
    row_id_counter = 0

    for pp in pp_plans:
        nrows = rng.randint(*rows_range)
        logger.info("Creating %d PP rows for %s...", nrows, pp['name'])
        created_in_plan = 0

        for row_idx in range(nrows):
            row_id_counter += 1
            if not departments:
                continue
            dept_code, _, sector_codes = rng.choice(departments)
            sector_code = rng.choice(sector_codes) if sector_codes else ''

            key = (dept_code, sector_code)
            sector_emps = emp_by_sector.get(key, [])
            executor_name = ''
            if sector_emps:
                emp = rng.choice(sector_emps)
                executor_name = emp['full_name']

            # Task duration 1-4 months
            start_offset = rng.randint(0, 300)
            duration = rng.randint(20, 120)
            date_start = date(2026, 1, 1) + timedelta(days=start_offset)
            date_end = date_start + timedelta(days=duration)
            if date_end > date(2026, 12, 31):
                date_end = date(2026, 12, 31)

            designation = _gen_designation(rng)
            task_type = _weighted_choice(rng, TASK_TYPES)
            work_name_tpl = rng.choice(WORK_NAME_TEMPLATES)
            work_name = work_name_tpl.format(des=designation)

            body = {
                'work_name': work_name,
                'work_designation': designation,
                'date_start': date_start.isoformat(),
                'date_end': date_end.isoformat(),
                'dept': dept_code,
                'sector_head': sector_code,
                'executor': executor_name,
                'task_type': task_type,
                'row_code': f"PP-{row_id_counter:05d}",
                'work_order': row_idx + 1,
                'stage_num': rng.randint(1, 5),
                'milestone_num': rng.randint(1, 8),
                'work_num': rng.randint(1, 20),
                'sheets_a4': rng.randint(1, 50),
                'norm': round(rng.uniform(0.5, 3.0), 2),
                'coeff': round(rng.uniform(0.8, 1.5), 2),
                'total_2d': rng.randint(1, 30),
                'total_3d': rng.randint(0, 10),
                'labor': rng.randint(10, 500),
                'project_id': pp['id'],
            }

            resp = client.post('/api/production_plan/create/', body)
            data = client.json_ok(resp)
            if data and data.get('id'):
                all_rows.append({**body, 'id': data['id'], 'pp_plan': pp})
                created_in_plan += 1
            elif resp and resp.status_code >= 500:
                client.metrics.report_bug(
                    f"500 creating PP row: {resp.text[:200]}")

        logger.info("PP %s: created %d rows", pp['name'], created_in_plan)

    logger.info("Total PP rows: %d", len(all_rows))
    return all_rows


def sync_pp_to_sp(client, pp_plans):
    """Syncs all PP plans -> SP tasks."""
    logger.info("Syncing PP->SP...")
    total_synced = 0
    for pp in pp_plans:
        resp = client.post('/api/production_plan/sync/', {
            'project_id': pp['id'],
        })
        data = client.json_ok(resp)
        if data:
            count = data.get('synced', data.get('created', 0))
            total_synced += count if isinstance(count, int) else 0
            logger.info("Sync %s: %s", pp['name'], data)
        else:
            if resp and resp.status_code >= 500:
                client.metrics.report_bug(
                    f"500 syncing PP->SP: {pp['name']}")
            logger.warning("Sync %s: error", pp['name'])
    logger.info("Total synced: %d", total_synced)
    return total_synced
