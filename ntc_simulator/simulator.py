"""
Симулятор работы НТЦ-2Ц — годовой цикл
========================================
Симулирует работу подразделения в течение 12 месяцев:
  - 115 сотрудников в 10 отделах
  - 100+ новых задач ежемесячно
  - Отпуска сотрудников (план vs факт)
  - Ошибки планирования: перегруз, недогруз
  - Невыполнение в срок -> сдвиг вправо
  - Смена исполнителя при перегрузе или увольнении
  - Итоговый отчёт за год

Запуск: python simulator.py
"""

import io
import random
import sys
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

# UTF-8 вывод для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

random.seed(2026)

# ── Константы ──────────────────────────────────────────────────────────────────

YEAR = 2026
MONTH_NORM = 168  # норма часов/мес
OVERLOAD_THR = MONTH_NORM * 1.10  # >110%
MIN_TASKS_MONTH = 100  # минимум новых задач в месяц
MAX_TASKS_MONTH = 140

# Вероятности событий
P_OVERDUE = 0.18  # вероятность что задача не выполнена в срок
P_EXECUTOR_SWAP = 0.30  # вероятность смены исполнителя при сдвиге
P_VACATION_SICK = 0.05  # вероятность больничного вместо отпуска

MONTHS_RU = [
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

# ── Структура НТЦ-2Ц ──────────────────────────────────────────────────────────

DEPT_SECTORS = {
    "021": ["021-110", "021-120", "021-130"],
    "022": ["022-100", "022-200", "022-300"],
    "024": ["024-110", "024-120"],
    "027": ["027-100", "027-200", "027-300"],
    "028": ["028-110", "028-120"],
    "029": ["029-100", "029-200"],
    "082": ["082-110", "082-120", "082-130"],
    "084": ["084-100", "084-200"],
    "086": ["086-110", "086-120"],
    "301": ["301-100", "301-200", "301-300"],
}

LAST_NAMES = [
    "Иванов",
    "Петров",
    "Сидоров",
    "Козлов",
    "Новиков",
    "Морозов",
    "Лебедев",
    "Соколов",
    "Попов",
    "Волков",
    "Смирнов",
    "Михайлов",
    "Фёдоров",
    "Зайцев",
    "Захаров",
    "Орлов",
    "Кузнецов",
    "Тихонов",
    "Беляев",
    "Громов",
    "Ермаков",
    "Жуков",
    "Кириллов",
    "Ларин",
    "Макаров",
    "Нестеров",
    "Осипов",
    "Панин",
    "Рябов",
    "Сорокин",
    "Титов",
    "Уваров",
    "Фомин",
    "Харитонов",
    "Цветков",
    "Чернов",
    "Шаров",
    "Щербаков",
    "Юрьев",
    "Якушев",
    "Абрамов",
    "Борисов",
    "Виноградов",
    "Герасимов",
    "Данилов",
    "Егоров",
    "Журавлёв",
    "Зимин",
    "Исаев",
    "Карпов",
    "Лысенко",
    "Мельников",
    "Назаров",
    "Обухов",
    "Павлов",
    "Родионов",
    "Суворов",
    "Третьяков",
    "Ушаков",
    "Филиппов",
    "Храмов",
    "Цыганков",
]

FIRST_NAMES_M = [
    "Александр",
    "Алексей",
    "Андрей",
    "Антон",
    "Артём",
    "Борис",
    "Василий",
    "Виктор",
    "Владимир",
    "Дмитрий",
    "Евгений",
    "Иван",
    "Игорь",
    "Кирилл",
    "Константин",
    "Максим",
    "Михаил",
    "Николай",
    "Олег",
    "Павел",
    "Роман",
    "Сергей",
    "Степан",
    "Юрий",
]

PATRONYMICS_M = [
    "Александрович",
    "Алексеевич",
    "Андреевич",
    "Антонович",
    "Борисович",
    "Васильевич",
    "Викторович",
    "Владимирович",
    "Дмитриевич",
    "Евгеньевич",
    "Иванович",
    "Игоревич",
    "Кириллович",
    "Константинович",
    "Максимович",
    "Михайлович",
    "Николаевич",
    "Олегович",
    "Павлович",
    "Романович",
    "Сергеевич",
    "Степанович",
    "Юрьевич",
]

POSITIONS = [
    "Инженер-конструктор 1 кат.",
    "Инженер-конструктор 2 кат.",
    "Инженер-конструктор 3 кат.",
    "Ведущий инженер-конструктор",
    "Главный специалист",
    "Специалист 1 кат.",
    "Техник-конструктор 1 кат.",
]

TASK_NAMES = [
    "Разработка конструкторской документации",
    "Согласование технического задания",
    "Проведение технических расчётов",
    "Оформление отчёта по НИР",
    "Участие в совещании рабочей группы",
    "Разработка программы испытаний",
    "Анализ входной документации",
    "Корректировка чертежей по замечаниям",
    "Выпуск извещения об изменении",
    "Проверка расчётной документации",
    "Разработка технического предложения",
    "Составление сметы на работы",
    "Проведение патентного поиска",
    "Подготовка презентации для заказчика",
    "Разработка методики испытаний",
    "Оформление акта выполненных работ",
    "Анализ результатов испытаний",
    "Разработка эскизного проекта",
    "Технический надзор за производством",
    "Согласование со смежными отделами",
    "Подготовка технического отчёта",
    "Разработка рабочей документации",
    "Оформление спецификации",
    "Проведение нормоконтроля",
    "Участие в защите технического проекта",
    "Разработка ТЗ на составную часть",
    "Проверка соответствия требованиям ГОСТ",
    "Подготовка материалов к тендеру",
    "Разработка программы и методики ПСИ",
    "Экспертиза входящей документации",
]

# ── Модели данных ──────────────────────────────────────────────────────────────


@dataclass
class Employee:
    id: int
    last_name: str
    first_name: str
    patronymic: str
    dept: str
    sector: str
    role: str  # head / deputy / user
    position: str
    monthly_norm: int = MONTH_NORM

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name} {self.patronymic}"

    @property
    def short_name(self) -> str:
        return f"{self.last_name} {self.first_name[0]}.{self.patronymic[0]}."


