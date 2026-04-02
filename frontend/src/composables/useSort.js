/**
 * Composable для сортировки таблицы по столбцу.
 */
import { reactive } from 'vue'

export function useSort() {
  const state = reactive({ col: null, dir: 'asc' })

  function toggle(col) {
    if (state.col === col) {
      state.dir = state.dir === 'asc' ? 'desc' : 'asc'
    } else {
      state.col = col
      state.dir = 'asc'
    }
  }

  function applySortToArray(items, getter) {
    if (!state.col) return items
    const sorted = [...items]
    const dir = state.dir === 'asc' ? 1 : -1
    sorted.sort((a, b) => {
      const va = getter(a, state.col) || ''
      const vb = getter(b, state.col) || ''
      return String(va).localeCompare(String(vb), 'ru') * dir
    })
    return sorted
  }

  return { state, toggle, applySortToArray }
}
