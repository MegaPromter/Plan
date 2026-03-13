"""
Модуль 5: Конкурентность — параллельные запросы от разных пользователей.
Проверка optimistic locking, rate limiting, видимости по ролям.
"""
import logging
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from api_client import ApiClient, ApiMetrics

logger = logging.getLogger('simulator')


def test_concurrency(base_url, employees, metrics, config):
    """
    Тестирует конкурентный доступ с разными ролями.
    Использует ThreadPoolExecutor для параллельных запросов.
    """
    n_users = config.get('concurrency', {}).get('parallel_users', 3)
    logger.info("Тест конкурентности: %d параллельных пользователей", n_users)

    # Выбираем пользователей с разными ролями
    role_users = {}
    for emp in employees:
        role = emp['role']
        if role not in role_users:
            role_users[role] = emp

    test_users = list(role_users.values())[:n_users]
    if not test_users:
        logger.warning("Нет пользователей для теста конкурентности")
        return {}

    results = {
        'optimistic_lock_conflicts': 0,
        'rate_limit_hits': 0,
        'visibility_violations': 0,
        'concurrent_errors': 0,
    }

    # 1. Тест optimistic locking: два пользователя обновляют одну задачу
    results['optimistic_lock_conflicts'] = _test_optimistic_locking(
        base_url, test_users, metrics)

    # 2. Тест видимости: user видит только свои задачи
    results['visibility_violations'] = _test_visibility(
        base_url, test_users, metrics)

    # 3. Тест параллельных запросов
    results['concurrent_errors'] = _test_parallel_requests(
        base_url, test_users, metrics)

    logger.info("Конкурентность: %s", results)
    return results


def _test_optimistic_locking(base_url, users, metrics):
    """Два пользователя одновременно обновляют одну задачу."""
    if len(users) < 2:
        return 0

    conflicts = 0
    clients = []
    for u in users[:2]:
        c = ApiClient(base_url, metrics)
        if c.login(u['username'], u['password']):
            clients.append(c)

    if len(clients) < 2:
        return 0

    # Находим задачу
    resp = clients[0].get('/api/tasks/', params={'limit': 5})
    data = clients[0].json_ok(resp)
    if not data:
        return 0
    tasks = data if isinstance(data, list) else data.get('items', [])
    if not tasks:
        return 0

    task = tasks[0]
    tid = task['id']
    updated_at = task.get('updated_at', '')

    # Оба клиента обновляют одновременно
    def update_task(client, idx):
        resp = client.put(f'/api/tasks/{tid}/', {
            'plan_hours': {f"2026-{idx + 1:02d}": 99},
            'updated_at': updated_at,
        })
        return resp

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(update_task, clients[0], 1),
            executor.submit(update_task, clients[1], 2),
        ]
        results = [f.result() for f in futures]

    for r in results:
        if r and r.status_code == 409:
            conflicts += 1
            logger.info("Optimistic locking сработал (409)")

    if conflicts == 0:
        # Оба запроса прошли — возможно locking не работает
        metrics.report_bug(
            "Optimistic locking: оба конкурентных обновления прошли без 409")

    return conflicts


def _test_visibility(base_url, users, metrics):
    """Проверяет что user видит только задачи своего отдела/сектора."""
    violations = 0

    regular_users = [u for u in users if u['role'] == 'user']
    if not regular_users:
        return 0

    user = regular_users[0]
    c = ApiClient(base_url, metrics)
    if not c.login(user['username'], user['password']):
        return 0

    resp = c.get('/api/tasks/', params={'limit': 200})
    data = c.json_ok(resp)
    if not data:
        return 0

    tasks = data if isinstance(data, list) else data.get('items', [])
    user_dept = user.get('dept', '')
    user_sector = user.get('sector', '')

    for task in tasks:
        task_dept = task.get('dept', '')
        task_sector = task.get('sector', '')
        # user должен видеть только свой отдел
        if user_dept and task_dept and task_dept != user_dept:
            violations += 1
            metrics.report_bug(
                f"Нарушение видимости: user ({user_dept}/{user_sector}) "
                f"видит задачу отдела {task_dept}")
            break  # Достаточно одного нарушения

    return violations


def _test_parallel_requests(base_url, users, metrics):
    """Множественные параллельные GET-запросы."""
    errors = 0
    clients = []
    for u in users:
        c = ApiClient(base_url, metrics)
        if c.login(u['username'], u['password']):
            clients.append(c)

    if not clients:
        return 0

    def fetch_tasks(client):
        resp = client.get('/api/tasks/', params={'limit': 50})
        return resp

    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        futures = [executor.submit(fetch_tasks, c) for c in clients]
        for f in futures:
            r = f.result()
            if r is None or r.status_code >= 500:
                errors += 1
            elif r.status_code == 429:
                logger.info("Rate limiting сработал (429)")

    return errors
