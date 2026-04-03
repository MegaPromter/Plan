<template>
  <!--
    PPGanttView — диаграмма Ганта для модуля ПП.
    Lazy-загружает dhtmlxGantt, настраивает колонки, масштабы,
    drag-редактирование (если isWriter), custom resize колонок.

    Порт логики из production_plan.js: ppLoadGantt, ppSetupGantt,
    ppRenderGantt, ppSetGanttScale и gantt_common.js.
  -->
  <div v-show="active" ref="containerRef" class="pp-gantt-wrap">
    <!-- Кнопки масштаба (показываются вместе с Гантом) -->
    <div ref="scaleGroupRef" class="gantt-scale-group" id="ppGanttScaleGroup">
      <button
        v-for="s in scales"
        :key="s.key"
        class="btn btn-sm"
        :class="{ active: currentScale === s.key }"
        :data-scale="s.key"
        @click="setScale(s.key)"
      >
        {{ s.label }}
      </button>
    </div>

    <!-- Контейнер для dhtmlxGantt -->
    <div
      id="ppGanttContainer"
      ref="ganttEl"
      style="width: 100%; height: 500px;"
    ></div>
  </div>
</template>

<script setup>
/**
 * PPGanttView — компонент диаграммы Ганта для ПП.
 *
 * Функции:
 * - Lazy-загрузка библиотеки dhtmlxGantt (CSS + JS) через динамический <script>
 * - Масштабы: день / неделя / месяц / год с сохранением в localStorage
 * - Колонки: задача, обозначение, наименование, начало, окончание
 * - Ширины колонок сохраняются в localStorage
 * - Read-only режим (нет drag) если не isWriter
 * - Drag для редактирования дат → PUT /api/production_plan/<id>/?field=date_start|date_end
 * - Custom resize колонок (GPL не поддерживает встроенный)
 */
import { ref, watch, onMounted, onUnmounted, nextTick, inject } from 'vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'
import { updatePPField } from '../../api/pp.js'

// ── Props ───────────────────────────────────────────────────────────────
const props = defineProps({
  /** Отфильтрованные строки ПП */
  rows:   { type: Array, default: () => [] },
  /** Активна ли панель Ганта (v-show) */
  active: { type: Boolean, default: false },
})

// ── Store ───────────────────────────────────────────────────────────────
const store = inject(PP_STORE_KEY)
const isWriter = store.isWriter

// ── Refs ────────────────────────────────────────────────────────────────
const containerRef = ref(null)
const ganttEl = ref(null)
const scaleGroupRef = ref(null)

// ── Состояние ───────────────────────────────────────────────────────────
const ganttLoaded = ref(false)
const ganttInited = ref(false)
const currentScale = ref(localStorage.getItem('pp_gantt_scale') || 'year')

// ── Константы масштабов ─────────────────────────────────────────────────
const scales = [
  { key: 'day',   label: 'День' },
  { key: 'week',  label: 'Неделя' },
  { key: 'month', label: 'Месяц' },
  { key: 'year',  label: 'Год' },
]

// ── Ключи localStorage для ширин колонок ────────────────────────────────
const COL_STORAGE_KEY = 'pp_gantt_col_widths'
const COL_DEFAULTS = {
  text: 200,
  designation: 140,
  work_name_full: 160,
  start_date: 90,
  end_date: 90,
  grid: 670,
}

// ── Утилиты ─────────────────────────────────────────────────────────────

/** Date -> "YYYY-MM-DD" */
function formatDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

/** Загрузка сохранённых ширин колонок */
function loadColWidths() {
  try {
    const saved = JSON.parse(localStorage.getItem(COL_STORAGE_KEY))
    if (saved) return { ...COL_DEFAULTS, ...saved }
  } catch (e) { /* ignore */ }
  return { ...COL_DEFAULTS }
}

/** Сохранение ширин колонок */
function saveColWidths() {
  if (typeof gantt === 'undefined') return
  const data = { grid: gantt.config.grid_width }
  gantt.config.columns.forEach(c => { data[c.name] = c.width })
  localStorage.setItem(COL_STORAGE_KEY, JSON.stringify(data))
}

// ── Lazy-загрузка dhtmlxGantt ───────────────────────────────────────────

function loadGanttLib(onReady) {
  if (typeof gantt !== 'undefined') {
    onReady()
    return
  }
  // CSS
  if (!document.querySelector('link[href*="dhtmlxgantt.css"]')) {
    const css = document.createElement('link')
    css.rel = 'stylesheet'
    css.href = '/static/lib/dhtmlxgantt/dhtmlxgantt.css'
    document.head.appendChild(css)
  }
  // JS
  const script = document.createElement('script')
  script.src = '/static/lib/dhtmlxgantt/dhtmlxgantt.js'
  script.onload = onReady
  script.onerror = () => {
    if (ganttEl.value) {
      ganttEl.value.innerHTML =
        '<div style="padding:40px;text-align:center;color:var(--muted);">' +
        '\u26A0 Библиотека dhtmlxGantt не загружена.</div>'
    }
  }
  document.head.appendChild(script)
}

