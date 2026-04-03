/**
 * Константы модуля «Управление предприятием».
 * Метки статусов, приоритетов, порядок сортировки и другие справочники.
 */

/** Метки статусов проекта */
export const STATUS_LABELS = {
  prospective: 'Перспективный',
  approved:    'Утверждён',
  active:      'Активный',
  suspended:   'Приостановлен',
  deferred:    'Отложен',
  closed:      'Закрыт',
  cancelled:   'Отменён',
}

/** Метки приоритетов */
export const PRIORITY_LABELS = {
  critical: 'Критический',
  high:     'Высокий',
  medium:   'Средний',
  low:      'Низкий',
}

/** Порядок приоритетов для сортировки (меньше = важнее) */
export const PRIORITY_ORDER = {
  critical: 0,
  high:     1,
  medium:   2,
  low:      3,
}

/** Метки режима владения графиком (edit_owner) */
export const EDIT_OWNER_LABELS = {
  cross:  'Сквозной',
  pp:     'ПП',
  locked: 'Заблокирован',
}

/** Названия месяцев (русские, индекс 0-11) */
export const MONTH_NAMES = [
  'Январь', 'Февраль', 'Март', 'Апрель',
  'Май', 'Июнь', 'Июль', 'Август',
  'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

/** Метки статусов сценария */
export const SCENARIO_STATUS_LABELS = {
  draft:    'Черновик',
  active:   'Активный',
  archived: 'Архив',
}
