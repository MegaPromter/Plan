/**
 * Константы модуля «Производственный план».
 * Порядок столбцов, метки, индексы, названия месяцев и статусов.
 */

// ══════════════════════════════════════════════════════════════════════════
//  СТОЛБЦЫ ПП-ТАБЛИЦЫ
// ══════════════════════════════════════════════════════════════════════════

/** Список полей колонок ПП-таблицы (в порядке отображения) */
export const PP_COLUMNS = [
  'row_code', 'work_order', 'stage_num', 'milestone_num', 'work_num',
  'work_designation', 'work_name',
  'date_start', 'date_end', 'sheets_a4', 'norm', 'coeff', 'labor',
  'center', 'dept', 'sector_head', 'executor', 'task_type',
]

/** Метки колонок (русские заголовки для мобильного card-layout) */
export const PP_COL_LABELS = {
  row_code: 'Код строки',
  work_order: 'Наряд-заказ',
  stage_num: '№ этапа',
  milestone_num: '№ вехи',
  work_num: '№ работы',
  work_designation: 'Обозначение',
  work_name: 'Наименование',
  date_start: 'Начало',
  date_end: 'Окончание',
  sheets_a4: 'Ф, А4',
  norm: 'Норматив',
  coeff: 'Коэфф',
  labor: 'Трудоёмкость',
  center: 'Подразделение',
  dept: 'Отдел',
  sector_head: 'Сектор',
  executor: 'Разработчик',
  task_type: 'Тип задачи',
}

/**
 * Маппинг колонки → индекс для data-col-idx (режимы отображения).
 * Индекс 0 — порядковый номер (№), 19 — действия.
 */
export const PP_COL_IDX = {
  row_code: 1,
  work_order: 2,
  stage_num: 3,
  milestone_num: 4,
  work_num: 5,
  work_designation: 6,
  work_name: 7,
  date_start: 8,
  date_end: 9,
  sheets_a4: 10,
  norm: 11,
  coeff: 12,
  labor: 13,
  center: 14,
  dept: 15,
  sector_head: 16,
  executor: 17,
  task_type: 18,
}

// ══════════════════════════════════════════════════════════════════════════
//  НАЗВАНИЯ МЕСЯЦЕВ
// ══════════════════════════════════════════════════════════════════════════

/** Полные названия месяцев на русском (индекс 0 = Январь) */
export const MONTH_NAMES_RU = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

/** Сокращённые названия месяцев для панели периода */
export const MONTH_NAMES_SHORT = [
  'Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
  'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек',
]

// ══════════════════════════════════════════════════════════════════════════
//  МУЛЬТИФИЛЬТРЫ
// ══════════════════════════════════════════════════════════════════════════

/**
 * Дефолтный текст кнопок-триггеров мультифильтров (треугольник ▼).
 * Генерируется автоматически для каждого столбца.
 */
export const MF_DEFAULTS = Object.fromEntries(
  PP_COLUMNS.map(c => [c, '\u25BC'])
)

// ══════════════════════════════════════════════════════════════════════════
//  СТАТУСЫ СТРОК
// ══════════════════════════════════════════════════════════════════════════

/** Метки статус-панели (компактные pills) */
export const STATUS_LABELS = {
  all: 'Все',
  done: '\u2713',       // ✓
  overdue: '\u26A0',    // ⚠
  inwork: '\u27F3',     // ⟳
}

/**
 * Определяет статус строки ПП по её данным.
 * @param {Object} row — строка ПП
 * @returns {'done'|'overdue'|'inwork'}
 */
export function getRowStatus(row) {
  if (row.has_reports) return 'done'
  if (row.is_overdue) return 'overdue'
  return 'inwork'
}

// ══════════════════════════════════════════════════════════════════════════
//  СТОЛБЦЫ С ВЫПАДАЮЩИМИ СПИСКАМИ
// ══════════════════════════════════════════════════════════════════════════

/** Столбцы, которые отображаются как <select> (дропдаун) */
export const SELECT_COLUMNS = new Set([
  'dept', 'center', 'executor', 'task_type', 'sector_head',
])

/** Столбцы с текстовыми полями ввода */
export const TEXT_COLUMNS = new Set(['work_name', 'work_designation'])

/** Столбцы с датами */
export const DATE_COLUMNS = new Set(['date_start', 'date_end'])

