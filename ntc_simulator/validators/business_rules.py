"""
Business rules validation after simulation.

v2: Updated for scale (10 depts, thousands of tasks).
    PP lock check now expects 403 for locked-only payloads.
"""

import logging

logger = logging.getLogger("simulator")


def check_business_rules(client):
    """
    Validates:
    1. Auto-notices for 'Корректировка документа' tasks with reports
    2. PP field locks (403 on locked-only payload)
    3. Overdue tasks indicator (is_overdue field)
    """
    results = {
        "auto_notices_missing": 0,
        "pp_field_locks_ok": True,
        "overdue_tasks": 0,
        "overdue_flagged_correctly": True,
    }

    results["auto_notices_missing"] = _check_auto_notices(client)
    results["pp_field_locks_ok"] = _check_pp_field_locks(client)
    overdue_count, flag_ok = _check_overdue_tasks(client)
    results["overdue_tasks"] = overdue_count
    results["overdue_flagged_correctly"] = flag_ok

    logger.info("Business rules: %s", results)
    return results


def _check_auto_notices(client):
    """Checks notices exist for 'Корректировка документа' tasks with reports."""
    resp = client.get("/api/tasks/", params={"limit": 5000})
    data = client.json_ok(resp)
    if not data:
        return 0

    tasks = data if isinstance(data, list) else data.get("items", [])
    correction_tasks = [
        t for t in tasks if t.get("task_type") == "Корректировка документа"
    ]

    # Load journal
    resp_j = client.get("/api/journal/", params={"per_page": 5000})
    journal = client.json_ok(resp_j)
    notices = []
    if journal:
        notices = journal if isinstance(journal, list) else journal.get("items", [])

    # Build set of task_ids with notices
    noticed_task_ids = set()
    for n in notices:
        tid = n.get("task_id") or n.get("work_id")
        if tid:
            noticed_task_ids.add(tid)

    missing = 0
    for task in correction_tasks:
        tid = task["id"]
        resp_r = client.get(f"/api/reports/{tid}/")
        reports = client.json_ok(resp_r)
        if not reports:
            continue
        report_list = reports if isinstance(reports, list) else reports.get("items", [])
        if not report_list:
            continue
        # Has reports -> should have notice
        if tid not in noticed_task_ids:
            missing += 1

    if missing > 0:
        client.metrics.report_bug(
            f"Auto-notices: {missing} 'Корректировка' tasks with reports but no notices"
        )
    return missing


def _check_pp_field_locks(client):
    """Checks that PP tasks have locked fields (403 on locked-only payload)."""
    resp = client.get("/api/tasks/", params={"limit": 5000})
    data = client.json_ok(resp)
    if not data:
        return True

    tasks = data if isinstance(data, list) else data.get("items", [])
    pp_tasks = [t for t in tasks if t.get("from_pp")]

    if not pp_tasks:
        return True

    # Try to update locked field only -- should get 403
    task = pp_tasks[0]
    tid = task["id"]
    resp = client.put(
        f"/api/tasks/{tid}/",
        {
            "work_name": "TEST LOCK CHECK",
        },
    )
    if resp and resp.status_code == 403:
        # Correct: locked fields rejected
        return True
    elif resp and resp.status_code < 300:
        # Lock not working
        client.metrics.report_bug(
            f"PP lock: work_name updated for PP task {tid} (expected 403, got {resp.status_code})"
        )
        return False
    # Other error (404, 409, etc.) -- not a lock issue
    return True


def _check_overdue_tasks(client):
    """Counts overdue tasks and checks is_overdue flag correctness."""
    import datetime

    today = datetime.date.today().isoformat()

    resp = client.get("/api/tasks/", params={"limit": 5000})
    data = client.json_ok(resp)
    if not data:
        return 0, True

    tasks = data if isinstance(data, list) else data.get("items", [])
    overdue = 0
    flag_mismatches = 0

    for task in tasks:
        date_end = task.get("date_end", "")
        deadline = task.get("deadline", "")
        effective = date_end or deadline
        is_actually_overdue = bool(effective and effective < today)

        if is_actually_overdue:
            overdue += 1

        # Check is_overdue flag
        api_flag = task.get("is_overdue", False)
        if api_flag != is_actually_overdue:
            flag_mismatches += 1

    if flag_mismatches > 0:
        client.metrics.report_bug(f"is_overdue flag mismatch: {flag_mismatches} tasks")

    return overdue, flag_mismatches == 0
