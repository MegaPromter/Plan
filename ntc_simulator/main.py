"""
NTC Simulator entry point.
Orchestrates: setup -> planning -> dependencies -> monthly cycle ->
concurrency -> validation -> report.

v2: 10 departments, 500-1000 tasks/dept/month, deadline misses,
    employee reports, massive scale.
"""
import argparse
import logging
import os
import random
import sys
import time
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import ApiClient, ApiMetrics
from setup import setup_calendar, setup_org_structure, CALENDAR_2026
from scenarios.planning import create_projects, create_pp_plans, create_pp_rows, sync_pp_to_sp
from scenarios.dependencies import create_dependencies
from scenarios.monthly import simulate_month
from scenarios.concurrency import test_concurrency
from validators.integrity import check_monthly_integrity, final_integrity_check
from validators.business_rules import check_business_rules
from report_generator import generate_report


def setup_logging():
    """Configure logging with UTF-8 support."""
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    log_format = '%(asctime)s [%(levelname)s] %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler('simulation.log', encoding='utf-8', mode='w'),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def load_config(path='sim_config.yaml'):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description='NTC Simulator v2')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--config', default='sim_config.yaml', help='Config path')
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger('simulator')
    logger.info("=" * 70)
    logger.info("  NTC SIMULATOR v2 -- 10 departments, 500-1000 tasks/dept/month")
    logger.info("=" * 70)
    logger.info("Seed: %d", args.seed)

    config = load_config(args.config)
    rng = random.Random(args.seed)

    base_url = config['server']['base_url']
    admin_user = config['admin']['username']
    admin_pass = config['admin']['password']

    metrics = ApiMetrics()
    client = ApiClient(base_url, metrics)

    t_start = time.time()

    # -- Phase 0: Login admin --------------------------------------------------
    logger.info("Phase 0: Admin login...")
    if not client.login(admin_user, admin_pass):
        logger.error("FATAL: admin login failed")
        sys.exit(1)

    # -- Phase 1: Setup --------------------------------------------------------
    logger.info("Phase 1: Org structure (10 depts, ~300+ employees)...")
    year = config.get('simulation', {}).get('year', 2026)

    setup_calendar(client, year)
    org_data = setup_org_structure(client, rng, config)
    employees = org_data['employees']

    counters = {
        'employees': len(employees),
        'departments': len(org_data['departments']),
        'calendar_records': 12,
    }

    # Stats per department
    for dc, cc, scs in org_data['departments']:
        dept_emps = [e for e in employees if e['dept'] == dc]
        counters[f'dept_{dc}_employees'] = len(dept_emps)

    logger.info("Setup done: %d employees, %d departments",
                counters['employees'], counters['departments'])

    # -- Phase 2: Planning (projects, PP plans, PP rows, sync) -----------------
    logger.info("Phase 2: Planning...")
    projects = create_projects(client, rng, config)
    pp_plans = create_pp_plans(client, rng, projects, config)
    pp_rows = create_pp_rows(client, rng, pp_plans, org_data, config)
    synced = sync_pp_to_sp(client, pp_plans)

    counters['projects'] = len(projects)
    counters['pp_plans'] = len(pp_plans)
    counters['pp_rows'] = len(pp_rows)
    counters['synced_to_sp'] = synced

    # -- Phase 3: Dependencies -------------------------------------------------
    logger.info("Phase 3: Dependencies...")
    dep_results = create_dependencies(client, rng, config)
    counters['dependencies'] = dep_results['created']
    counters['dep_conflicts_initial'] = dep_results['conflicts']
    counters['dep_aligned_initial'] = dep_results['aligned']

    # -- Phase 4: Monthly simulation (12 months) -------------------------------
    logger.info("Phase 4: Monthly simulation (12 months x 10 depts)...")
    monthly_stats = {}
    integrity_issues = {}

    for month in range(1, 13):
        month_start = time.time()

        stats = simulate_month(
            client, rng, month, year, org_data, pp_plans, config, metrics)
        monthly_stats[month] = stats

        # Integrity check
        issues = check_monthly_integrity(client, month, year, CALENDAR_2026)
        if issues:
            integrity_issues[month] = issues

        month_elapsed = time.time() - month_start
        total_created = stats['pp_tasks_created'] + stats['sp_tasks_created']
        logger.info("Month %02d done in %.1fs: %d tasks, %d reports, %d overdue",
                    month, month_elapsed, total_created,
                    stats['reports_created'], stats['deadlines_missed'])

    # Aggregate monthly stats
    total_monthly = {}
    for stats in monthly_stats.values():
        for key, val in stats.items():
            total_monthly[key] = total_monthly.get(key, 0) + val
    counters.update({
        'vacations': total_monthly.get('vacations_created', 0),
        'pp_tasks_created_monthly': total_monthly.get('pp_tasks_created', 0),
        'sp_tasks_created_monthly': total_monthly.get('sp_tasks_created', 0),
        'tasks_updated': total_monthly.get('tasks_updated', 0),
        'deadlines_missed': total_monthly.get('deadlines_missed', 0),
        'reports': total_monthly.get('reports_created', 0),
        'notices_processed': total_monthly.get('notices_processed', 0),
        'pp_monthly_changes': total_monthly.get('pp_changes', 0),
    })

    total_tasks = (counters['pp_rows'] +
                   counters.get('pp_tasks_created_monthly', 0) +
                   counters.get('sp_tasks_created_monthly', 0))
    logger.info("Total tasks created over year: %d (PP init: %d, PP monthly: %d, SP: %d)",
                total_tasks, counters['pp_rows'],
                counters.get('pp_tasks_created_monthly', 0),
                counters.get('sp_tasks_created_monthly', 0))

    # -- Phase 5: Concurrency --------------------------------------------------
    logger.info("Phase 5: Concurrency tests...")
    concurrency_results = test_concurrency(
        base_url, employees, metrics, config)

    # -- Phase 6: Final checks -------------------------------------------------
    logger.info("Phase 6: Final validation...")
    final_issues = final_integrity_check(client)
    if final_issues:
        integrity_issues['final'] = final_issues

    business_rules = check_business_rules(client)

    # -- Phase 7: Report -------------------------------------------------------
    elapsed = time.time() - t_start
    logger.info("Phase 7: Generating report...")
    report = generate_report(
        metrics, counters, monthly_stats, integrity_issues,
        business_rules, concurrency_results, elapsed)

    logger.info("Simulation completed in %s", report['elapsed_human'])
    logger.info("Verdict: %s", report['verdict'])

    return report


if __name__ == '__main__':
    main()
