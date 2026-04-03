/**
 * Composable для управления состоянием в URL hash.
 *
 * Формат хеша: #tab=portfolio&project=5
 * При пустом хеше — восстановление из localStorage('ent_last_state').
 *
 * Используется для навигации по вкладкам Enterprise SPA и
 * восстановления последнего состояния при повторном визите.
 */
import { ref, onMounted, onUnmounted, watch } from 'vue'

const LS_KEY = 'ent_last_state'

/**
 * Парсит URL hash в объект параметров.
 * '#tab=portfolio&project=5' → { tab: 'portfolio', project: '5' }
 */
function parseHash() {
  const h = location.hash.replace('#', '')
  const params = {}
  h.split('&').forEach(part => {
    const [k, v] = part.split('=')
    if (k) params[k] = decodeURIComponent(v || '')
  })
  return params
}

/**
 * Записывает параметры в URL hash и дублирует в localStorage.
 * @param {Object} updates — пары ключ-значение для обновления
 */
function saveHashState(updates) {
  const params = parseHash()
  Object.assign(params, updates)
  const parts = []
  for (const k in params) {
    if (params[k]) parts.push(k + '=' + encodeURIComponent(params[k]))
  }
  history.replaceState(null, '', '#' + parts.join('&'))
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(params))
  } catch (e) { /* localStorage недоступен */ }
}

/**
 * @param {Object} store — экземпляр enterpriseStore (из createEnterpriseStore)
 */
export function useHashRouter(store) {
  let _restored = false

  /**
   * Восстанавливает состояние из hash или localStorage.
   * Вызывается один раз при монтировании компонента.
   */
  function restore() {
    if (_restored) return
    _restored = true

    let params = parseHash()

    // Если hash пуст — восстанавливаем из localStorage
    if (!params.tab && !params.project) {
      try {
        const saved = JSON.parse(localStorage.getItem(LS_KEY) || '{}')
        if (saved.tab) params = saved
      } catch (e) { /* невалидный JSON */ }
    }

    const tab = params.tab || 'portfolio'
    store.currentTab.value = tab

    // Восстанавливаем выбранный проект
    const pid = params.project
    if (pid) {
      store.selectedProjectId.value = Number(pid) || null
    }
  }

  /**
   * Синхронизирует изменения store → URL hash.
   */
  function syncToHash() {
    const updates = {}
    if (store.currentTab.value) updates.tab = store.currentTab.value
    if (store.selectedProjectId.value) updates.project = String(store.selectedProjectId.value)
    else updates.project = ''
    saveHashState(updates)
  }

  // Обработчик события hashchange (навигация кнопками браузера)
  function onHashChange() {
    const params = parseHash()
    if (params.tab && params.tab !== store.currentTab.value) {
      store.currentTab.value = params.tab
    }
    const pid = params.project ? Number(params.project) : null
    if (pid !== store.selectedProjectId.value) {
      store.selectedProjectId.value = pid
    }
  }

  onMounted(() => {
    window.addEventListener('hashchange', onHashChange)
    restore()
  })

  onUnmounted(() => {
    window.removeEventListener('hashchange', onHashChange)
  })

  // Следим за изменениями в store и обновляем hash
  watch(() => store.currentTab.value, () => syncToHash())
  watch(() => store.selectedProjectId.value, () => syncToHash())

  return {
    /** Парсит текущий hash */
    parseHash,
    /** Обновляет hash вручную (для кастомных параметров) */
    saveHashState,
    /** Восстанавливает состояние из hash/localStorage */
    restore,
  }
}
