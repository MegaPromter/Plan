# План исправлений — полный аудит 2026-03-14

## Фаза 1: Критические баги (500 ошибки, сломанный функционал)

### 1. parse_json_body() → возвращать {} вместо None
- Файл: `apps/api/mixins.py`
- 16+ эндпоинтов крашатся с 500 на невалидном JSON

### 2. ProjectAdmin.search_fields — 'name' → 'name_full', 'name_short'
- Файл: `apps/works/admin.py`

### 3. --radius в base.html :root
- work_calendar рендерится с квадратными углами

### 4. modal.js — исправить fallback-цвета на светлую тему

### 5. Убрать дубликат showToast из base.html (utils.js уже определяет)

## Фаза 2: Высокие баги

### 6. journal_spa.html — page_size → per_page
### 7. production_plan_spa.html — initColumnResize после renderPPTable
### 8. Мёртвый код list.html/detail.html/form.html
### 9. delegations.py — try/except int(delegate_id)
### 10. projects_spa.html — cursor:default для не-админов

## Фаза 3: UX

### 11. :focus-visible
### 12. Z-index шкала
### 13. Loading-состояния
