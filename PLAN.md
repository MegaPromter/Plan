# План реализации 9 UI-улучшений

## Пункты (из 10, без мобильной адаптации)

1. **Вынести CSS в отдельные файлы** — извлечь дублирующиеся стили
2. **Унифицировать шрифты** — Inter везде (вместо IBM Plex Sans в plan_spa)
3. **Перевести хардкод-цвета на CSS-переменные** — подготовка к тёмной теме
4. **Dark mode** — переключатель свет/тёмная/система
5. **Переключатель плотности таблиц** — compact/comfortable/spacious
6. **Skeleton-загрузка** — вместо спиннера при загрузке таблиц
7. **Slideout-панель** — боковая панель редактирования в СП (вместо модалки)
8. **Улучшение таблиц** — sticky первая колонка, bulk actions
9. **Цветовая палитра — мягче** — тёплые нейтралы

---

## Этап 1: CSS-рефакторинг (пп. 1, 2, 3, 9)

### 1.1 Создать `static/css/variables.css`
- Вынести `:root` переменные из base.html (строки 21-56)
- Добавить `[data-theme="dark"]` переменные (для пп. 4)
- Смягчить палитру (пп. 9): фон `#f8f9fb`, текст без чистого чёрного
- Добавить переменные плотности (пп. 5): `--td-pad`, `--td-font`, `--td-lh`

### 1.2 Создать `static/css/tables.css`
- Извлечь общие табличные стили из ПП, СП, ЖИ
- Общий класс `.data-table` с th/td стилями
- Skeleton-классы + @keyframes shimmer
- Density-классы: `.density-compact`, `.density-comfortable`, `.density-spacious`
- Sticky первая колонка

### 1.3 Создать `static/css/components.css`
- Модалки (`.modal-overlay`, `.modal`, `.modal-header`)
- Мультифильтры (`.mf-*`)
- Кнопки (`.btn-primary`, `.btn-outline`, `.btn-sm`)
- Бейджи
- Slideout-панель (`.slideout`, `.slideout-overlay`)
- Переключатель плотности (`.density-toggle`)
- Переключатель темы

### 1.4 Шрифт (пп. 2)
- plan_spa.html: IBM Plex Sans → Inter
- Числовые данные: `font-variant-numeric: tabular-nums`

### 1.5 Подключение
- base.html: `<link>` к variables.css, tables.css, components.css
- plan_spa.html: тоже (автономный документ, не extends base)
- Удалить дублирующиеся CSS из `<style>` блоков

---

## Этап 2: Dark Mode (пп. 4)

### 2.1 `[data-theme="dark"]` в variables.css
- Тёмные поверхности: `--bg: #0f1117`, `--surface: #1a1d27`
- Инвертированный текст: `--text: #e2e8f0`
- nav-bg оставить (уже тёмный)

### 2.2 Переключатель
- Кнопка в topbar: ☀/🌙/💻 (свет/тёмная/система)
- JS: `localStorage + data-theme + prefers-color-scheme`

### 2.3 Хардкод → переменные
- `#eef1f7` → `var(--surface2)`, `#4a5568` → `var(--text2)` и т.д.

---

## Этап 3: Density (пп. 5)

- CSS-классы на `.table-wrap`
- UI: кнопки в тулбаре
- Сохранение: `col_settings.density`

---

## Этап 4: Skeleton (пп. 6)

- CSS shimmer в tables.css
- JS-функции skeleton-строк в каждом из 3 JS-файлов
- Заменить начальный спиннер; scroll-спиннер оставить

---

## Этап 5: Slideout в СП (пп. 7)

- HTML slideout в plan_spa.html
- `openEditTaskModal()` → открывает slideout
- Модалку создания оставить

---

## Этап 6: Sticky column + Bulk actions (пп. 8)

- Sticky первая колонка через CSS
- Чекбоксы + панель массовых действий (СП)

---

## Затрагиваемые файлы

**Новые:** `static/css/variables.css`, `static/css/tables.css`, `static/css/components.css`

**Изменяемые:**
- `templates/base.html`
- `templates/works/plan_spa.html`
- `templates/works/production_plan_spa.html`
- `templates/works/notice_list.html`
- `templates/works/projects_spa.html`
- `static/js/production_plan.js`
- `static/js/plan.js`
- `static/js/notices.js`
- `apps/api/views/col_settings.py`
