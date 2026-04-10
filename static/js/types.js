/**
 * types.js — JSDoc-определения типов для всего проекта.
 * Этот файл НЕ содержит исполняемого кода, только описания типов.
 * VS Code читает их автоматически через jsconfig.json (checkJs: true).
 *
 * Использование в других файлах:
 *   /// <reference path="types.js" />
 *   или просто @type {Task} — VS Code подхватит из jsconfig.
 */

// ══════════════════════════════════════════════════════════════════════
// Модели данных (соответствуют Django-моделям / API-ответам)
// ══════════════════════════════════════════════════════════════════════

/**
 * Задача (Work) — основная сущность СП и ПП.
 * Приходит из /api/tasks/ и /api/production_plan/.
 * @typedef {Object} Task
 * @property {number} id
 * @property {string} name — название задачи
 * @property {string} [number] — номер задачи
 * @property {string} [description] — описание
 * @property {string} [stage] — этап
 * @property {string} [justification] — обоснование
 * @property {string} [status] — статус ('inwork'|'done'|'overdue')
 * @property {string} [task_type] — тип задачи ('Разработка'|'Корректировка документа'|...)
 * @property {string} [dept] — код отдела ('301', '209' и т.д.)
 * @property {string} [sector] — код сектора
 * @property {string} [executor] — ФИО основного исполнителя
 * @property {Array<TaskExecutor>} [executors_list] — список исполнителей (JSONField)
 * @property {string} [date_start] — дата начала (YYYY-MM-DD)
 * @property {string} [date_end] — дата окончания (YYYY-MM-DD)
 * @property {string} [deadline] — крайний срок (YYYY-MM-DD)
 * @property {number} [labor] — трудоёмкость (часы)
 * @property {Object<string, number>} [plan_hours] — плановые часы по месяцам {'1': 40, '2': 80}
 * @property {Object<string, number>} [plan_hours_all] — плановые часы за все годы
 * @property {boolean} [has_reports] — есть ли отчёты (задача выполнена)
 * @property {boolean} [is_overdue] — просрочена ли
 * @property {boolean} [from_pp] — перенесена из ПП
 * @property {number} [predecessors_count] — кол-во зависимостей
 * @property {string} [row_code] — код строки (ПП)
 * @property {string} [project_name] — название проекта
 * @property {string} [project_short] — короткое название проекта
 * @property {number} [project_id] — ID проекта
 * @property {string} [product_name] — название изделия
 * @property {Object} [actions] — действия {pp_id, pp_labor}
 * @property {string} [pp_project_name] — название ПП-проекта
 */

/**
 * Исполнитель задачи (элемент executors_list).
 * @typedef {Object} TaskExecutor
 * @property {string} name — ФИО
 * @property {number} [hours] — плановые часы
 */

/**
 * ПП-проект (PPProject).
 * @typedef {Object} PPProject
 * @property {number} id
 * @property {string} name — название
 * @property {number} [up_project_id] — FK на Project (УП)
 * @property {string} [up_project_name] — название проекта УП
 */

/**
 * Проект (Project) из УП.
 * @typedef {Object} Project
 * @property {number} id
 * @property {string} name_full
 * @property {string} [name_short]
 * @property {string} [code]
 * @property {Array<ProjectProduct>} [products]
 */

/**
 * Изделие проекта (ProjectProduct).
 * @typedef {Object} ProjectProduct
 * @property {number} id
 * @property {string} name
 * @property {string} [name_short]
 * @property {string} [code]
 */

/**
 * Производственный календарь (WorkCalendar).
 * @typedef {Object} CalendarMonth
 * @property {number} id
 * @property {number} year
 * @property {number} month
 * @property {number} hours_norm — норма часов в месяце
 */

/**
 * Сотрудник (Employee) — краткая версия из API.
 * @typedef {Object} Employee
 * @property {number} id
 * @property {string} full_name — ФИО
 * @property {string} [short_name] — Фамилия И.О.
 * @property {string} [role] — роль (admin|dept_head|...)
 * @property {string} [dept] — код отдела
 * @property {string} [sector] — код сектора
 */

/**
 * Извещение (Notice).
 * @typedef {Object} Notice
 * @property {number} id
 * @property {string} [notice_number]
 * @property {string} [date_issued] — дата выдачи (YYYY-MM-DD)
 * @property {string} [ii_pi] — тип (ИИ|ПИ)
 * @property {string} [designation] — обозначение документа
 * @property {string} [reason]
 * @property {string} [executor_name]
 * @property {string} [closure_notice_number]
 * @property {string} [closure_date_issued]
 * @property {number} [work_report] — FK на WorkReport (авто-режим)
 */

// ══════════════════════════════════════════════════════════════════════
// Конфигурация страниц (JSON-блоки из Django-шаблонов)
// ══════════════════════════════════════════════════════════════════════

/**
 * Конфигурация СП (из #sp-config в plan_spa.html).
 * @typedef {Object} SPConfig
 * @property {boolean} isWriter — может ли редактировать
 * @property {boolean} isAdmin — администратор
 * @property {string} userRole — роль пользователя
 * @property {string} userDept — код отдела пользователя
 * @property {string} [userSector] — код сектора
 * @property {string} [userCenter] — код центра
 * @property {Object} [colSettings] — настройки колонок
 */

/**
 * Конфигурация ПП (из #pp-config в production_plan_spa.html).
 * @typedef {Object} PPConfig
 * @property {boolean} isWriter
 * @property {boolean} isAdmin
 * @property {string} userRole
 * @property {string} userDept
 */

/**
 * Конфигурация дашборда (из #dash-config в dashboard.html).
 * @typedef {Object} DashConfig
 * @property {number} currentYear
 * @property {number} currentMonth
 * @property {string} role
 * @property {boolean} isWriter
 */

/**
 * Конфигурация аналитики (из #an-config в analytics_spa.html).
 * @typedef {Object} AnalyticsConfig
 * @property {number} currentYear
 * @property {string} role
 * @property {string} deptCode
 */

// ══════════════════════════════════════════════════════════════════════
// API-ответы
// ══════════════════════════════════════════════════════════════════════

/**
 * Стандартный ответ API со списком.
 * @template T
 * @typedef {Object} ApiListResponse
 * @property {Array<T>} results
 * @property {number} [count]
 * @property {string} [next]
 * @property {string} [previous]
 */

/**
 * Ответ fetchJson (обёртка из utils.js).
 * @typedef {Object} FetchResult
 * @property {boolean} ok
 * @property {number} status
 * @property {*} data — распарсенный JSON
 */

// ══════════════════════════════════════════════════════════════════════
// Колонки и фильтры
// ══════════════════════════════════════════════════════════════════════

/**
 * Фильтры колонок (ключ — имя колонки, значение — строка или Set для мультифильтра).
 * @typedef {Object<string, string|Set<string>>} ColFilters
 */

/**
 * Настройки колонок (ширины, видимость).
 * @typedef {Object<string, number|boolean>} ColSettings
 */

// Экспорт не нужен — JSDoc @typedef доступны глобально через jsconfig.json
