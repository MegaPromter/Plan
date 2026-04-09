"""
Создание секторов (2-4 на отдел) и распределение сотрудников по секторам.
Коды секторов: "отдел-010", "отдел-120", "отдел-210", "отдел-310".
Запуск: python scripts/seed_prod_sectors.py
"""
import paramiko
import random
import json

depts = [
    {"id":1,"code":"001"},{"id":2,"code":"002"},{"id":3,"code":"003"},
    {"id":4,"code":"201"},{"id":5,"code":"202"},{"id":6,"code":"204"},
    {"id":7,"code":"207"},{"id":8,"code":"208"},{"id":9,"code":"209"},
    {"id":10,"code":"231"},{"id":11,"code":"301"},{"id":12,"code":"302"},
    {"id":13,"code":"303"},{"id":14,"code":"304"},{"id":15,"code":"401"},
    {"id":16,"code":"402"},{"id":18,"code":"403"},{"id":17,"code":"404"},
]

sector_suffixes = ['010', '120', '210', '310']

random.seed(123)

# Генерируем план секторов для каждого отдела
sectors_plan = []  # [(dept_id, sector_code, min_people, max_people)]
for dept in depts:
    num_sectors = random.randint(2, 4)
    for i in range(num_sectors):
        code = f"{dept['code']}-{sector_suffixes[i]}"
        sectors_plan.append((dept['id'], code))

print(f"Sectors to create: {len(sectors_plan)}")

# Django-скрипт
django_script = '''import random
import json
from apps.employees.models import Department, Sector, Employee

random.seed(456)

sectors_plan = {sectors_json}

# 1. Создаём секторы
created_sectors = 0
sector_map = {{}}  # dept_id -> [sector_id, ...]
for dept_id, code in sectors_plan:
    s, c = Sector.objects.get_or_create(
        department_id=dept_id, code=code,
        defaults={{"name": ""}}
    )
    if c:
        created_sectors += 1
    sector_map.setdefault(dept_id, []).append(s.id)

print(f"Created {{created_sectors}} sectors")

# 2. Распределяем сотрудников по секторам
# Для каждого отдела: берём всех сотрудников, раскидываем по секторам (4-15 на сектор)
assigned = 0
for dept_id, sector_ids in sector_map.items():
    emps = list(
        Employee.objects.filter(department_id=dept_id, is_active=True)
        .order_by('id')
        .values_list('id', flat=True)
    )
    if not emps:
        continue

    # Перемешиваем
    random.shuffle(emps)

    # Распределяем: sector_head-ы первыми в свой сектор
    sector_heads = list(
        Employee.objects.filter(
            department_id=dept_id, role='sector_head', is_active=True
        ).values_list('id', flat=True)
    )

    # Назначаем sector_head-ов в первые секторы
    for i, sh_id in enumerate(sector_heads):
        if i < len(sector_ids):
            Employee.objects.filter(id=sh_id).update(sector_id=sector_ids[i])
            assigned += 1
            if sh_id in emps:
                emps.remove(sh_id)

    # Остальных распределяем равномерно
    idx = 0
    for emp_id in emps:
        sector_id = sector_ids[idx % len(sector_ids)]
        Employee.objects.filter(id=emp_id).update(sector_id=sector_id)
        assigned += 1
        idx += 1

print(f"Assigned {{assigned}} employees to sectors")
print(f"Total sectors: {{Sector.objects.count()}}")

# Проверка: сотрудники без сектора
no_sector = Employee.objects.filter(sector__isnull=True, is_active=True).count()
print(f"Employees without sector: {{no_sector}}")
'''.format(sectors_json=json.dumps(sectors_plan, ensure_ascii=False))

# Подключение и выполнение
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('72.56.13.101', username='root', password='pBg6?CB.QBqpGa')

sftp = ssh.open_sftp()
with sftp.file('/tmp/seed_sectors.py', 'w') as f:
    f.write(django_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command(
    'cd /opt/planapp && source venv/bin/activate && python manage.py shell < /tmp/seed_sectors.py'
)
out = stdout.read().decode()
err = stderr.read().decode()

for line in out.strip().split('\n'):
    if any(k in line for k in ('Created', 'Assigned', 'Total', 'without')):
        print(line)

if 'Traceback' in err:
    print('ERROR:', err[-1500:])

ssh.exec_command('rm /tmp/seed_sectors.py')
ssh.close()
