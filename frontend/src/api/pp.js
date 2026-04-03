/**
 * API-клиент для модуля «Производственный план».
 * Все запросы к /api/production_plan/, /api/pp_projects/,
 * /api/directories/, /api/projects/, /api/tasks/, /api/dependencies/
 * проходят через эти функции.
 */

function getCsrfToken() {
  const el = document.querySelector('[name=csrfmiddlewaretoken]')
  if (el) return el.value
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match ? match[1] : ''
}

const headers = () => ({
  'Content-Type': 'application/json',
  'X-CSRFToken': getCsrfToken(),
})

/**
 * Обработка ответа: при HTTP-ошибке парсим JSON тела и выбрасываем.
 * Формат ошибки: { error: '...' } — совместим с Django API.
 */
async function handleResponse(r) {
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
  // 204 No Content — нет тела ответа
  if (r.status === 204) return {}
  return r.json()
}

// ══════════════════════════════════════════════════════════════════════════
//  СПРАВОЧНИКИ
// ══════════════════════════════════════════════════════════════════════════

/**
 * Загрузить справочники (отделы, НТЦ, сотрудники, типы задач и т.д.)
 * Cache-bust через timestamp чтобы не получать устаревшие данные.
 */
export async function fetchDirectories() {
  const r = await fetch('/api/directories/?t=' + Date.now())
  if (!r.ok) throw new Error('HTTP ' + r.status)
  const data = await r.json()
  // API возвращает секторы под ключом 'sector'; для колонки 'sector_head'
  // создаём алиас, чтобы компоненты могли читать dirs.sector_head
  if (data.sector && !data.sector_head) data.sector_head = data.sector
  return data
}

// ══════════════════════════════════════════════════════════════════════════
//  ПП-ПРОЕКТЫ
// ══════════════════════════════════════════════════════════════════════════

/** Загрузить список ПП-проектов текущего пользователя */
export async function fetchPPProjects() {
  const r = await fetch('/api/pp_projects/')
  if (!r.ok) throw new Error('HTTP ' + r.status)
  const data = await r.json()
  return Array.isArray(data) ? data : (data.results || [])
}

/** Создать новый ПП-проект (план) */
export async function createPPProject(data) {
  const r = await fetch('/api/pp_projects/create/', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Обновить ПП-проект (название, привязка к УП) */
export async function updatePPProject(id, data) {
  const r = await fetch(`/api/pp_projects/${id}/`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Удалить ПП-проект со всеми строками */
export async function deletePPProject(id) {
  const r = await fetch(`/api/pp_projects/${id}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}

// ══════════════════════════════════════════════════════════════════════════
//  СТРОКИ ПП (PRODUCTION PLAN ROWS)
// ══════════════════════════════════════════════════════════════════════════

/**
 * Загрузить строки производственного плана для конкретного проекта.
 * @param {number|string} projectId — ID ПП-проекта
 * @returns {Array} массив строк (уже развёрнутый в обратном порядке — новые вверху)
 */
export async function fetchPPRows(projectId) {
  const r = await fetch('/api/production_plan/?project_id=' + projectId)
  if (!r.ok) throw new Error('HTTP ' + r.status)
  const data = await r.json()
  const rows = Array.isArray(data) ? data : (data.results || [])
  // Обратный порядок: новые строки отображаются вверху
  rows.reverse()
  return rows
}

/** Создать новую строку ПП */
export async function createPPRow(data) {
  const r = await fetch('/api/production_plan/create/', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/**
 * Обновить одно поле строки ПП (инлайн-редактирование).
 * PUT /api/production_plan/<id>/?field=<field>
 * @param {number|string} rowId — ID строки
 * @param {string} field — имя поля (например 'work_name', 'dept')
 * @param {*} value — новое значение
 */
export async function updatePPField(rowId, field, value) {
  const r = await fetch(`/api/production_plan/${rowId}/?field=${field}`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify({ value }),
  })
  return handleResponse(r)
}

/** Удалить строку ПП */
export async function deletePPRow(id) {
  const r = await fetch(`/api/production_plan/${id}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}

// ══════════════════════════════════════════════════════════════════════════
//  СИНХРОНИЗАЦИЯ ПП → СП (план/отчёт)
// ══════════════════════════════════════════════════════════════════════════

/**
 * Синхронизировать строки ПП с модулем «План/отчёт».
 * POST /api/production_plan/sync/
 * @param {Object} data — { project_id: number, ids: number[] }
 */
export async function syncToTasks(data) {
  const r = await fetch('/api/production_plan/sync/', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

// ══════════════════════════════════════════════════════════════════════════
//  ЭТАПЫ ПРОЕКТА УП (PP STAGES)
// ══════════════════════════════════════════════════════════════════════════

/**
 * Загрузить этапы проекта УП (для привязки к этапам ПП).
 * GET /api/projects/<projectId>/stages/
 */
export async function fetchProjectStages(projectId) {
  const r = await fetch(`/api/projects/${projectId}/stages/`)
  if (!r.ok) return []
  return r.json()
}

// ══════════════════════════════════════════════════════════════════════════
//  ЗАВИСИМОСТИ ЗАДАЧ (DEPENDENCIES)
// ══════════════════════════════════════════════════════════════════════════

/**
 * Загрузить зависимости задачи (предшественники + последователи).
 * GET /api/tasks/<taskId>/dependencies/
 */
export async function fetchDependencies(taskId) {
  const r = await fetch(`/api/tasks/${taskId}/dependencies/`, {
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

/**
 * Добавить зависимость к задаче.
 * POST /api/tasks/<taskId>/dependencies/
 * @param {number|string} taskId — ID задачи (successor)
 * @param {Object} data — { predecessor_id, dep_type, lag_days }
 */
export async function addDependency(taskId, data) {
  const r = await fetch(`/api/tasks/${taskId}/dependencies/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/**
 * Удалить зависимость по ID.
 * DELETE /api/dependencies/<depId>/
 */
export async function deleteDependency(depId) {
  const r = await fetch(`/api/dependencies/${depId}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}

/**
 * Выравнивание дат по зависимостям.
 * POST /api/tasks/<taskId>/align_dates/
 * @param {number|string} taskId
 * @param {Object} data — { cascade: boolean }
 */
export async function alignDates(taskId, data) {
  const r = await fetch(`/api/tasks/${taskId}/align_dates/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

// ══════════════════════════════════════════════════════════════════════════
//  ПРОЕКТЫ УП (для привязки ПП → УП)
// ══════════════════════════════════════════════════════════════════════════

/**
 * Загрузить все проекты модуля «Управление проектами» (с изделиями).
 * GET /api/projects/
 */
export async function fetchUpProjects() {
  const r = await fetch('/api/projects/')
  if (!r.ok) throw new Error('HTTP ' + r.status)
  const data = await r.json()
  return Array.isArray(data) ? data : []
}
