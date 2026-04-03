/**
 * API-клиент для модуля «Управление предприятием».
 * Все запросы к /api/enterprise/ проходят через эти функции.
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
  return r.json()
}

// ══════════════════════════════════════════════════════════════════════════
//  ПОРТФЕЛЬ
// ══════════════════════════════════════════════════════════════════════════

/** Загрузить портфель проектов */
export async function fetchPortfolio() {
  const r = await fetch('/api/enterprise/portfolio/')
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

/** Обновить enterprise-поля проекта (статус, приоритет, ГК) */
export async function updateProject(id, data) {
  const r = await fetch(`/api/enterprise/portfolio/${id}/`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/**
 * Создать проект.
 * Шаг 1: POST /api/projects/create/ (базовые поля)
 * Шаг 2: PUT /api/enterprise/portfolio/<id>/ (enterprise-поля)
 * Возвращает результат второго запроса.
 */
export async function createProject(data) {
  // Базовые поля проекта (name_full, name_short, code)
  const r1 = await fetch('/api/projects/create/', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      name_full: data.name_full,
      name_short: data.name_short,
      code: data.code,
    }),
  })
  const proj = await handleResponse(r1)

  // Enterprise-поля (статус, приоритет, ГК)
  const r2 = await fetch(`/api/enterprise/portfolio/${proj.id}/`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify({
      status: data.status,
      priority_category: data.priority_category,
      priority_number: data.priority_number,
      chief_designer_id: data.chief_designer_id,
    }),
  })
  return handleResponse(r2)
}

// ══════════════════════════════════════════════════════════════════════════
//  ГЕНЕРАЛЬНЫЙ ГРАФИК (ГГ)
// ══════════════════════════════════════════════════════════════════════════

