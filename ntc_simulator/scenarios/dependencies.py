"""
Модуль 3: Зависимости — создание связей между задачами, проверка конфликтов, выравнивание дат.
"""

import logging
import random

logger = logging.getLogger("simulator")


DEP_TYPES = [("FS", 0.70), ("SS", 0.15), ("FF", 0.10), ("SF", 0.05)]


def _weighted_choice(rng, items):
    values, weights = zip(*items)
    return rng.choices(values, weights=weights, k=1)[0]


def create_dependencies(client, rng, config):
    """
    Создаёт зависимости между задачами СП.
    Загружает все задачи, выбирает coverage% и связывает.
    """
    dep_cfg = config.get("dependencies", {})
    coverage = dep_cfg.get("coverage", 0.3)
    max_lag = dep_cfg.get("max_lag_days", 5)

    # Загружаем все задачи
    resp = client.get("/api/tasks/", params={"limit": 5000})
    data = client.json_ok(resp)
    if not data:
        logger.warning("Не удалось загрузить задачи для зависимостей")
        return {"created": 0, "conflicts": 0, "aligned": 0}

    tasks = data if isinstance(data, list) else data.get("items", [])
    if not tasks:
        logger.warning("Нет задач для создания зависимостей")
        return {"created": 0, "conflicts": 0, "aligned": 0}

    task_ids = [t["id"] for t in tasks]
    n_deps = int(len(task_ids) * coverage)

    logger.info("Создаю ~%d зависимостей из %d задач...", n_deps, len(task_ids))

    created = 0
    conflicts = 0
    aligned = 0
    existing_pairs = set()

    for _ in range(n_deps):
        if len(task_ids) < 2:
            break
        pred_id = rng.choice(task_ids)
        succ_id = rng.choice(task_ids)
        # Без самозависимостей и дублей
        if pred_id == succ_id:
            continue
        pair = (pred_id, succ_id)
        if pair in existing_pairs:
            continue
        existing_pairs.add(pair)

        dep_type = _weighted_choice(rng, DEP_TYPES)
        lag = rng.randint(0, max_lag)

        resp = client.post(
            f"/api/tasks/{succ_id}/dependencies/",
            {
                "predecessor_id": pred_id,
                "dep_type": dep_type,
                "lag_days": lag,
            },
        )
        data = client.json_ok(resp)
        if data:
            created += 1
        elif resp and resp.status_code == 400:
            err = resp.json().get("error", "") if resp.text else ""
            if "цикл" in err.lower() or "cycle" in err.lower():
                logger.debug("Пропущен цикл: %d -> %d", pred_id, succ_id)
            else:
                logger.debug("Ошибка зависимости %d->%d: %s", pred_id, succ_id, err)
        elif resp and resp.status_code >= 500:
            client.metrics.report_bug(
                f"500 при создании зависимости {pred_id}->{succ_id}: {resp.text[:200]}"
            )

    logger.info("Зависимости: создано %d", created)

    # Проверяем конфликты и выравниваем
    conflicts, aligned = _check_and_align(client, task_ids)

    return {"created": created, "conflicts": conflicts, "aligned": aligned}


def _check_and_align(client, task_ids):
    """Проверяет конфликты дат и выравнивает при необходимости."""
    logger.info("Проверка конфликтов зависимостей...")

    # Загружаем все зависимости
    resp = client.get("/api/dependencies/", params={"context": "plan"})
    data = client.json_ok(resp)
    if not data:
        return 0, 0

    deps = data if isinstance(data, list) else data.get("items", [])
    conflict_tasks = set()
    for dep in deps:
        if dep.get("has_conflict"):
            conflict_tasks.add(dep.get("successor_id"))
            conflict_tasks.add(dep.get("successor"))

    conflicts = len(conflict_tasks)
    aligned = 0

    if conflict_tasks:
        logger.info("Найдено %d задач с конфликтами, выравниваю...", conflicts)
        for tid in conflict_tasks:
            if not tid:
                continue
            resp = client.post(
                f"/api/tasks/{tid}/align_dates/",
                {
                    "cascade": True,
                },
            )
            data = client.json_ok(resp)
            if data and data.get("ok"):
                aligned += data.get("aligned_count", 1)

    logger.info("Конфликты: %d, выровнено: %d", conflicts, aligned)
    return conflicts, aligned
