"""
Module 4: Monthly simulation.

v2 Requirements:
  - Each of 10 departments creates 500-1000 tasks per month (PP + SP combined)
  - At least 4 tasks per employee per month
  - 5-50% of tasks have deadline misses (overdue simulation)
  - Tasks created in both PP and SP
  - Every employee fills report at end of month
  - Vacations, notices, PP adjustments
"""
import logging
from datetime import date, timedelta

logger = logging.getLogger('simulator')

MONTH_NAMES = [
    '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

TASK_TYPES = [
    ('Выпуск нового документа', 0.55),
    ('Корректировка документа', 0.25),
    ('Техническое сопровождение', 0.15),
    ('Прочие работы', 0.05),
]

WORK_NAME_TEMPLATES_SP = [
    'Разработка {des}',
    'Корректировка {des}',
    'Доработка {des}',
    'Проверка {des}',
    'Согласование {des}',
    'Ревизия {des}',
    'Оформление {des}',
    'Верификация {des}',
    'Анализ {des}',
    'Контроль {des}',
    'Сопровождение {des}',
    'Экспертиза {des}',
]


def _gen_designation(rng):
    letters = ''.join(rng.choices('АБВГДЕЖЗИК', k=4))
    return f"{letters}.{rng.randint(100000, 999999)}.{rng.randint(100, 999)}"


def _weighted_choice(rng, items):
    values, weights = zip(*items)
    return rng.choices(values, weights=weights, k=1)[0]


def month_name(m):
    return MONTH_NAMES[m] if 1 <= m <= 12 else f'Месяц {m}'


def simulate_month(client, rng, month, year, org_data, pp_plans, config, metrics):
    """
    Simulates one month of NTC operations.
    Returns per-department and total statistics.
    """
    month_cfg = config.get('monthly', {})
    mname = month_name(month)

    logger.info("=== %s %d ===", mname, year)
    stats = {
        'vacations_created': 0,
        'pp_tasks_created': 0,
        'sp_tasks_created': 0,
        'tasks_updated': 0,
        'deadlines_missed': 0,
        'reports_created': 0,
        'notices_processed': 0,
        'pp_changes': 0,
    }

    departments = org_data['departments']
    employees = org_data['employees']

    # Group employees by department
    emp_by_dept = {}
    for emp in employees:
        if emp['dept']:
            emp_by_dept.setdefault(emp['dept'], []).append(emp)

    # Group employees by dept/sector
    emp_by_sector = {}
    for emp in employees:
        if emp['dept'] and emp['sector']:
            key = (emp['dept'], emp['sector'])
            emp_by_sector.setdefault(key, []).append(emp)

    # 1. Vacations
    stats['vacations_created'] = _create_vacations(
        client, rng, month, year, employees, month_cfg)

    # 2. Create tasks PER DEPARTMENT (PP + SP = 500-1000)
    for dept_code, center_code, sector_codes in departments:
        dept_emps = emp_by_dept.get(dept_code, [])
        if not dept_emps:
            continue

        dept_stats = _create_dept_tasks(
            client, rng, month, year,
            dept_code, sector_codes, dept_emps, emp_by_sector,
            pp_plans, month_cfg)

        stats['pp_tasks_created'] += dept_stats['pp_created']
        stats['sp_tasks_created'] += dept_stats['sp_created']

    # 3. Simulate deadline misses (5-50% of tasks)
    stats['deadlines_missed'] = _simulate_deadline_misses(
        client, rng, month, year, month_cfg)

    # 4. Update some tasks (plan_hours, dates)
    stats['tasks_updated'] = _update_tasks(
        client, rng, month, year, month_cfg)

    # 5. Every employee fills reports at end of month
    stats['reports_created'] = _create_employee_reports(
        client, rng, month, year, employees, month_cfg)

    # 6. Process notices
    stats['notices_processed'] = _process_notices(
        client, rng, month, year, month_cfg)

    # 7. PP adjustments
    stats['pp_changes'] = _adjust_pp(
        client, rng, month, year, pp_plans, departments, emp_by_sector, month_cfg)

    total_created = stats['pp_tasks_created'] + stats['sp_tasks_created']
    logger.info("Итог %s: PP+%d, SP+%d (=%d), обнов.%d, срывов=%d, отчётов+%d, отпусков+%d",
                mname, stats['pp_tasks_created'], stats['sp_tasks_created'],
                total_created, stats['tasks_updated'], stats['deadlines_missed'],
                stats['reports_created'], stats['vacations_created'])
    return stats


# ---------------------------------------------------------------------------
#  1. Vacations
# ---------------------------------------------------------------------------

def _create_vacations(client, rng, month, year, employees, cfg):
    """Creates vacations for some employees (5% probability)."""
    prob = cfg.get('vacation_probability', 0.05)
    created = 0

    for emp in employees:
        if rng.random() > prob:
            continue
        duration = rng.randint(7, 14)
        start_day = rng.randint(1, 25)
        try:
            d_from = date(year, month, min(start_day, 28))
        except ValueError:
            d_from = date(year, month, 1)
        d_to = d_from + timedelta(days=duration)

        vac_type = rng.choice(['annual', 'annual', 'annual', 'sick', 'unpaid'])
        resp = client.post('/api/vacations/create/', {
            'employee_name': emp['full_name'],
            'date_from': d_from.isoformat(),
            'date_to': d_to.isoformat(),
            'vacation_type': vac_type,
        })
        if client.json_ok(resp):
            created += 1

    return created


# ---------------------------------------------------------------------------
#  2. Create dept tasks: PP + SP = 500-1000 per dept
# ---------------------------------------------------------------------------

def _create_dept_tasks(client, rng, month, year,
                       dept_code, sector_codes, dept_emps, emp_by_sector,
                       pp_plans, cfg):
    """
    Creates tasks for one department in one month.
    Target: min_tasks_per_dept (500) to max_tasks_per_dept (1000).
    Split ~40% PP, ~60% SP.
    Ensures at least min_tasks_per_employee (4) per worker.
    """
    min_total = cfg.get('min_tasks_per_dept', 500)
    max_total = cfg.get('max_tasks_per_dept', 1000)
    min_per_emp = cfg.get('min_tasks_per_employee', 4)

    target_total = rng.randint(min_total, max_total)

    # Ensure at least min_per_emp * workers
    worker_emps = [e for e in dept_emps if e['role'] in ('user', 'sector_head')]
    min_by_workers = min_per_emp * max(len(worker_emps), 1)
    target_total = max(target_total, min_by_workers)

    # Split: ~40% PP, ~60% SP
    pp_count = int(target_total * 0.4)
    sp_count = target_total - pp_count

    result = {'pp_created': 0, 'sp_created': 0}

    # --- Create PP rows ---
    if pp_plans:
        pp = rng.choice(pp_plans)
        result['pp_created'] = _create_pp_batch(
            client, rng, month, year,
            dept_code, sector_codes, emp_by_sector,
            pp, pp_count, cfg)

    # --- Create SP tasks ---
    result['sp_created'] = _create_sp_batch(
        client, rng, month, year,
        dept_code, sector_codes, worker_emps, emp_by_sector,
        sp_count, min_per_emp, cfg)

    logger.debug("Dept %s %02d/%d: PP=%d SP=%d (target=%d)",
                 dept_code, month, year,
                 result['pp_created'], result['sp_created'], target_total)
    return result


def _create_pp_batch(client, rng, month, year,
                     dept_code, sector_codes, emp_by_sector,
                     pp, count, cfg):
    """Creates a batch of PP rows for one department in one month."""
    created = 0
    dur_range = cfg.get('task_duration', [20, 120])

    for i in range(count):
        sector_code = rng.choice(sector_codes) if sector_codes else ''
        key = (dept_code, sector_code)
        sector_emps = emp_by_sector.get(key, [])
        executor_name = rng.choice(sector_emps)['full_name'] if sector_emps else ''

        try:
            d_start = date(year, month, rng.randint(1, 25))
        except ValueError:
            d_start = date(year, month, 1)
        duration = rng.randint(*dur_range)
        d_end = d_start + timedelta(days=duration)
        if d_end > date(2026, 12, 31):
            d_end = date(2026, 12, 31)

        designation = _gen_designation(rng)
        task_type = _weighted_choice(rng, TASK_TYPES)

        body = {
            'work_name': f"{task_type} {designation}",
            'work_designation': designation,
            'date_start': d_start.isoformat(),
            'date_end': d_end.isoformat(),
            'dept': dept_code,
            'sector_head': sector_code,
            'executor': executor_name,
            'task_type': task_type,
            'row_code': f"PP-M{month:02d}-{dept_code}-{i + 1:04d}",
            'work_order': i + 1,
            'stage_num': rng.randint(1, 5),
            'milestone_num': rng.randint(1, 8),
            'work_num': rng.randint(1, 20),
            'sheets_a4': rng.randint(1, 30),
            'norm': round(rng.uniform(0.5, 2.5), 2),
            'coeff': round(rng.uniform(0.8, 1.3), 2),
            'total_2d': rng.randint(1, 15),
            'total_3d': rng.randint(0, 5),
            'labor': rng.randint(10, 200),
            'project_id': pp['id'],
        }

        resp = client.post('/api/production_plan/create/', body)
        if client.json_ok(resp):
            created += 1
        elif resp and resp.status_code >= 500:
            client.metrics.report_bug(
                f"500 creating PP row dept {dept_code}: {resp.text[:200]}")

    # Sync new PP rows to SP
    if created > 0:
        client.post('/api/production_plan/sync/', {'project_id': pp['id']})

    return created


def _create_sp_batch(client, rng, month, year,
                     dept_code, sector_codes, worker_emps, emp_by_sector,
                     count, min_per_emp, cfg):
    """
    Creates SP tasks for one department.
    Ensures at least min_per_emp tasks per worker.
    """
    created = 0
    dur_range = cfg.get('task_duration', [20, 120])

    # Build assignment queue: ensure min_per_emp per worker first
    assignments = []
    for emp in worker_emps:
        for _ in range(min_per_emp):
            assignments.append(emp)

    # Fill remaining slots with random workers
    remaining = count - len(assignments)
    for _ in range(max(0, remaining)):
        if worker_emps:
            assignments.append(rng.choice(worker_emps))

    rng.shuffle(assignments)

    for i, emp in enumerate(assignments):
        sector_code = emp.get('sector', '')
        try:
            d_start = date(year, month, rng.randint(1, 25))
        except ValueError:
            d_start = date(year, month, 1)
        duration = rng.randint(*dur_range)
        d_end = d_start + timedelta(days=duration)
        if d_end > date(2026, 12, 31):
            d_end = date(2026, 12, 31)

        designation = _gen_designation(rng)
        task_type = _weighted_choice(rng, TASK_TYPES)
        tpl = rng.choice(WORK_NAME_TEMPLATES_SP)
        work_name = tpl.format(des=designation)

        # plan_hours distributed across task months
        plan_hours = {}
        m = month
        total_hours = rng.randint(10, 80)
        while total_hours > 0 and m <= 12:
            h = min(total_hours, rng.randint(5, 30))
            plan_hours[f"{year}-{m:02d}"] = h
            total_hours -= h
            m += 1

        body = {
            'work_name': work_name,
            'work_number': str(rng.randint(1, 999)),
            'dept': dept_code,
            'sector': sector_code,
            'executor': emp['full_name'],
            'date_start': d_start.isoformat(),
            'date_end': d_end.isoformat(),
            'deadline': d_end.isoformat(),
            'plan_hours': plan_hours,
            'stage': f"Этап {rng.randint(1, 5)}",
            'justification': f"Оперативная задача {month_name(month)} {year}",
            'task_type': task_type,
        }

        resp = client.post('/api/tasks/create/', body)
        data = client.json_ok(resp)
        if data and data.get('id'):
            created += 1
        elif resp and resp.status_code >= 500:
            client.metrics.report_bug(
                f"500 creating SP task dept {dept_code}: {resp.text[:200]}")

    return created


# ---------------------------------------------------------------------------
#  3. Deadline misses: 5-50% of current tasks get date_end shifted to past
# ---------------------------------------------------------------------------

def _simulate_deadline_misses(client, rng, month, year, cfg):
    """
    Simulates deadline misses by setting date_end to a date in the past.
    Affects 5-50% of tasks for the month.
    """
    miss_range = cfg.get('deadline_miss_ratio', [0.05, 0.50])
    miss_ratio = rng.uniform(*miss_range)

    # Fetch tasks for current month
    resp = client.get('/api/tasks/', params={'limit': 5000})
    data = client.json_ok(resp)
    if not data:
        return 0

    tasks = data if isinstance(data, list) else data.get('items', [])
    # Filter tasks that have date_end in the future or current month
    month_key = f"{year}-{month:02d}"
    eligible = [
        t for t in tasks
        if t.get('date_end', '') >= month_key
        and not t.get('from_pp', False)  # Only SP tasks (PP dates locked)
    ]

    n_miss = int(len(eligible) * miss_ratio)
    if n_miss == 0:
        return 0

    targets = rng.sample(eligible, min(n_miss, len(eligible)))
    missed = 0

    for task in targets:
        tid = task['id']
        # Set date_end to a few days ago (simulating overdue)
        try:
            overdue_date = date(year, month, rng.randint(1, 20))
        except ValueError:
            overdue_date = date(year, month, 1)
        overdue_date = overdue_date - timedelta(days=rng.randint(1, 15))

        body = {
            'date_end': overdue_date.isoformat(),
        }
        if task.get('updated_at'):
            body['updated_at'] = task['updated_at']

        resp = client.put(f'/api/tasks/{tid}/', body)
        if resp and resp.status_code < 300:
            missed += 1
        elif resp and resp.status_code == 409:
            pass  # Optimistic lock conflict, skip

    logger.info("Deadline misses: %d/%d (ratio %.1f%%)",
                missed, len(eligible), miss_ratio * 100)
    return missed


# ---------------------------------------------------------------------------
#  4. Task updates
# ---------------------------------------------------------------------------

def _update_tasks(client, rng, month, year, cfg):
    """Updates random tasks (plan_hours adjustments)."""
    update_ratio = cfg.get('task_update_ratio', 0.15)
    updated = 0

    resp = client.get('/api/tasks/', params={'limit': 5000})
    data = client.json_ok(resp)
    if not data:
        return 0

    tasks = data if isinstance(data, list) else data.get('items', [])
    if not tasks:
        return 0

    n_updates = int(len(tasks) * update_ratio)
    targets = rng.sample(tasks, min(n_updates, len(tasks)))

    for task in targets:
        tid = task['id']
        # Update plan_hours
        new_hours = {}
        m = month
        while m <= 12:
            if rng.random() > 0.5:
                new_hours[f"{year}-{m:02d}"] = rng.randint(5, 40)
            m += 1

        body = {'plan_hours': new_hours}
        if task.get('updated_at'):
            body['updated_at'] = task['updated_at']

        resp = client.put(f'/api/tasks/{tid}/', body)
        if resp and resp.status_code < 300:
            updated += 1

    return updated


# ---------------------------------------------------------------------------
#  5. Employee reports: every employee fills report at end of month
# ---------------------------------------------------------------------------

def _create_employee_reports(client, rng, month, year, employees, cfg):
    """
    Every employee fills at least one report at end of month.
    Finds tasks assigned to each employee and creates a report for them.
    """
    created = 0
    doc_counter = month * 10000

    # Get all tasks to find per-employee assignments
    resp = client.get('/api/tasks/', params={'limit': 5000})
    data = client.json_ok(resp)
    if not data:
        return 0

    tasks = data if isinstance(data, list) else data.get('items', [])

    # Build executor -> tasks map
    executor_tasks = {}
    for t in tasks:
        executor = t.get('executor', '')
        if executor:
            executor_tasks.setdefault(executor, []).append(t)

    worker_emps = [e for e in employees
                   if e['role'] in ('user', 'sector_head', 'dept_head', 'dept_deputy')]

    for emp in worker_emps:
        emp_tasks = executor_tasks.get(emp['full_name'], [])
        if not emp_tasks:
            continue

        # Pick 1-3 tasks to report on
        n_reports = min(rng.randint(1, 3), len(emp_tasks))
        report_tasks = rng.sample(emp_tasks, n_reports)

        for task in report_tasks:
            tid = task['id']
            task_type = task.get('task_type', '')
            doc_counter += 1

            ii_pi = 'ИИ'
            if task_type == 'Корректировка документа':
                ii_pi = rng.choice(['ИИ', 'ПИ'])

            try:
                d_accepted = date(year, month, rng.randint(20, 28))
            except ValueError:
                d_accepted = date(year, month, 1)
            d_expires = d_accepted + timedelta(days=rng.randint(30, 180))

            body = {
                'task_id': tid,
                'doc_type': rng.choice(['ЧО', 'СБ', 'СП', 'ТУ', 'РР', 'ВП', 'ПЗ']),
                'doc_number': f"Д-{year}-{doc_counter:06d}",
                'doc_name': f"Документ {emp['full_name']} к задаче {tid}",
                'doc_designation': task.get('description', ''),
                'sheets_a4': rng.randint(1, 20),
                'norm': round(rng.uniform(0.5, 3.0), 2),
                'coeff': round(rng.uniform(0.8, 1.5), 2),
                'bvd_hours': rng.randint(4, 40),
                'date_accepted': d_accepted.isoformat(),
                'date_expires': d_expires.isoformat(),
                'ii_pi': ii_pi,
            }

            resp = client.post('/api/reports/', body)
            if client.json_ok(resp):
                created += 1
            elif resp and resp.status_code >= 500:
                client.metrics.report_bug(
                    f"500 creating report for task {tid}: {resp.text[:200]}")

    logger.info("Reports: %d created by %d employees", created, len(worker_emps))
    return created


# ---------------------------------------------------------------------------
#  6. Notices
# ---------------------------------------------------------------------------

def _process_notices(client, rng, month, year, cfg):
    """Close some open notices."""
    notice_range = cfg.get('notices_per_month', [10, 30])
    n_actions = rng.randint(*notice_range)

    resp = client.get('/api/journal/', params={'per_page': 500})
    data = client.json_ok(resp)
    if not data:
        return 0

    notices = data if isinstance(data, list) else data.get('items', [])
    open_notices = [
        n for n in notices
        if not n.get('closure_notice_number')
        and n.get('ii_pi') == 'ИИ'
    ]

    processed = 0
    for n in rng.sample(open_notices, min(n_actions, len(open_notices))):
        nid = n.get('id')
        if not nid:
            continue
        try:
            closure_date = date(year, month, rng.randint(1, 28))
        except ValueError:
            closure_date = date(year, month, 1)

        resp = client.put(f'/api/journal/{nid}/', {
            'closure_notice_number': f"ПИ-{nid}-{month:02d}",
            'closure_date_issued': closure_date.isoformat(),
            'closure_executor': 'Автоматическое закрытие',
        })
        if resp and resp.status_code < 300:
            processed += 1

    return processed


# ---------------------------------------------------------------------------
#  7. PP adjustments
# ---------------------------------------------------------------------------

def _adjust_pp(client, rng, month, year, pp_plans, departments, emp_by_sector, cfg):
    """PP adjustments: add new rows, update dates."""
    changes_range = cfg.get('pp_changes_per_dept', [3, 8])
    changed = 0

    if not pp_plans:
        return 0

    for dept_code, _, sector_codes in departments:
        n_changes = rng.randint(*changes_range)

        for _ in range(n_changes):
            pp = rng.choice(pp_plans)
            action = rng.choice(['add', 'update_date'])

            if action == 'add':
                sector_code = rng.choice(sector_codes) if sector_codes else ''
                try:
                    d_start = date(year, month, rng.randint(1, 25))
                except ValueError:
                    d_start = date(year, month, 1)
                d_end = d_start + timedelta(days=rng.randint(20, 120))
                if d_end > date(2026, 12, 31):
                    d_end = date(2026, 12, 31)

                designation = _gen_designation(rng)
                key = (dept_code, sector_code)
                sector_emps = emp_by_sector.get(key, [])
                executor = rng.choice(sector_emps)['full_name'] if sector_emps else ''

                body = {
                    'work_name': f"Доп. работа ПП {month:02d}/{year} {dept_code}",
                    'work_designation': designation,
                    'date_start': d_start.isoformat(),
                    'date_end': d_end.isoformat(),
                    'dept': dept_code,
                    'sector_head': sector_code,
                    'executor': executor,
                    'task_type': 'Выпуск нового документа',
                    'row_code': f"PP-ADJ-{rng.randint(10000, 99999)}",
                    'work_order': rng.randint(100, 999),
                    'stage_num': rng.randint(1, 5),
                    'milestone_num': rng.randint(1, 8),
                    'work_num': rng.randint(1, 20),
                    'sheets_a4': rng.randint(1, 20),
                    'norm': round(rng.uniform(0.5, 2.0), 2),
                    'coeff': round(rng.uniform(0.8, 1.3), 2),
                    'total_2d': rng.randint(1, 10),
                    'total_3d': rng.randint(0, 5),
                    'labor': rng.randint(10, 200),
                    'project_id': pp['id'],
                }
                resp = client.post('/api/production_plan/create/', body)
                if client.json_ok(resp):
                    changed += 1

            elif action == 'update_date':
                resp = client.get('/api/production_plan/', params={
                    'project_id': pp['id'], 'limit': 50,
                })
                data = client.json_ok(resp)
                if not data:
                    continue
                rows = data if isinstance(data, list) else data.get('items', [])
                if rows:
                    row = rng.choice(rows)
                    new_end = date(year, min(month + rng.randint(1, 3), 12),
                                   rng.randint(1, 28))
                    resp = client.put(
                        f"/api/production_plan/{row['id']}/",
                        {'value': new_end.isoformat()},
                        params={'field': 'date_end'},
                    )
                    if resp and resp.status_code < 300:
                        changed += 1

    # Re-sync all PP plans
    if changed > 0:
        for pp in pp_plans:
            client.post('/api/production_plan/sync/', {
                'project_id': pp['id'],
            })

    return changed
