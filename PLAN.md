# План: ЖИ читает данные из ЕТБД + каскадное удаление + ManualNotice

## Итоговые требования

1. **Поля ЖИ из ЕТБД** (автоматическая синхронизация, read-only в ЖИ):
   - Из **Work** (ПП/СП): `work_name` → наименование, `work_designation` → обозначение, `department` → отдел, `sector` → сектор, `executor` → разработчик
   - Из **WorkReport** (отчёт): `ii_pi` → ИИ/ПИ, `doc_number` → номер изв., `date_accepted` → дата выпуска, `date_expires` → срок действия

2. **Собственные поля ЖИ** (хранятся в Notice): `description` (описание), `status` (статус)

3. **№** — сквозная нумерация (порядковый номер строки в выдаче, не хранится в БД)

4. **group** — заголовок-разделитель (без параметров, остаётся как есть)

5. **notice_type** — убирается (нет в реальной таблице)

6. **Каскадное удаление**: WorkReport.delete() → связанная Notice удаляется целиком. Work остаётся нетронутым.

7. **Ручные записи ЖИ** — отдельная модель `ManualNotice` со своей таблицей. Все поля хранятся в ней напрямую (нет FK на WorkReport/Work).

---

## Что меняется

### 1. Модель `Notice` — убрать дублирующие поля, добавить FK

**Было:** все поля хранятся в Notice (копии данных).
**Станет:** Notice хранит только `source_report` FK, `description`, `status`, `group`.

```python
class Notice(models.Model):
    source_report = models.OneToOneField(
        WorkReport, on_delete=models.CASCADE,
        related_name='notice', verbose_name='Отчёт-источник',
    )
    group       = models.CharField('Группа', max_length=200, blank=True)
    description = models.TextField('Описание', blank=True)
    status      = models.CharField('Статус', max_length=10,
                                   choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at  = models.DateTimeField('Создан', auto_now_add=True)
    updated_at  = models.DateTimeField('Обновлён', auto_now=True)
```

**Удаляемые поля из Notice:** `notice_number`, `ii_pi`, `notice_type`, `doc_designation`, `subject`, `department`, `sector`, `executor`, `date_issued`, `date_expires`.

Каскад: `on_delete=CASCADE` на `source_report` → удаление WorkReport автоматически удаляет Notice.

### 2. Новая модель `ManualNotice` — для ручных записей

```python
class ManualNotice(models.Model):
    """Ручная запись журнала извещений (без привязки к отчёту)."""
    STATUS_CHOICES = Notice.STATUS_CHOICES

    ii_pi           = models.CharField('ИИ/ПИ', max_length=10, blank=True)
    notice_number   = models.CharField('Номер изв.', max_length=100, blank=True)
    subject         = models.CharField('Наименование', max_length=500, blank=True)
    group           = models.CharField('Группа', max_length=200, blank=True)
    doc_designation = models.CharField('Обозначение', max_length=200, blank=True)
    department      = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    sector          = models.ForeignKey(Sector, on_delete=models.SET_NULL, null=True, blank=True)
    executor        = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    date_issued     = models.DateField('Дата выпуска', null=True, blank=True)
    date_expires    = models.DateField('Срок действия', null=True, blank=True)
    description     = models.TextField('Описание', blank=True)
    status          = models.CharField('Статус', max_length=10,
                                       choices=STATUS_CHOICES, default='active')
    created_at      = models.DateTimeField('Создан', auto_now_add=True)
    updated_at      = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        db_table = 'work_manual_notice'
```

### 3. WorkReport — убрать дублирующие поля `doc_name`, `doc_designation`

Эти поля дублируют `Work.work_name` и `Work.work_designation`.

- **Удалить** `doc_name` и `doc_designation` из WorkReport
- При сериализации читать из `report.work.work_name` и `report.work.work_designation`

### 4. API `journal.py` — единый список из Notice + ManualNotice

**`_serialize_notice(n)`** — для Notice (привязанных к отчёту):
```python
{
    'id': n.pk,
    'type': 'auto',
    'ii_pi': n.source_report.ii_pi,
    'notice_number': n.source_report.doc_number,
    'subject': n.source_report.work.work_name,
    'group': n.group,
    'doc_designation': n.source_report.work.work_designation,
    'date_issued': n.source_report.date_accepted,
    'date_expires': n.source_report.date_expires,
    'dept': n.source_report.work.department.code,
    'sector': n.source_report.work.sector.name,
    'executor': n.source_report.work.executor.full_name,
    'description': n.description,
    'status': n.status,
}
```

**`_serialize_manual_notice(m)`** — для ManualNotice:
```python
{
    'id': m.pk,
    'type': 'manual',
    'ii_pi': m.ii_pi,
    'notice_number': m.notice_number,
    'subject': m.subject,
    ...  # все поля из самой записи
}
```

**GET /api/journal/** — объединяет оба запроса, сортирует, нумерует сквозным №.

**POST /api/journal/create/** — принимает `type: 'auto'|'manual'`:
- `auto`: создаёт Notice с `source_report_id`
- `manual`: создаёт ManualNotice со всеми полями

**PUT/DELETE /api/journal/<id>/** — принимает `type` для маршрутизации к нужной модели.

### 5. API `reports.py` — изменения

- `_serialize_report()`: `doc_name` → `report.work.work_name`, `doc_designation` → `report.work.work_designation`
- `ReportCreateView`: убрать запись `doc_name`/`doc_designation`
- `ReportDetailView._update()`: убрать обновление `doc_name`/`doc_designation`

### 6. Frontend `plan_spa.html`

- `_makeNewReportRow()`: убрать копирование `doc_name`/`doc_designation` — фронт показывает из ответа API
- `_syncNoticeFromReport()`: вместо копирования полей — передавать `source_report_id` при создании Notice
- Удаление отчёта: каскад через БД, доп. код не нужен

### 7. Frontend `journal_spa.html`

- Для записей с `type: 'auto'`: поля кроме description/status — read-only
- Для записей с `type: 'manual'`: все поля редактируемые
- Кнопка «+ Добавить» → выбор типа (из отчёта / вручную)
- Сквозная нумерация № формируется при рендере

### 8. Миграция

1. `AddField` Notice.source_report (OneToOneField → WorkReport, CASCADE, null=True временно)
2. Data migration: связать существующие Notice с WorkReport по совпадению notice_number/doc_number + doc_designation
3. Перенести несвязанные Notice в ManualNotice
4. `RemoveField` из Notice: notice_number, ii_pi, notice_type, doc_designation, subject, department, sector, executor, date_issued, date_expires
5. `AlterField` Notice.source_report → null=False (обязательный FK)
6. `RemoveField` WorkReport: doc_name, doc_designation
7. `CreateModel` ManualNotice

---

## Порядок работ

1. Миграция: создать ManualNotice, добавить Notice.source_report FK (nullable)
2. Data migration: связать Notice↔WorkReport, перенести ручные в ManualNotice
3. Миграция: удалить дублирующие поля из Notice и WorkReport, сделать source_report NOT NULL
4. Backend: обновить сериализацию journal.py (Notice + ManualNotice)
5. Backend: обновить reports.py (doc_name/doc_designation из Work)
6. Frontend: plan_spa.html — убрать копирование, передавать source_report_id
7. Frontend: journal_spa.html — read-only для авто-записей, редактируемые для ручных
8. Тесты
