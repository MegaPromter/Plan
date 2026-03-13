"""
Module 7: Final report generation.

v2: Extended metrics for 10 depts, per-month breakdown, deadline misses.
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger('simulator')


def generate_report(metrics, counters, monthly_stats, integrity_issues,
                    business_rules, concurrency_results, elapsed_sec):
    """Generates final report and saves to simulation_report.json."""
    report = {
        'simulation_date': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed_sec, 1),
        'elapsed_human': _format_duration(elapsed_sec),

        'counters': counters,
        'api': metrics.summary(),
        'monthly_stats': monthly_stats,
        'integrity_issues': integrity_issues,
        'business_rules': business_rules,
        'concurrency': concurrency_results,
        'verdict': _verdict(metrics, integrity_issues, business_rules),
    }

    path = 'simulation_report.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info("Report saved: %s", path)

    _print_summary(report)
    return report


def _format_duration(sec):
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}min {s}s"
    return f"{m}min {s}s"


def _verdict(metrics, issues, rules):
    """Overall stability verdict."""
    total_5xx = sum(len(v) for v in metrics.errors_5xx.values())
    bugs = len(metrics.bugs)
    flat_issues = []
    for month_issues in issues.values():
        if isinstance(month_issues, list):
            flat_issues.extend(month_issues)

    if total_5xx > 0:
        return f"FAIL -- {total_5xx} 5xx errors"
    if bugs > 10:
        return f"WARNING -- {bugs} bugs found"
    if flat_issues:
        return f"WARNING -- {len(flat_issues)} integrity issues"
    return "PASS -- simulation completed successfully"


def _print_summary(report):
    """Pretty-print summary to console."""
    print("\n" + "=" * 70)
    print("  NTC SIMULATOR v2 -- RESULTS")
    print("=" * 70)
    print(f"  Duration: {report['elapsed_human']}")
    print(f"  Verdict:  {report['verdict']}")
    print()

    c = report['counters']
    print("  CREATED OBJECTS:")
    print(f"    Employees:            {c.get('employees', 0)}")
    print(f"    Departments:          {c.get('departments', 0)}")
    print(f"    Projects:             {c.get('projects', 0)}")
    print(f"    PP plans:             {c.get('pp_plans', 0)}")
    print(f"    PP rows (initial):    {c.get('pp_rows', 0)}")
    print(f"    PP tasks (monthly):   {c.get('pp_tasks_created_monthly', 0)}")
    print(f"    SP tasks (monthly):   {c.get('sp_tasks_created_monthly', 0)}")
    total = (c.get('pp_rows', 0) +
             c.get('pp_tasks_created_monthly', 0) +
             c.get('sp_tasks_created_monthly', 0))
    print(f"    TOTAL tasks:          {total}")
    print(f"    Dependencies:         {c.get('dependencies', 0)}")
    print(f"    Reports:              {c.get('reports', 0)}")
    print(f"    Deadline misses:      {c.get('deadlines_missed', 0)}")
    print(f"    Vacations:            {c.get('vacations', 0)}")
    print(f"    Notices processed:    {c.get('notices_processed', 0)}")
    print()

    # Per-month breakdown
    print("  MONTHLY BREAKDOWN:")
    print(f"    {'Mon':>4} {'PP':>6} {'SP':>6} {'Total':>7} {'Reports':>8} {'Overdue':>8}")
    print(f"    {'---':>4} {'---':>6} {'---':>6} {'-----':>7} {'-------':>8} {'-------':>8}")
    for m in range(1, 13):
        ms = report['monthly_stats'].get(m, report['monthly_stats'].get(str(m), {}))
        pp = ms.get('pp_tasks_created', 0)
        sp = ms.get('sp_tasks_created', 0)
        reps = ms.get('reports_created', 0)
        over = ms.get('deadlines_missed', 0)
        print(f"    {m:>4} {pp:>6} {sp:>6} {pp + sp:>7} {reps:>8} {over:>8}")
    print()

    api = report['api']
    print(f"  API: {api['total_requests']} total requests")
    try:
        e4 = sum(api['errors_4xx'].values()) if api['errors_4xx'] else 0
    except (TypeError, AttributeError):
        e4 = 0
    try:
        e5 = sum(api['errors_5xx'].values()) if api['errors_5xx'] else 0
    except (TypeError, AttributeError):
        e5 = 0
    print(f"    4xx errors: {e4}")
    print(f"    5xx errors: {e5}")
    print()

    if api['bugs']:
        print(f"  BUGS ({len(api['bugs'])}):")
        for b in api['bugs'][:30]:
            print(f"    [!] {b}")
        if len(api['bugs']) > 30:
            print(f"    ... and {len(api['bugs']) - 30} more")
    print()

    print("  BUSINESS RULES:")
    br = report['business_rules']
    for key, val in br.items():
        print(f"    {key}: {val}")
    print()

    conc = report['concurrency']
    if conc:
        print("  CONCURRENCY:")
        for key, val in conc.items():
            print(f"    {key}: {val}")
    print()

    print("=" * 70)
