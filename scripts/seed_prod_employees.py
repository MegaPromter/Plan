"""
Скрипт для генерации рандомных сотрудников на prod-сервере.
Запуск: python scripts/seed_prod_employees.py
"""

import json
import random

import paramiko

depts = [
    {"id": 1, "code": "001", "ntc": 2},
    {"id": 2, "code": "002", "ntc": 2},
    {"id": 3, "code": "003", "ntc": 2},
    {"id": 4, "code": "201", "ntc": 3},
    {"id": 5, "code": "202", "ntc": 3},
    {"id": 6, "code": "204", "ntc": 3},
    {"id": 7, "code": "207", "ntc": 3},
    {"id": 8, "code": "208", "ntc": 3},
    {"id": 9, "code": "209", "ntc": 3},
    {"id": 10, "code": "231", "ntc": 3},
    {"id": 11, "code": "301", "ntc": 4},
    {"id": 12, "code": "302", "ntc": 4},
    {"id": 13, "code": "303", "ntc": 4},
    {"id": 14, "code": "304", "ntc": 4},
    {"id": 15, "code": "401", "ntc": 5},
    {"id": 16, "code": "402", "ntc": 5},
    {"id": 18, "code": "403", "ntc": 5},
    {"id": 17, "code": "404", "ntc": 5},
]

last_m = [
    "Иванов",
    "Петров",
    "Сидоров",
    "Кузнецов",
    "Смирнов",
    "Попов",
    "Васильев",
    "Соколов",
    "Михайлов",
    "Новиков",
    "Морозов",
    "Волков",
    "Алексеев",
    "Лебедев",
    "Козлов",
    "Степанов",
    "Николаев",
    "Орлов",
    "Андреев",
    "Макаров",
    "Никитин",
    "Захаров",
    "Зайцев",
    "Борисов",
    "Яковлев",
    "Романов",
    "Сергеев",
    "Александров",
    "Дмитриев",
    "Гусев",
    "Ильин",
    "Максимов",
    "Поляков",
    "Сорокин",
    "Белов",
    "Медведев",
    "Антонов",
    "Тарасов",
    "Жуков",
    "Баранов",
    "Филиппов",
    "Комаров",
    "Давыдов",
    "Беляев",
    "Герасимов",
    "Богданов",
    "Осипов",
    "Матвеев",
    "Титов",
    "Марков",
    "Миронов",
    "Крылов",
    "Куликов",
    "Карпов",
    "Власов",
    "Денисов",
    "Гаврилов",
    "Тихонов",
    "Казаков",
    "Данилов",
    "Тимофеев",
]

last_f = [
    "Иванова",
    "Петрова",
    "Сидорова",
    "Кузнецова",
    "Смирнова",
    "Попова",
    "Васильева",
    "Соколова",
    "Михайлова",
    "Новикова",
    "Морозова",
    "Волкова",
    "Алексеева",
    "Лебедева",
    "Козлова",
    "Степанова",
    "Николаева",
    "Орлова",
    "Андреева",
    "Макарова",
    "Никитина",
    "Захарова",
    "Зайцева",
    "Борисова",
    "Яковлева",
    "Романова",
]

first_m = [
    "Александр",
    "Дмитрий",
    "Сергей",
    "Андрей",
    "Алексей",
    "Михаил",
    "Иван",
    "Максим",
    "Владимир",
    "Евгений",
    "Николай",
    "Павел",
    "Роман",
    "Олег",
    "Виктор",
    "Денис",
    "Игорь",
    "Антон",
    "Константин",
    "Юрий",
    "Вадим",
    "Григорий",
    "Борис",
    "Василий",
    "Тимофей",
    "Кирилл",
    "Леонид",
    "Валерий",
    "Геннадий",
]

first_f = [
    "Анна",
    "Елена",
    "Ольга",
    "Наталья",
    "Мария",
    "Екатерина",
    "Татьяна",
    "Ирина",
    "Светлана",
    "Юлия",
    "Дарья",
    "Алина",
    "Марина",
    "Виктория",
    "Галина",
    "Надежда",
]