// ── Русская локаль ──────────────────────────────────────────────────────

function applyLocaleRu() {
  gantt.locale = {
    date: {
      month_full: ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'],
      month_short: ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'],
      day_full: ['Воскресенье','Понедельник','Вторник','Среда','Четверг','Пятница','Суббота'],
      day_short: ['Вс','Пн','Вт','Ср','Чт','Пт','Сб'],
    },
    labels: {
      new_task: 'Новая задача', icon_save: 'Сохранить', icon_cancel: 'Отмена',
      icon_details: 'Детали', icon_edit: 'Редактировать', icon_delete: 'Удалить',
      confirm_closing: '', confirm_deleting: 'Удалить запись?',
      section_description: 'Описание', section_time: 'Период', section_type: 'Тип',
      column_text: 'Задача', column_start_date: 'Начало', column_duration: 'Длительность',
      column_add: '', link: 'Связь', confirm_link_deleting: 'Удалить связь?',
      link_start: '(начало)', link_end: '(конец)',
      type_task: 'Задача', type_project: 'Проект', type_milestone: 'Веха',
      minutes: 'мин', hours: 'ч', days: 'дн', weeks: 'нед', months: 'мес', years: 'лет',
    },
  }
}

// ── Применение масштаба ─────────────────────────────────────────────────

function applyScale(scale) {
  if (typeof gantt === 'undefined') return
  switch (scale) {
    case 'day':
      gantt.config.scales = [
        { unit: 'month', step: 1, format: '%M %Y' },
        { unit: 'day', step: 1, format: '%d' },
      ]
      gantt.config.min_column_width = 28
      break
    case 'week':
      gantt.config.scales = [
        { unit: 'month', step: 1, format: '%M %Y' },
        { unit: 'week', step: 1, format: '%d' },
      ]
      gantt.config.min_column_width = 60
      break
    case 'month':
      gantt.config.scales = [
        { unit: 'year', step: 1, format: '%Y' },
        { unit: 'month', step: 1, format: '%M' },
      ]
      gantt.config.min_column_width = 50
      break
    default: // year
      gantt.config.scales = [
        { unit: 'year', step: 1, format: '%Y' },
      ]
      gantt.config.min_column_width = 80
  }
}

function setScale(scale) {
  currentScale.value = scale
  localStorage.setItem('pp_gantt_scale', scale)
  applyScale(scale)
  if (ganttInited.value) gantt.render()
}

// ── Авто-высота строк (перенос текста) ──────────────────────────────────

function autoFitRowHeights() {
  if (typeof gantt === 'undefined') return
  const skipCols = new Set(['add', 'start_date', 'end_date', 'duration'])
  const cols = gantt.config.columns.filter(c => !skipCols.has(c.name))
  const measure = document.createElement('div')
  measure.style.cssText = 'position:absolute;visibility:hidden;white-space:normal;word-break:break-word;' +
    'line-height:1.4;font:inherit;padding:4px 0;box-sizing:border-box;'
  document.body.appendChild(measure)

  gantt.eachTask(task => {
    let maxH = 36
    cols.forEach(col => {
      const val = col.name === 'text' ? task.text : (task[col.name] || '')
      if (!val) return
      measure.style.width = (col.width - 28) + 'px'
      measure.textContent = val
      maxH = Math.max(maxH, measure.offsetHeight + 16)
    })
    task.row_height = maxH
  })
  document.body.removeChild(measure)
}

// ── Custom resize колонок (GPL) ─────────────────────────────────────────
let _resizing = false

function injectResizers() {
  if (_resizing) return
  const container = ganttEl.value
  if (!container) return
  container.querySelectorAll('.gantt-col-resizer, .gantt-grid-resizer').forEach(r => r.remove())

  // Resize колонок заголовка
  const headerRow = container.querySelector('.gantt_grid_scale')
  if (headerRow) {
    const cells = headerRow.querySelectorAll('.gantt_grid_head_cell')
    cells.forEach((cell, idx) => {
      if (idx >= cells.length - 1) return
      const handle = document.createElement('div')
      handle.className = 'gantt-col-resizer'
      cell.style.position = 'relative'
      cell.appendChild(handle)
      attachColResize(handle, idx)
    })
  }

  // Resize grid <-> timeline
  const grid = container.querySelector('.gantt_grid')
  if (grid) {
    const splitter = document.createElement('div')
    splitter.className = 'gantt-grid-resizer'
    grid.style.position = 'relative'
    grid.appendChild(splitter)
    attachGridSplitter(splitter, grid)
  }
}