/** Столбцы, нередактируемые в ПП (заполняются из ЕТБД / PPStage) */
export const READONLY_COLUMNS = new Set(['row_code', 'work_order'])

/** Столбцы расчёта трудоёмкости (sheets_a4 * norm * coeff = labor) */
export const LABOR_CALC_COLUMNS = new Set(['sheets_a4', 'norm', 'coeff'])

/**
 * Необязательные столбцы при синхронизации ПП → СП.
 * executor, center, sector_head, task_type — заполняются позже.
 */
export const SYNC_OPTIONAL_COLUMNS = new Set([
  'executor', 'center', 'sector_head', 'task_type',
])

// ══════════════════════════════════════════════════════════════════════════
//  ТИПЫ ЗАВИСИМОСТЕЙ
// ══════════════════════════════════════════════════════════════════════════

/** Типы связей для диалога зависимостей */
export const DEP_TYPES = [
  { value: 'FS', label: 'FS \u2014 \u041e\u043a\u043e\u043d\u0447\u0430\u043d\u0438\u0435\u2013\u041d\u0430\u0447\u0430\u043b\u043e' },
  { value: 'SS', label: 'SS \u2014 \u041d\u0430\u0447\u0430\u043b\u043e\u2013\u041d\u0430\u0447\u0430\u043b\u043e' },
  { value: 'FF', label: 'FF \u2014 \u041e\u043a\u043e\u043d\u0447\u0430\u043d\u0438\u0435\u2013\u041e\u043a\u043e\u043d\u0447\u0430\u043d\u0438\u0435' },
  { value: 'SF', label: 'SF \u2014 \u041d\u0430\u0447\u0430\u043b\u043e\u2013\u041e\u043a\u043e\u043d\u0447\u0430\u043d\u0438\u0435' },
]

/** Столбцы для экспорта в CSV */
export const EXPORT_COLUMNS = [
  { key: 'row_code',         header: 'Код строки',     width: 80,  forceText: true },
  { key: 'work_order',       header: 'Наряд-заказ',    width: 90,  forceText: true },
  { key: 'stage_num',        header: '№ этапа',        width: 60,  forceText: true },
  { key: 'milestone_num',    header: '№ вехи',         width: 60,  forceText: true },
  { key: 'work_num',         header: '№ работы',       width: 60,  forceText: true },
  { key: 'work_designation', header: 'Обозначение',    width: 140 },
  { key: 'work_name',        header: 'Наименование',   width: 240 },
  { key: 'date_start',       header: 'Начало',         width: 100 },
  { key: 'date_end',         header: 'Окончание',      width: 100 },
  { key: 'sheets_a4',        header: 'Ф, А4',          width: 60 },
  { key: 'norm',             header: 'Норматив',       width: 70 },
  { key: 'coeff',            header: 'Коэфф',          width: 60 },
  { key: 'labor',            header: 'Трудоёмкость',   width: 90 },
  { key: 'task_type',        header: 'Тип задачи',     width: 160 },
  { key: 'center',           header: 'Подразделение',  width: 90,  forceText: true },
  { key: 'dept',             header: 'Отдел',          width: 80,  forceText: true },
  { key: 'sector_head',      header: 'Сектор',         width: 100, forceText: true },
  { key: 'executor',         header: 'Разработчик',    width: 140 },
]

// ══════════════════════════════════════════════════════════════════════════
//  РЕЖИМЫ ОТОБРАЖЕНИЯ (скрытые столбцы по data-col-idx)
// ══════════════════════════════════════════════════════════════════════════

/** Индексы столбцов, скрываемых в каждом режиме (CSS .pp-view-*) */
export const PP_VIEW_HIDDEN = {
  compact: [1, 2, 3, 4, 5, 10, 11, 12, 13, 14],
  normal:  [1, 2, 3, 4, 5],
  full:    [],
}

/**
 * Форматирует «YYYY-MM» в читабельный вид «Март 2026».
 * @param {string} ym — строка формата 'YYYY-MM'
 * @returns {string}
 */
export function formatYearMonth(ym) {
  const [y, m] = ym.split('-')
  const mi = parseInt(m, 10) - 1
  return (MONTH_NAMES_RU[mi] || m) + ' ' + y
}