@dataclass
class VacationRecord:
    employee: Employee
    month: int
    days: int
    vac_type: str  # annual / sick


@dataclass
class Task:
    id: int
    name: str
    executor: Employee
    dept: str
    plan_hours: float
    month_planned: int  # месяц, в котором запланирована
    month_actual: int  # месяц фактического выполнения
    status: str = "planned"  # planned / done / overdue / shifted / reassigned / deleted
    shift_count: int = 0  # сколько раз сдвигалась вправо
    prev_executor: Optional[str] = None  # ФИО предыдущего исполнителя (при смене)

    def __repr__(self):
        ex = self.executor.short_name
        prev = f" (был: {self.prev_executor})" if self.prev_executor else ""
        return (
            f"[{self.id:04d}] {self.name[:38]:<38} | {ex:<18}{prev} "
            f"| пл.{self.month_planned:02d}->факт.{self.month_actual:02d} "
            f"| {self.plan_hours:.0f}ч | {self.status}"
        )


# ── Генерация сотрудников ──────────────────────────────────────────────────────


def generate_employees() -> List[Employee]:
    employees = []
    emp_id = 1
    used_names = set()

    for dept, sectors in DEPT_SECTORS.items():
        count = random.randint(10, 14)
        for i in range(count):
            for _ in range(200):
                ln = random.choice(LAST_NAMES)
                fn = random.choice(FIRST_NAMES_M)
                pn = random.choice(PATRONYMICS_M)
                key = (ln, fn[0], pn[0])
                if key not in used_names:
                    used_names.add(key)
                    break
            sector = random.choice(sectors)
            if i == 0:
                role, pos = "head", "Начальник отдела"
            elif i == 1:
                role, pos = "deputy", "Заместитель начальника отдела"
            else:
                role, pos = "user", random.choice(POSITIONS)
            employees.append(
                Employee(
                    id=emp_id,
                    last_name=ln,
                    first_name=fn,
                    patronymic=pn,
                    dept=dept,
                    sector=sector,
                    role=role,
                    position=pos,
                )
            )
            emp_id += 1
    return employees