function attachColResize(handle, colIdx) {
  let startX, startW
  handle.addEventListener('mousedown', e => {
    e.preventDefault()
    e.stopPropagation()
    startX = e.clientX
    startW = gantt.config.columns[colIdx].width
    _resizing = true
    const onMove = ev => {
      const delta = ev.clientX - startX
      const newW = Math.max(40, startW + delta)
      gantt.config.columns[colIdx].width = newW
      gantt.config.grid_width = gantt.config.columns.reduce((s, c) => s + c.width, 0)
      gantt.render()
    }
    const onUp = () => {
      _resizing = false
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      saveColWidths()
      injectResizers()
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  })
}

function attachGridSplitter(splitter, grid) {
  let startX, startColW
  splitter.addEventListener('mousedown', e => {
    e.preventDefault()
    e.stopPropagation()
    startX = e.clientX
    const lastCol = gantt.config.columns[gantt.config.columns.length - 1]
    startColW = lastCol.width
    const startGridW = grid.offsetWidth
    _resizing = true
    const onMove = ev => {
      const delta = ev.clientX - startX
      const newColW = Math.max(40, startColW + delta)
      lastCol.width = newColW
      gantt.config.grid_width = startGridW - startColW + newColW
      gantt.render()
    }
    const onUp = () => {
      _resizing = false
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      saveColWidths()
      injectResizers()
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  })
}

// ── Настройка Ганта ─────────────────────────────────────────────────────

function setupGantt() {
  if (typeof gantt === 'undefined') return
  applyLocaleRu()

  gantt.config.date_format = '%Y-%m-%d'
  gantt.config.smart_rendering = false
  gantt.config.fit_tasks = true
  gantt.config.open_tree_initially = true

  // Tooltip
  gantt.config.tooltip_offset_x = 10
  gantt.config.tooltip_offset_y = 20
  gantt.templates.tooltip_text = (start, end, task) => {
    return '<b>' + task.text + '</b><br/>' +
      gantt.templates.tooltip_date_format(start) + ' \u2014 ' +
      gantt.templates.tooltip_date_format(end)
  }

  // Колонки с сохранёнными ширинами
  const cw = loadColWidths()
  gantt.config.columns = [
    { name: 'text', label: 'Задача', width: cw.text, tree: false },
    { name: 'designation', label: 'Обозначение', width: cw.designation, align: 'left' },
    { name: 'work_name_full', label: 'Наименование', width: cw.work_name_full, align: 'left' },
    { name: 'start_date', label: 'Начало', align: 'center', width: cw.start_date },
    { name: 'end_date', label: 'Окончание', align: 'center', width: cw.end_date },
  ]
  gantt.config.grid_width = cw.grid

  // Режим: readonly / drag
  gantt.config.readonly = !isWriter
  gantt.config.show_links = false
  gantt.config.drag_links = false
  gantt.config.drag_move = isWriter
  gantt.config.drag_resize = isWriter
  gantt.config.drag_progress = false

  // Восстанавливаем масштаб
  applyScale(currentScale.value)

  // Инициализация
  gantt.init('ppGanttContainer')
  ganttInited.value = true

  // Вставляем ресайзеры после каждого рендера
  gantt.attachEvent('onGanttRender', () => injectResizers())

  // Drag -> сохранение дат на сервере
  if (isWriter) {
    gantt.attachEvent('onAfterTaskDrag', (id) => {
      const task = gantt.getTask(id)
      if (!task) return
      const startStr = formatDate(task.start_date)
      const endStr = formatDate(task.end_date)

      Promise.all([
        updatePPField(id, 'date_start', startStr),
        updatePPField(id, 'date_end', endStr),
      ]).then(([r1, r2]) => {
        // Обновить в store
        const row = store.rows.value.find(r => r.id === id)
        if (row) {
          row.date_start = startStr
          row.date_end = endStr
        }
      }).catch(() => {
        alert('Ошибка сохранения дат')
        renderGantt()
      })
    })
  }
}

// ── Рендер данных ───────────────────────────────────────────────────────

function renderGantt() {
  if (typeof gantt === 'undefined' || !store.currentProjectId.value) return
  try {
    // Используем строки из props (отфильтрованные)
    const filteredRows = props.rows.filter(r => r.date_end)
    const ganttData = {
      data: filteredRows.map(r => ({
        id: r.id,
        text: r.work_name || r.work_num || '#' + r.id,
        designation: r.work_designation || '',
        work_name_full: r.work_name || '',
        start_date: r.date_start || r.date_end,
        end_date: r.date_end,
      })),
      links: [],
    }
    gantt.clearAll()
    gantt.parse(ganttData)
    autoFitRowHeights()
    gantt.render()
  } catch (e) {
    console.error('PPGanttView: renderGantt error:', e)
  }
}

// ── Загрузка Ганта при первой активации ─────────────────────────────────

watch(() => props.active, async (isActive) => {
  if (!isActive) return
  if (!ganttLoaded.value) {
    ganttLoaded.value = true
    await nextTick()
    loadGanttLib(() => {
      setupGantt()
      renderGantt()
    })
  } else if (ganttInited.value) {
    // Повторная активация — перерисовать с актуальными данными
    await nextTick()
    renderGantt()
  }
})

// Перерисовка при изменении данных (если Гант активен)
watch(() => props.rows, () => {
  if (props.active && ganttInited.value) {
    renderGantt()
  }
}, { deep: true })

// Экспортируем для родительского компонента
defineExpose({ renderGantt, setScale, currentScale })
</script>