/** Загрузить ГГ для проекта */
export async function fetchGG(projectId) {
  const r = await fetch(`/api/enterprise/gg/${projectId}/`)
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

/** Создать ГГ для проекта */
export async function createGG(projectId) {
  const r = await fetch(`/api/enterprise/gg/${projectId}/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({}),
  })
  return handleResponse(r)
}

/** Создать пункт (stage) ГГ */
export async function createGGStage(projectId, data) {
  const r = await fetch(`/api/enterprise/gg/${projectId}/stages/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Обновить пункт (stage) ГГ */
export async function updateGGStage(id, data) {
  const r = await fetch(`/api/enterprise/gg_stages/${id}/`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Удалить пункт (stage) ГГ */
export async function deleteGGStage(id) {
  const r = await fetch(`/api/enterprise/gg_stages/${id}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}

/** Создать веху ГГ */
export async function createGGMilestone(projectId, data) {
  const r = await fetch(`/api/enterprise/gg/${projectId}/milestones/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Обновить веху ГГ (используется при drag в Ганте) */
export async function updateGGMilestone(id, data) {
  const r = await fetch(`/api/enterprise/gg_milestones/${id}/`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Удалить веху ГГ */
export async function deleteGGMilestone(id) {
  const r = await fetch(`/api/enterprise/gg_milestones/${id}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}

// ══════════════════════════════════════════════════════════════════════════
//  СКВОЗНОЙ ГРАФИК
// ══════════════════════════════════════════════════════════════════════════

/** Загрузить сквозной график для проекта */
export async function fetchCross(projectId) {
  const r = await fetch(`/api/enterprise/cross/${projectId}/`)
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

/**
 * Создать сквозной график.
 * @param {number} projectId
 * @param {Object} opts — например { from_gg: true }
 */
export async function createCross(projectId, opts = {}) {
  const r = await fetch(`/api/enterprise/cross/${projectId}/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(opts),
  })
  return handleResponse(r)
}

/** Обновить настройки сквозного графика (edit_owner, granularity) */
export async function updateCrossSettings(projectId, data) {
  const r = await fetch(`/api/enterprise/cross/${projectId}/`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Создать этап сквозного графика */
export async function createCrossStage(projectId, data) {
  const r = await fetch(`/api/enterprise/cross/${projectId}/stages/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Обновить этап сквозного графика */
export async function updateCrossStage(id, data) {
  const r = await fetch(`/api/enterprise/cross_stages/${id}/`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Удалить этап сквозного графика */
export async function deleteCrossStage(id) {
  const r = await fetch(`/api/enterprise/cross_stages/${id}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}

/** Создать веху сквозного графика */
export async function createCrossMilestone(projectId, data) {
  const r = await fetch(`/api/enterprise/cross/${projectId}/milestones/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Удалить веху сквозного графика */
export async function deleteCrossMilestone(id) {
  const r = await fetch(`/api/enterprise/cross_milestones/${id}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}

/** Привязать работы ПП к этапу сквозного графика */
export async function assignWorks(stageId, workIds) {
  const r = await fetch(`/api/enterprise/cross_stages/${stageId}/works/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ work_ids: workIds }),
  })
  return handleResponse(r)
}

/** Отвязать работу от этапа сквозного графика */
export async function unlinkWork(stageId, workId) {
  const r = await fetch(`/api/enterprise/cross_stages/${stageId}/works/`, {
    method: 'DELETE',
    headers: headers(),
    body: JSON.stringify({ work_ids: [workId] }),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}

// ══════════════════════════════════════════════════════════════════════════
//  СНИМКИ (BASELINES)
// ══════════════════════════════════════════════════════════════════════════

/** Загрузить список снимков для проекта */
export async function fetchBaselines(projectId) {
  const r = await fetch(`/api/enterprise/cross/${projectId}/baselines/`)
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

/** Создать снимок */
export async function createBaseline(projectId, comment = '') {
  const r = await fetch(`/api/enterprise/cross/${projectId}/baselines/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ comment }),
  })
  return handleResponse(r)
}

/** Удалить снимок */
export async function deleteBaseline(id) {
  const r = await fetch(`/api/enterprise/baselines/${id}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}

/** Загрузить конкретный снимок (для просмотра/сравнения) */
export async function fetchBaseline(id) {
  const r = await fetch(`/api/enterprise/baselines/${id}/`)
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

// ══════════════════════════════════════════════════════════════════════════
//  ЗАГРУЗКА / МОЩНОСТЬ (CAPACITY)
// ══════════════════════════════════════════════════════════════════════════

/**
 * Загрузить данные по мощности/загрузке.
 * @param {Object} params — { year, mode, project_id? }
 */
export async function fetchCapacity(params = {}) {
  const qs = new URLSearchParams()
  if (params.year) qs.set('year', params.year)
  if (params.mode) qs.set('mode', params.mode)
  if (params.project_id) qs.set('project_id', params.project_id)
  const r = await fetch(`/api/enterprise/capacity/?${qs}`)
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

// ══════════════════════════════════════════════════════════════════════════
//  СЦЕНАРИИ «ЧТО-ЕСЛИ»
// ══════════════════════════════════════════════════════════════════════════

/**
 * Загрузить список сценариев.
 * @param {Object} params — { status?, project_id? }
 */
export async function fetchScenarios(params = {}) {
  const qs = new URLSearchParams()
  if (params.status) qs.set('status', params.status)
  if (params.project_id) qs.set('project_id', params.project_id)
  const r = await fetch(`/api/enterprise/scenarios/?${qs}`)
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

/** Загрузить конкретный сценарий с записями */
export async function fetchScenario(id) {
  const r = await fetch(`/api/enterprise/scenarios/${id}/`)
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

/** Создать сценарий */
export async function createScenario(data) {
  const r = await fetch('/api/enterprise/scenarios/', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Обновить сценарий */
export async function updateScenario(id, data) {
  const r = await fetch(`/api/enterprise/scenarios/${id}/`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Удалить сценарий */
export async function deleteScenario(id) {
  const r = await fetch(`/api/enterprise/scenarios/${id}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}

/** Создать запись (entry) в сценарии */
export async function createScenarioEntry(scenarioId, data) {
  const r = await fetch(`/api/enterprise/scenarios/${scenarioId}/entries/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  })
  return handleResponse(r)
}

/** Удалить запись (entry) из сценария */
export async function deleteScenarioEntry(scenarioId, entryId) {
  const r = await fetch(`/api/enterprise/scenarios/${scenarioId}/entries/${entryId}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw data
  }
}
