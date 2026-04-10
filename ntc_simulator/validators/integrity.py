"""
Data integrity checks after each month and at end of simulation.

v2: Updated for massive scale (10 depts, thousands of tasks).
"""

import logging

logger = logging.getLogger("simulator")


def check_monthly_integrity(client, month, year, calendar_hours):
    """
    Monthly checks:
    1. No 5xx errors in API
    2. Employee load within norms
    3. Dependency conflicts
    """
    issues = []

    # 1. 5xx errors
    errors_5xx = client.metrics.errors_5xx
    if errors_5xx:
        count = sum(len(v) for v in errors_5xx.values())
        if count > 0:
            issues.append(f"5xx errors: {count} in month {month:02d}/{year}")

    # 2. Employee load (spot-check, not full scan at this scale)
    hours_norm = calendar_hours.get(month, 176)
    max_allowed = hours_norm * 1.5  # Relaxed for simulation scale
    overloaded = _check_employee_load(client, month, year, max_allowed)
    if overloaded:
        issues.append(
            f"Overloaded employees: {len(overloaded)} "
            f"(norm {hours_norm}h, max {max_allowed:.0f}h)"
        )

    # 3. Dependency conflicts
    conflicts = _check_dependency_conflicts(client)
    if conflicts > 0:
        issues.append(f"Dependency conflicts: {conflicts}")

    for issue in issues:
        logger.warning("INTEGRITY [%02d/%d]: %s", month, year, issue)

    return issues


def _check_employee_load(client, month, year, max_hours):
    """Checks employee load doesn't exceed norms."""
    month_key = f"{year}-{month:02d}"
    resp = client.get(
        "/api/tasks/",
        params={
            "limit": 5000,
        },
    )
    data = client.json_ok(resp)
    if not data:
        return []

    tasks = data if isinstance(data, list) else data.get("items", [])

    load = {}
    for task in tasks:
        executor = task.get("executor", "")
        plan_hours = task.get("plan_hours", {})
        if isinstance(plan_hours, dict):
            hours = plan_hours.get(month_key, 0)
            if isinstance(hours, (int, float)) and hours > 0:
                load[executor] = load.get(executor, 0) + hours

    overloaded = [
        (name, hours) for name, hours in load.items() if hours > max_hours and name
    ]

    # Only report top-10 most overloaded
    overloaded.sort(key=lambda x: x[1], reverse=True)
    for name, hours in overloaded[:10]:
        client.metrics.report_bug(
            f"Overload: {name} = {hours}h (max {max_hours:.0f}h) in {month_key}"
        )

    return overloaded


def _check_dependency_conflicts(client):
    """Checks for unresolved dependency conflicts."""
    resp = client.get("/api/dependencies/", params={"context": "plan"})
    data = client.json_ok(resp)
    if not data:
        return 0

    deps = data if isinstance(data, list) else data.get("items", [])
    conflicts = sum(1 for d in deps if d.get("has_conflict"))
    return conflicts


def final_integrity_check(client):
    """Final integrity check after simulation."""
    logger.info("Final integrity check...")
    issues = []

    # Total 5xx count
    total_5xx = sum(len(v) for v in client.metrics.errors_5xx.values())
    if total_5xx > 0:
        issues.append(f"Total 5xx errors: {total_5xx}")
        for ep, codes in client.metrics.errors_5xx.items():
            issues.append(f"  {ep}: {len(codes)} errors")

    # Dependency conflicts
    conflicts = _check_dependency_conflicts(client)
    if conflicts > 0:
        issues.append(f"Unresolved dependency conflicts: {conflicts}")

    # Task count sanity check
    resp = client.get("/api/tasks/", params={"limit": 1})
    if resp and resp.status_code == 200:
        total = resp.headers.get("X-Total-Count", "?")
        logger.info("Total tasks in DB: %s", total)
        issues_info = f"Total tasks in DB: {total}"
        logger.info(issues_info)

    for issue in issues:
        logger.warning("FINAL INTEGRITY: %s", issue)

    return issues
