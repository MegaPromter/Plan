/**
 * Composable для ленивой (chunk-based) отрисовки списка.
 *
 * При прокрутке контейнера добавляет новые порции элементов,
 * пока не будут показаны все. Аналогично _ppAppendBatch + createScrollLoader
 * из production_plan.js.
 *
 * @param {Ref<HTMLElement|null>} containerRef — реф на DOM-контейнер со скроллом
 * @param {Ref<Array>} allItems — полный массив отфильтрованных/отсортированных элементов
 * @param {number} chunkSize — количество элементов в одной порции (по умолчанию 50)
 */
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'

export function useLazyScroll(containerRef, allItems, chunkSize = 50) {
  // Количество отрисованных элементов
  const renderedCount = ref(0)

  // Видимый срез (первые renderedCount из allItems)
  const renderedItems = ref([])

  /** Добавить следующую порцию элементов */
  function appendNextChunk() {
    const all = allItems.value
    if (renderedCount.value >= all.length) return
    const end = Math.min(renderedCount.value + chunkSize, all.length)
    renderedCount.value = end
    renderedItems.value = all.slice(0, end)
  }

  /** Сбросить и начать заново (первая порция) */
  function reset() {
    renderedCount.value = 0
    renderedItems.value = []
    nextTick(() => {
      appendNextChunk()
    })
  }

  /** Все ли элементы уже отрисованы (computed — реактивно обновляется) */
  const allRendered = computed(() => renderedCount.value >= allItems.value.length)

  // ── Обработчик прокрутки ────────────────────────────────────────────────
  let _scrollHandler = null
  let _currentEl = null

  function attachScroll(el) {
    detachScroll()
    if (!el) return
    _currentEl = el
    _scrollHandler = _throttle(() => {
      // Если прокрутили до низа (с запасом 200px) — подгружаем
      const { scrollTop, scrollHeight, clientHeight } = el
      if (scrollTop + clientHeight >= scrollHeight - 200) {
        appendNextChunk()
      }
    }, 150)
    el.addEventListener('scroll', _scrollHandler, { passive: true })
  }

  function detachScroll() {
    if (_currentEl && _scrollHandler) {
      _currentEl.removeEventListener('scroll', _scrollHandler)
    }
    _scrollHandler = null
    _currentEl = null
  }

  // При изменении allItems — сброс и перерисовка
  watch(allItems, () => {
    reset()
  })

  // При изменении containerRef — перевесить слушатель
  watch(containerRef, (el) => {
    if (el) attachScroll(el)
    else detachScroll()
  }, { immediate: true })

  onUnmounted(() => {
    detachScroll()
  })

  return { renderedItems, renderedCount, appendNextChunk, reset, allRendered, attachScroll }
}

// ── Вспомогательный throttle ────────────────────────────────────────────
function _throttle(fn, delay) {
  let last = 0
  return function (...args) {
    const now = Date.now()
    if (now - last >= delay) {
      last = now
      fn.apply(this, args)
    }
  }
}
