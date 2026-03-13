"""
Модуль для работы с отчётами и извещениями (вспомогательный).
Основная логика отчётов/извещений — в monthly.py.
Здесь — финальная проверка автосоздания извещений.
"""
import logging

logger = logging.getLogger('simulator')


def verify_auto_notices(client):
    """
    Проверяет что для всех задач с типом 'Корректировка документа',
    имеющих отчёты, созданы извещения.
    """
    logger.info("Проверка автосоздания извещений...")

    # Загружаем все задачи
    resp = client.get('/api/tasks/', params={'limit': 5000})
    data = client.json_ok(resp)
    if not data:
        return 0

    tasks = data if isinstance(data, list) else data.get('items', [])
    correction_tasks = [
        t for t in tasks if t.get('task_type') == 'Корректировка документа'
    ]

    if not correction_tasks:
        logger.info("Нет задач типа 'Корректировка' — пропуск проверки")
        return 0

    missing = 0
    for task in correction_tasks:
        tid = task['id']
        # Проверяем наличие отчётов
        resp = client.get(f'/api/reports/{tid}/')
        reports = client.json_ok(resp)
        if not reports:
            continue
        report_list = reports if isinstance(reports, list) else reports.get('items', [])
        if not report_list:
            continue

        # Должно быть извещение для каждого отчёта
        # (упрощённая проверка — хотя бы одно извещение на задачу)
        resp_j = client.get('/api/journal/', params={'per_page': 1000})
        journal = client.json_ok(resp_j)
        if not journal:
            continue
        notices = journal if isinstance(journal, list) else journal.get('items', [])

        # Ищем извещение, связанное с этой задачей
        has_notice = any(
            n.get('work_id') == tid or n.get('task_id') == tid
            for n in notices
        )
        if not has_notice and report_list:
            missing += 1
            client.metrics.report_bug(
                f"Нет извещения для задачи {tid} типа 'Корректировка документа' "
                f"(отчётов: {len(report_list)})")

    logger.info("Проверка извещений: %d задач без извещений из %d",
                missing, len(correction_tasks))
    return missing
