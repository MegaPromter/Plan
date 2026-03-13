"""
Module 1: Initial data generation.
Creates org structure (centers, departments, sectors, employees),
production calendar for 2026.
Uses admin API /api/users/ (POST, no rate limiting).

v2: 10 departments, Russian names (Cyrillic), ~300+ employees.
"""
import logging

logger = logging.getLogger('simulator')

# -- Русские ФИО (кириллица) --------------------------------------------------

RU_LAST_NAMES = [
    'Иванов', 'Петров', 'Сидоров', 'Козлов', 'Новиков', 'Морозов',
    'Волков', 'Соловьёв', 'Васильев', 'Зайцев', 'Павлов', 'Семёнов',
    'Голубев', 'Виноградов', 'Богданов', 'Воробьёв', 'Фёдоров', 'Михайлов',
    'Беляев', 'Тарасов', 'Белов', 'Комаров', 'Орлов', 'Киселёв',
    'Макаров', 'Андреев', 'Ковалёв', 'Ильин', 'Гусев', 'Титов',
    'Кузьмин', 'Кудрявцев', 'Баранов', 'Куликов', 'Алексеев', 'Степанов',
    'Яковлев', 'Сорокин', 'Сергеев', 'Романов', 'Захаров', 'Борисов',
    'Королёв', 'Герасимов', 'Пономарёв', 'Григорьев', 'Лазарев', 'Медведев',
    'Ершов', 'Никитин', 'Соболев', 'Рябов', 'Поляков', 'Цветков',
    'Данилов', 'Жуков', 'Фролов', 'Журавлёв', 'Николаев', 'Крылов',
    'Максимов', 'Сафонов', 'Логинов', 'Воронов', 'Селезнёв',
    'Калинин', 'Лебедев', 'Абрамов', 'Миронов', 'Широков', 'Филиппов',
]

RU_FIRST_NAMES = [
    'Александр', 'Дмитрий', 'Максим', 'Сергей', 'Андрей', 'Алексей',
    'Артём', 'Илья', 'Кирилл', 'Михаил', 'Никита', 'Егор',
    'Евгений', 'Иван', 'Владимир', 'Павел', 'Роман', 'Николай',
    'Олег', 'Виктор', 'Денис', 'Юрий', 'Пётр', 'Константин',
    'Антон', 'Тимофей', 'Вадим', 'Григорий', 'Валерий', 'Борис',
    'Геннадий', 'Леонид', 'Фёдор', 'Станислав', 'Аркадий', 'Руслан',
]

RU_PATRONYMICS = [
    'Александрович', 'Дмитриевич', 'Сергеевич', 'Андреевич', 'Алексеевич',
    'Михайлович', 'Иванович', 'Владимирович', 'Петрович', 'Николаевич',
    'Олегович', 'Евгеньевич', 'Юрьевич', 'Константинович', 'Павлович',
    'Викторович', 'Борисович', 'Геннадьевич', 'Валерьевич', 'Фёдорович',
]

# -- 10 отделов (коды) --------------------------------------------------------

DEPT_CODES = [
    '021', '028', '084', '086', '301',
    '042', '055', '063', '077', '099',
]

CENTER_CODES = ['NTC-1', 'NTC-2']

# -- Производственный календарь 2026 ------------------------------------------

CALENDAR_2026 = {
    1: 120, 2: 152, 3: 168, 4: 176, 5: 143, 6: 167,
    7: 184, 8: 168, 9: 176, 10: 176, 11: 159, 12: 183,
}

# Role -> position key
ROLE_POSITION_MAP = {
    'admin': 'ntc_head',
    'ntc_head': 'ntc_head',
    'ntc_deputy': 'ntc_deputy',
    'dept_head': 'dept_head',
    'dept_deputy': 'dept_deputy',
    'sector_head': 'sector_head',
    'user': 'eng_1',
}


def setup_calendar(client, year=2026):
    """Creates production calendar for the year."""
    logger.info("Creating production calendar %d...", year)
    created = 0
    for month, hours in CALENDAR_2026.items():
        resp = client.post('/api/work_calendar/create/', {
            'year': year, 'month': month, 'hours_norm': hours,
        })
        data = client.json_ok(resp)
        if data:
            created += 1
        else:
            logger.debug("Calendar %d/%02d: already exists or error", year, month)
    logger.info("Calendar: created %d records of 12", created)
    return created


