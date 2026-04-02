/**
 * API-клиент для Журнала извещений.
 * Все запросы к /api/journal/ проходят через эти функции.
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

/** Загрузить все извещения */
export async function fetchNotices() {
  const r = await fetch('/api/journal/?per_page=500')
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

/** Создать извещение */
export async function createNotice(payload) {
  const r = await fetch('/api/journal/create/', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(payload),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.error || 'Ошибка создания')
  return data
}

/** Обновить извещение */
export async function updateNotice(id, payload) {
  const r = await fetch(`/api/journal/${id}/`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(payload),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.error || 'Ошибка сохранения')
  return data
}

/** Удалить извещение */
export async function deleteNotice(id) {
  const r = await fetch(`/api/journal/${id}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw new Error(data.error || 'Ошибка удаления')
  }
}

/** Загрузить сотрудников отдела (для селекта исполнителя при погашении) */
export async function fetchDeptEmployees(deptCode) {
  const r = await fetch(`/api/dept_employees/?dept=${encodeURIComponent(deptCode)}`)
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}