pat_m = [
    "Александрович",
    "Дмитриевич",
    "Сергеевич",
    "Андреевич",
    "Алексеевич",
    "Михайлович",
    "Иванович",
    "Владимирович",
    "Евгеньевич",
    "Николаевич",
    "Павлович",
    "Олегович",
    "Викторович",
    "Игоревич",
    "Петрович",
    "Юрьевич",
    "Борисович",
    "Валерьевич",
]

pat_f = [
    "Александровна",
    "Дмитриевна",
    "Сергеевна",
    "Андреевна",
    "Алексеевна",
    "Михайловна",
    "Ивановна",
    "Владимировна",
    "Евгеньевна",
    "Николаевна",
    "Павловна",
    "Олеговна",
    "Викторовна",
    "Игоревна",
    "Петровна",
    "Юрьевна",
    "Борисовна",
    "Валерьевна",
]

positions = [
    "tech_3",
    "tech_2",
    "tech_1",
    "spec",
    "spec_2",
    "spec_1",
    "lead_spec",
    "eng",
    "eng_3",
    "eng_2",
    "eng_1",
    "lead_eng",
    "lead_eng_dir_3",
    "lead_eng_dir_2",
    "lead_eng_coord",
    "bureau_head",
    "jr_researcher",
    "sr_researcher",
    "lead_researcher",
    "sector_head",
    "dept_deputy",
    "dept_head",
]
pos_w = [3, 5, 5, 4, 6, 6, 8, 10, 12, 15, 12, 8, 3, 2, 3, 2, 2, 3, 2, 2, 1, 1]

tr_map = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "_": "_",
}

random.seed(42)
used = set()
emps = []

for dept in depts:
    count = random.randint(12, 25)
    for i in range(count):
        fem = random.random() < 0.3
        ln = random.choice(last_f if fem else last_m)
        fn = random.choice(first_f if fem else first_m)
        pt = random.choice(pat_f if fem else pat_m)
        pos = random.choices(positions, weights=pos_w, k=1)[0]
        if i == 0:
            role, pos = "dept_head", "dept_head"
        elif i == 1:
            role, pos = "dept_deputy", "dept_deputy"
        elif i in (2, 3):
            role, pos = "sector_head", "sector_head"
        else:
            role = "user"
        base = ln.lower() + "_" + fn[0].lower()
        uname = "".join(tr_map.get(c, c) for c in base)
        while uname in used:
            uname += str(random.randint(1, 99))
        used.add(uname)
        emps.append([uname, ln, fn, pt, role, pos, dept["id"], dept["ntc"]])

print(f"Generated {len(emps)} employees for {len(depts)} depts")

# Django-скрипт для выполнения на сервере через manage.py shell
django_script = """import json
from django.contrib.auth.models import User
from apps.employees.models import Employee

data = {data_json}

created = 0
for uname, ln, fn, pt, role, pos, dept_id, ntc_id in data:
    u, _ = User.objects.get_or_create(
        username=uname,
        defaults={{"first_name": fn, "last_name": ln, "is_active": True}}
    )
    u.set_password("pass1234")
    u.save()
    e, c = Employee.objects.get_or_create(
        user=u,
        defaults={{
            "last_name": ln, "first_name": fn, "patronymic": pt,
            "role": role, "position": pos,
            "department_id": dept_id, "ntc_center_id": ntc_id, "is_active": True,
        }}
    )
    if c:
        created += 1

print(f"Created {{created}} employees")
print(f"Total employees: {{Employee.objects.count()}}")
""".format(
    data_json=json.dumps(emps, ensure_ascii=False)
)

# Подключение к серверу и выполнение
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("72.56.13.101", username="root", password="pBg6?CB.QBqpGa")

sftp = ssh.open_sftp()
with sftp.file("/tmp/seed_employees.py", "w") as f:
    f.write(django_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command(
    "cd /opt/planapp && source venv/bin/activate && python manage.py shell < /tmp/seed_employees.py"
)
out = stdout.read().decode()
err = stderr.read().decode()

for line in out.strip().split("\n"):
    if "Created" in line or "Total" in line:
        print(line)

if "Traceback" in err:
    print("ERROR:", err[-1500:])

# Очистка
ssh.exec_command("rm /tmp/seed_employees.py")
ssh.close()