def setup_org_structure(client, rng, config):
    """
    Creates org structure: 10 departments, 3-4 sectors each, 5-8 employees per sector.
    Returns dict with employees list and departments list.
    """
    logger.info("Creating org structure (10 departments)...")

    org_cfg = config.get('org', {})
    employees = []
    user_counter = [0]
    used_names = set()

    def _make_unique_name():
        """Generates unique full name (Cyrillic)."""
        for _ in range(500):
            last = rng.choice(RU_LAST_NAMES)
            first = rng.choice(RU_FIRST_NAMES)
            patr = rng.choice(RU_PATRONYMICS)
            full = f"{last} {first} {patr}"
            if full not in used_names:
                used_names.add(full)
                return last, first, patr
        # Fallback: add numeric suffix
        user_counter[0] += 1
        last = rng.choice(RU_LAST_NAMES)
        first = rng.choice(RU_FIRST_NAMES)
        patr = rng.choice(RU_PATRONYMICS)
        return last, first + str(user_counter[0]), patr

    def _translit(text):
        """Simple Cyrillic -> Latin transliteration for usernames."""
        table = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
            'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
            'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
            'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
            'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya',
        }
        return ''.join(table.get(c, c) for c in text.lower())

    def _make_username(last, first):
        user_counter[0] += 1
        t_last = _translit(last)
        t_first = _translit(first[:1])
        return f"{t_last}_{t_first}_{user_counter[0]}"

    def _create_user(role, dept_code, sector_code, center_code):
        last, first, patr = _make_unique_name()
        username = _make_username(last, first)
        password = 'SimPass123!'
        position = ROLE_POSITION_MAP.get(role, 'eng_1')

        body = {
            'username': username,
            'password': password,
            'role': role,
            'last_name': last,
            'first_name': first,
            'patronymic': patr,
            'position': position,
            'dept': dept_code or '',
            'sector': sector_code or '',
            'center': center_code or '',
        }

        resp = client.post('/api/users/', body)
        data = client.json_ok(resp)
        if data and data.get('id'):
            emp = {
                'id': data['id'],
                'username': username,
                'password': password,
                'role': role,
                'dept': dept_code,
                'sector': sector_code,
                'center': center_code,
                'full_name': f"{last} {first} {patr}",
            }
            employees.append(emp)
            return emp
        else:
            logger.warning("Failed to create user %s: %s",
                           username, resp.text[:200] if resp else 'no response')
            return None

    depts_per_center = org_cfg.get('departments_per_center', [5, 5])
    sectors_range = org_cfg.get('sectors_per_dept', [3, 4])
    emp_range = org_cfg.get('employees_per_sector', [5, 8])

    dept_idx = 0
    departments = []

    for ci, center_code in enumerate(CENTER_CODES):
        ndepts = depts_per_center[ci] if ci < len(depts_per_center) else 5
        _create_user('ntc_head', '', '', center_code)
        _create_user('ntc_deputy', '', '', center_code)

        for _ in range(ndepts):
            if dept_idx >= len(DEPT_CODES):
                break
            dc = DEPT_CODES[dept_idx]
            dept_idx += 1

            _create_user('dept_head', dc, '', '')
            _create_user('dept_deputy', dc, '', '')

            nsectors = rng.randint(*sectors_range)
            sector_codes = []
            for si in range(nsectors):
                sc = f"{dc}-{si + 1}"
                sector_codes.append(sc)
                _create_user('sector_head', dc, sc, '')
                nemp = rng.randint(*emp_range)
                for _ in range(nemp):
                    _create_user('user', dc, sc, '')

            departments.append((dc, center_code, sector_codes))

    logger.info("Org structure: %d employees, %d departments",
                len(employees), len(departments))

    for dc, cc, scs in departments:
        dept_emps = [e for e in employees if e['dept'] == dc]
        logger.info("  Dept %s (%s): %d employees, %d sectors",
                    dc, cc, len(dept_emps), len(scs))

    return {
        'employees': employees,
        'departments': departments,
    }
