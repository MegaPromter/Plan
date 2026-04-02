/**
 * Composable для мультифильтрации таблицы.
 * Реактивно хранит выбранные значения по каждому столбцу.
 */
import { reactive, computed } from 'vue'

export function useMultiFilter(data, columns) {
  // { col_name: Set(['значение1', 'значение2']), ... }
  const filters = reactive({})

  /** Получить уникальные значения столбца из данных */
  function getValues(col) {
    const vals = new Set()
    data.value.forEach(row => {
      const v = String(row[col] || '')
      if (v) vals.add(v)
    })
    return [...vals].sort((a, b) => a.localeCompare(b, 'ru'))
  }

  /** Установить фильтр для столбца */
  function setFilter(col, selectedSet) {
    if (!selectedSet || selectedSet.size === 0) {
      delete filters[col]
    } else {
      filters[col] = selectedSet
    }
  }

  /** Сбросить фильтр столбца */
  function clearFilter(col) {
    delete filters[col]
  }

  /** Сбросить все фильтры */
  function clearAll() {
    Object.keys(filters).forEach(k => delete filters[k])
  }

  /** Применить все фильтры к массиву данных */
  function applyFilters(items) {
    return items.filter(row => {
      for (const [col, sel] of Object.entries(filters)) {
        if (!sel || sel.size === 0) continue
        const cell = String(row[col] || '')
        if (!sel.has(cell)) return false
      }
      return true
    })
  }

  return { filters, getValues, setFilter, clearFilter, clearAll, applyFilters }
}