# ── Генерация плана отпусков ───────────────────────────────────────────────────


def generate_vacation_plan(
    employees: List[Employee],
) -> Dict[int, List[VacationRecord]]:
    """
    Каждый сотрудник берёт отпуск 1 раз в год (14–28 дней).
    Летом вероятность выше.
    Возвращает dict: month -> [VacationRecord, ...]
    """
    month_weights = [1, 1, 2, 3, 5, 10, 14, 14, 8, 4, 2, 1]
    plan: Dict[int, List[VacationRecord]] = defaultdict(list)

    for emp in employees:
        month = random.choices(range(1, 13), weights=month_weights, k=1)[0]
        days = random.randint(14, 28)
        vtype = "sick" if random.random() < P_VACATION_SICK else "annual"
        rec = VacationRecord(employee=emp, month=month, days=days, vac_type=vtype)
        plan[month].append(rec)

    return plan


def get_vacation_hours(
    emp: Employee, month: int, vacation_plan: Dict[int, List[VacationRecord]]
) -> float:
    """Сколько рабочих часов «съедает» отпуск сотрудника в данном месяце."""
    for rec in vacation_plan.get(month, []):
        if rec.employee.id == emp.id:
            # ~8 ч/день рабочих
            return min(rec.days * 8, MONTH_NORM)
    return 0.0


# ── Генерация задач месяца ────────────────────────────────────────────────────

_task_id = 0


def next_id() -> int:
    global _task_id
    _task_id += 1
    return _task_id


def generate_month_tasks(
    employees: List[Employee],
    month: int,
    vacation_plan: Dict[int, List[VacationRecord]],
) -> List[Task]:
    """Генерирует 100–140 новых задач на месяц, распределяя по сотрудникам."""
    count = random.randint(MIN_TASKS_MONTH, MAX_TASKS_MONTH)
    tasks = []

    # Доступные сотрудники (не в отпуске весь месяц)
    available = []
    for emp in employees:
        vac_h = get_vacation_hours(emp, month, vacation_plan)
        effective = MONTH_NORM - vac_h
        if effective > 20:  # минимум 20 ч свободного времени
            available.append((emp, effective))

    if not available:
        available = [(e, MONTH_NORM) for e in employees]

    for _ in range(count):
        emp, effective = random.choice(available)
        # Часы задачи: 4–40 ч
        hours = round(random.uniform(4, min(40, effective)), 1)
        tasks.append(
            Task(
                id=next_id(),
                name=random.choice(TASK_NAMES),
                executor=emp,
                dept=emp.dept,
                plan_hours=hours,
                month_planned=month,
                month_actual=month,
            )
        )
    return tasks


# ── Расчёт нагрузки ────────────────────────────────────────────────────────────


def calc_load(
    tasks: List[Task], month: int, include_done: bool = False
) -> Dict[int, float]:
    """
    Суммарные часы по исполнителям за указанный месяц.
    include_done=True — включать выполненные задачи (для статистики нагрузки).
    include_done=False — только активные (для балансировки, по умолчанию).
    """
    load: Dict[int, float] = defaultdict(float)
    excluded = {"deleted"} if include_done else {"deleted", "done"}
    for t in tasks:
        if t.month_actual == month and t.status not in excluded:
            load[t.executor.id] += t.plan_hours
    return dict(load)


# ── Симуляция месяца ──────────────────────────────────────────────────────────


