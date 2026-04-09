"""
Создание этапов (PPStage) для всех проектов на prod.
Этапы копируются из проекта ДОС на локалке.
Запуск: python scripts/seed_prod_stages.py
"""
import paramiko
import json

# 6 этапов ДОС (с локалки)
stages_template = [
    {"num": "3.1", "name": "Разработка корпусов",              "wo": "нз-123",  "rc": "КС-154", "order": 0},
    {"num": "3.2", "name": "Разработка схем ПГС",             "wo": "НЗ-789",  "rc": "КС-432", "order": 1},
    {"num": "3.3", "name": "Разработка схем БКС",             "wo": "НЗ-098",  "rc": "КС-645", "order": 2},
    {"num": "3.4", "name": "Разработка монтажей",             "wo": "НЗ-764",  "rc": "КС-222", "order": 3},
    {"num": "3.5", "name": "Разработка общей документации",    "wo": "НЗ-0987", "rc": "КС-874", "order": 4},
    {"num": "3.6", "name": "Разработка расчётов",             "wo": "НЗ-198",  "rc": "888-999", "order": 5},
]

django_script = '''import json
from apps.works.models import Project, PPStage

stages_template = {tpl}

projects = Project.objects.all()
created = 0
for proj in projects:
    for s in stages_template:
        obj, c = PPStage.objects.get_or_create(
            project=proj,
            stage_number=s["num"],
            defaults={{
                "name": s["name"],
                "work_order": s["wo"],
                "row_code": s["rc"],
                "order": s["order"],
            }}
        )
        if c:
            created += 1

print(f"Created {{created}} stages for {{projects.count()}} projects")
print(f"Total stages: {{PPStage.objects.count()}}")
'''.format(tpl=json.dumps(stages_template, ensure_ascii=False))

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('72.56.13.101', username='root', password='pBg6?CB.QBqpGa')

sftp = ssh.open_sftp()
with sftp.file('/tmp/seed_stages.py', 'w') as f:
    f.write(django_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command(
    'cd /opt/planapp && source venv/bin/activate && python manage.py shell < /tmp/seed_stages.py'
)
out = stdout.read().decode()
err = stderr.read().decode()

for line in out.strip().split('\n'):
    if 'Created' in line or 'Total' in line:
        print(line)

if 'Traceback' in err:
    print('ERROR:', err[-1000:])

ssh.exec_command('rm /tmp/seed_stages.py')
ssh.close()