def simulate_month(
    month: int,
    all_tasks: List[Task],
    employees: List[Employee],
    vacation_plan: Dict[int, List[VacationRecord]],
    stats: dict,
):
    """
    Выполняет симуляцию одного месяца:
    1. Добавляет новые задачи
    2. Выявляет и устраняет перегруз/недогруз
    3. Симулирует выполнение / невыполнение задач
    4. Сдвигает просроченные задачи вправо (со сменой исполнителя или без)
    """
    month_name = MONTHS_RU[month]
    print(f"\n{'='*80}")
    print(f"  МЕСЯЦ {month:02d}: {month_name} {YEAR}")
    print(f"{'='*80}")

    # --- Отпуска в этом месяце ---
    vac_this_month = vacation_plan.get(month, [])
    if vac_this_month:
        print(f"\n  Отпуска ({len(vac_this_month)} чел.):", end=" ")
        names = [r.employee.short_name for r in vac_this_month[:5]]
        suffix = f" и ещё {len(vac_this_month)-5}..." if len(vac_this_month) > 5 else ""
        print(", ".join(names) + suffix)

    # --- Новые задачи ---
    new_tasks = generate_month_tasks(employees, month, vacation_plan)
    all_tasks.extend(new_tasks)
    print(f"  Новых задач добавлено: {len(new_tasks)}")
    stats["tasks_created"] += len(new_tasks)

    # --- Балансировка нагрузки (ДО симуляции выполнения, пока задачи активны) ---
    # БАГ-ФИКС 1: calc_load без include_done — считает только активные (не done/deleted)
    # БАГ-ФИКС 2: порог недогруза поднят до 85% нормы (было 60% — слишком низко)
    load = calc_load(all_tasks, month)
    overloaded = [
        (e, load.get(e.id, 0)) for e in employees if load.get(e.id, 0) > OVERLOAD_THR
    ]
    underloaded = [
        (e, load.get(e.id, 0))
        for e in employees
        if 0 < load.get(e.id, 0) < MONTH_NORM * 0.85
    ]

    adj_count = 0
    for emp, hours in overloaded:
        excess = hours - MONTH_NORM
        my_tasks = [
            t
            for t in all_tasks
            if t.executor.id == emp.id
            and t.month_actual == month
            and t.status not in ("deleted", "done")
        ]
        if not my_tasks:
            continue
        my_tasks.sort(key=lambda t: t.plan_hours, reverse=True)
        victim = my_tasks[0]

        if underloaded and random.random() < 0.5:
            # Переназначаем задачу на недогруженного сотрудника
            new_exec, _ = random.choice(underloaded)
            victim.prev_executor = emp.short_name
            victim.executor = new_exec
            victim.status = "reassigned"
            stats["reassigned"] += 1
        else:
            # Уменьшаем часы у самой тяжёлой задачи
            victim.plan_hours = max(2.0, round(victim.plan_hours - excess, 1))
            victim.status = "adjusted"
        adj_count += 1

    # Недогруженным добавляем часы к последней задаче
    for emp, hours in underloaded:
        deficit = MONTH_NORM - hours
        my_tasks = [
            t
            for t in all_tasks
            if t.executor.id == emp.id
            and t.month_actual == month
            and t.status not in ("deleted", "done")
        ]
        if my_tasks:
            my_tasks[-1].plan_hours = round(my_tasks[-1].plan_hours + deficit * 0.5, 1)
            my_tasks[-1].status = "adjusted"
            adj_count += 1

    if overloaded or underloaded:
        print(
            f"  Балансировка: перегруз {len(overloaded)} чел., "
            f"недогруз {len(underloaded)} чел. -> скорректировано {adj_count} задач"
        )
        stats["balance_corrections"] += adj_count

    # --- Симуляция выполнения ---
    month_tasks = [
        t for t in all_tasks if t.month_actual == month and t.status not in ("deleted",)
    ]

    done_count = 0
    overdue_count = 0
    shifted_count = 0
    swap_count = 0

    for t in month_tasks:
        if t.status == "done":
            continue

        # Задача не выполнена в срок?
        is_overdue = random.random() < P_OVERDUE

        # Сотрудник в отпуске в этот месяц?
        vac_h = get_vacation_hours(t.executor, month, vacation_plan)
        if vac_h > MONTH_NORM * 0.5:
            # Высокая вероятность невыполнения если сотрудник большую часть в отпуске
            is_overdue = random.random() < 0.65

        if is_overdue:
            overdue_count += 1
            stats["overdue_total"] += 1

            # Сдвиг вправо (если не декабрь)
            if month < 12:
                t.month_actual = month + 1
                t.status = "shifted"
                t.shift_count += 1
                shifted_count += 1
                stats["shifted_total"] += 1

                # Смена исполнителя?
                if random.random() < P_EXECUTOR_SWAP:
                    # Найдём сотрудника из того же отдела с меньшей нагрузкой
                    same_dept = [
                        e
                        for e in employees
                        if e.dept == t.dept and e.id != t.executor.id
                    ]
                    if same_dept:
                        next_load = calc_load(all_tasks, month + 1)
                        same_dept.sort(key=lambda e: next_load.get(e.id, 0))
                        new_exec = same_dept[0]
                        t.prev_executor = t.executor.short_name
                        t.executor = new_exec
                        t.status = "reassigned+shifted"
                        swap_count += 1
                        stats["executor_swaps"] += 1
            else:
                # Декабрь — задача просрочена, переносится на следующий год
                t.status = "overdue"
        else:
            t.status = "done"
            done_count += 1
            stats["done_total"] += 1

    print(
        f"  Выполнено: {done_count}  |  Просрочено: {overdue_count}  "
        f"|  Сдвинуто: {shifted_count}  |  Смена исполнителя: {swap_count}"
    )

    # --- Итоговая нагрузка месяца ---
    # БАГ-ФИКС 3: include_done=True — считаем фактически отработанные часы
    load_after = calc_load(all_tasks, month, include_done=True)
    avg = sum(load_after.values()) / len(employees) if employees else 0
    over_final = sum(1 for e in employees if load_after.get(e.id, 0) > OVERLOAD_THR)
    under_final = sum(
        1 for e in employees if 0 < load_after.get(e.id, 0) < MONTH_NORM * 0.85
    )
    print(
        f"  Средняя нагрузка: {avg:.1f} ч  |  "
        f"Перегруз: {over_final} чел.  |  Недогруз: {under_final} чел."
    )

    stats["months_processed"] += 1
    return new_tasks


# ── Итоговый годовой отчёт ────────────────────────────────────────────────────


def print_annual_report(
    all_tasks: List[Task],
    employees: List[Employee],
    vacation_plan: Dict[int, List[VacationRecord]],
    stats: dict,
):
    print(f"\n{'='*80}")
    print(f"  ГОДОВОЙ ОТЧЁТ НТЦ-2Ц — {YEAR}")
    print(f"{'='*80}")

    # Общая статистика задач
    total = len(all_tasks)
    done = sum(1 for t in all_tasks if t.status == "done")
    shifted = sum(1 for t in all_tasks if "shifted" in t.status)
    reass = sum(1 for t in all_tasks if "reassigned" in t.status)
    overdue = sum(1 for t in all_tasks if t.status == "overdue")
    adjusted = sum(1 for t in all_tasks if t.status == "adjusted")

    print(
        f"""
  ЗАДАЧИ ЗА ГОД:
    Всего создано          : {total}
    Выполнено              : {done}  ({done/total*100:.1f}%)
    Сдвинуто вправо        : {stats['shifted_total']}
    Смена исполнителя      : {stats['executor_swaps']}
    Скорректировано часов  : {adjusted}
    Просрочено (дек.)      : {overdue}
    Балансировок нагрузки  : {stats['balance_corrections']}
"""
    )

    # Статистика по месяцам
    # БАГ-ФИКС 4: считаем выполнение только тех задач, что были запланированы в месяце
    # и выполнены именно в этом же месяце (не сдвинутые в другой)
    print(f"  ЗАДАЧИ ПО МЕСЯЦАМ:")
    print(
        f"  {'Месяц':<12} {'Создано':>8} {'Вып.в срок':>11} {'Сдвинуто':>10} {'Просрочено':>11}"
    )
    print(f"  {'-'*58}")
    for m in range(1, 13):
        m_tasks = [t for t in all_tasks if t.month_planned == m]
        # Выполнено В СРОК = done И не сдвигалось (month_actual == month_planned)
        m_done = sum(1 for t in m_tasks if t.status == "done" and t.month_actual == m)
        # Сдвинуто = было запланировано в m, но выполняется позже
        m_shift = sum(1 for t in m_tasks if "shifted" in t.status)
        m_overdue = sum(1 for t in m_tasks if t.status == "overdue")
        pct = m_done / len(m_tasks) * 100 if m_tasks else 0
        print(
            f"  {MONTHS_RU[m]:<12} {len(m_tasks):>8} {m_done:>8} ({pct:4.0f}%) "
            f"{m_shift:>10} {m_overdue:>11}"
        )

    # Отпуска
    total_vac = sum(len(v) for v in vacation_plan.values())
    sick = sum(
        1 for recs in vacation_plan.values() for r in recs if r.vac_type == "sick"
    )
    print(
        f"""
  ОТПУСКА:
    Всего запланировано    : {total_vac}
    Ежегодные              : {total_vac - sick}
    Больничные             : {sick}
"""
    )

    # Топ-10 самых нагруженных за год (по кол-ву задач)
    emp_task_count: Dict[int, int] = defaultdict(int)
    emp_hours_year: Dict[int, float] = defaultdict(float)
    for t in all_tasks:
        emp_task_count[t.executor.id] += 1
        emp_hours_year[t.executor.id] += t.plan_hours

    emp_by_id = {e.id: e for e in employees}
    print(f"  ТОП-10 САМЫХ НАГРУЖЕННЫХ СОТРУДНИКОВ ЗА ГОД:")
    print(f"  {'ФИО':<30} {'Отдел':<6} {'Задач':>6} {'Часов':>8}")
    print(f"  {'-'*55}")
    top10 = sorted(emp_hours_year.items(), key=lambda x: x[1], reverse=True)[:10]
    for eid, hrs in top10:
        emp = emp_by_id.get(eid)
        if emp:
            print(
                f"  {emp.short_name:<30} {emp.dept:<6} "
                f"{emp_task_count[eid]:>6} {hrs:>8.0f}"
            )

    # Топ задач со сдвигами
    multi_shift = [t for t in all_tasks if t.shift_count >= 2]
    if multi_shift:
        print(f"\n  ЗАДАЧИ С МНОГОКРАТНЫМ СДВИГОМ (>= 2 раз):")
        print(f"  {'Задача':<40} {'Исполнитель':<20} {'Сдвигов':>8}")
        print(f"  {'-'*70}")
        for t in sorted(multi_shift, key=lambda x: x.shift_count, reverse=True)[:10]:
            print(f"  {t.name[:40]:<40} {t.executor.short_name:<20} {t.shift_count:>8}")

    # Смены исполнителей
    swapped = [t for t in all_tasks if t.prev_executor]
    if swapped:
        print(f"\n  ПРИМЕРЫ СМЕНЫ ИСПОЛНИТЕЛЯ (первые 10):")
        print(f"  {'Задача':<38} {'Был':<20} {'Стал':<20}")
        print(f"  {'-'*78}")
        for t in swapped[:10]:
            print(
                f"  {t.name[:38]:<38} {t.prev_executor:<20} {t.executor.short_name:<20}"
            )

    print(f"\n{'='*80}")
    print(f"  Симуляция завершена. Обработано {stats['months_processed']} месяцев.")
    print(f"{'='*80}\n")


# ── Точка входа ───────────────────────────────────────────────────────────────


def main():
    print("=" * 80)
    print(f"  СИМУЛЯТОР НТЦ-2Ц — ГОДОВОЙ ЦИКЛ {YEAR}")
    print("=" * 80)

    # Генерация сотрудников
    employees = generate_employees()
    print(f"\n  Сотрудников: {len(employees)} в {len(DEPT_SECTORS)} отделах")

    # План отпусков на год
    vacation_plan = generate_vacation_plan(employees)
    total_vac = sum(len(v) for v in vacation_plan.values())
    print(f"  Плановых отпусков: {total_vac}")
    print(f"  Задач будет создано: ~{MIN_TASKS_MONTH*12}–{MAX_TASKS_MONTH*12} за год")

    # Счётчики статистики
    stats = {
        "tasks_created": 0,
        "done_total": 0,
        "overdue_total": 0,
        "shifted_total": 0,
        "executor_swaps": 0,
        "balance_corrections": 0,
        "reassigned": 0,
        "months_processed": 0,
    }

    all_tasks: List[Task] = []

    # Симуляция 12 месяцев
    for month in range(1, 13):
        simulate_month(month, all_tasks, employees, vacation_plan, stats)

    # Годовой отчёт
    print_annual_report(all_tasks, employees, vacation_plan, stats)


if __name__ == "__main__":
    main()
