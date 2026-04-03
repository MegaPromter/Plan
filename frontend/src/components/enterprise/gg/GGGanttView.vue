<template>
  <!-- Гант-вид генерального графика -->
  <div>
    <!-- Кнопки масштаба -->
    <div class="gg-gantt-scales" ref="scalesEl">
      <button
        v-for="s in scales"
        :key="s.key"
        class="btn btn-xs btn-ghost"
        :class="{ active: currentScale === s.key }"
        @click="setScale(s.key)"
      >
        {{ s.label }}
      </button>
    </div>

    <!-- Контейнер Ганта -->
    <div ref="ganttContainer" style="width:100%; height:500px;"></div>

    <!-- Ошибка загрузки библиотеки -->
    <div v-if="loadError" style="padding:40px; text-align:center; color:var(--muted);">
      Библиотека dhtmlxGantt не загружена.
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import {
  updateGGStage,
  updateGGMilestone,
} from '../../../api/enterprise.js'

const props = defineProps({
  schedule: { type: Object, default: null },
  isWriter: { type: Boolean, default: false },
  /** true когда вкладка Ганта активна (для re-render при переключении) */
  active:   { type: Boolean, default: false },
})

const emit = defineEmits(['edit-stage'])

// ── Константы масштабов ─────────────────────────────────────────────────
const scales = [
  { key: 'day', label: 'День' },
  { key: 'week', label: 'Неделя' },
  { key: 'month', label: 'Месяц' },
  { key: 'quarter', label: 'Квартал' },
  { key: 'year', label: 'Год' },
]

// ── Состояние ───────────────────────────────────────────────────────────
const ganttContainer = ref(null)
const scalesEl = ref(null)
const loadError = ref(false)
const currentScale = ref(localStorage.getItem('gg_gantt_scale') || 'year')

let ganttLoaded = false  // библиотека загружена
let ganttInited = false  // gantt.init() вызван

// ── Ключи localStorage для ширин колонок ────────────────────────────────
const COL_KEY = 'gg_gantt_col_widths'
const COL_DEFAULTS = { text: 200, start_date: 70, end_date: 70, grid: 340 }

// ── Lazy-load dhtmlxGantt ───────────────────────────────────────────────

/**
 * Загружает CSS + JS библиотеки dhtmlxGantt динамически.
 * Повторяет логику ganttLoad() из gantt_common.js.
 */
function loadGanttLib() {
  return new Promise((resolve, reject) => {
    if (typeof window.gantt !== 'undefined') {
      resolve()
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
    script.onload = resolve
    script.onerror = () => reject(new Error('dhtmlxGantt not loaded'))
    document.head.appendChild(script)
  })
}

// ── Русская локаль (из gantt_common.js) ─────────────────────────────────

function applyLocaleRu() {
  const g = window.gantt
  if (!g) return
  g.locale = {
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

// ── Форматирование даты → "YYYY-MM-DD" ─────────────────────────────────

function formatDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

// ── Загрузка/сохранение ширин колонок ───────────────────────────────────

function loadColWidths() {
  try {
    const saved = JSON.parse(localStorage.getItem(COL_KEY))
    if (saved) return { ...COL_DEFAULTS, ...saved }
  } catch (e) { /* ignore */ }
  return { ...COL_DEFAULTS }
}

function saveColWidths() {
  const g = window.gantt
  if (!g) return
  const data = { grid: g.config.grid_width }
  g.config.columns.forEach(c => { data[c.name] = c.width })
  localStorage.setItem(COL_KEY, JSON.stringify(data))
}

// ── Настройка Ганта (один раз) ──────────────────────────────────────────

function setupGantt() {
  const g = window.gantt
  if (!g || ganttInited) return
  ganttInited = true

  // Базовые настройки (из ganttSetupBase)
  applyLocaleRu()
  g.config.date_format = '%Y-%m-%d'
  g.config.smart_rendering = false
  g.config.fit_tasks = true
  g.config.open_tree_initially = true
  g.config.tooltip_offset_x = 10
  g.config.tooltip_offset_y = 20
  g.templates.tooltip_text = function(start, end, task) {
    return '<b>' + task.text + '</b><br/>' +
      g.templates.tooltip_date_format(start) + ' \u2014 ' +
      g.templates.tooltip_date_format(end)
  }

  // Колонки с восстановлением ширин
  const savedCols = loadColWidths()
  g.config.grid_width = savedCols.grid
  g.config.columns = [
    { name: 'text', label: 'Название', width: savedCols.text, tree: true, resize: true },
    { name: 'start_date', label: 'Начало', align: 'center', width: savedCols.start_date, resize: true },
    { name: 'end_date', label: 'Окончание', align: 'center', width: savedCols.end_date, resize: true },
  ]

  // Интерактивный режим для writers
  g.config.readonly = !props.isWriter
  g.config.drag_move = props.isWriter
  g.config.drag_resize = props.isWriter
  g.config.drag_progress = false
  g.config.drag_links = false
  g.config.show_links = true

  // Восстанавливаем масштаб до init
  applyScaleConfig(currentScale.value)

  g.init(ganttContainer.value)

  // Drag -> сохранение дат на сервере
  g.attachEvent('onAfterTaskDrag', function(id) {
    const task = g.getTask(id)
    if (!task || !task.server_id) return
    const startStr = formatDate(task.start_date)
    const endStr = formatDate(task.end_date)
    const isMilestone = task.type === g.config.types.milestone

    if (isMilestone) {
      updateGGMilestone(task.server_id, { date: startStr }).catch(e => {
        alert(e.error || 'Ошибка сохранения')
        renderData()
      })
    } else {
      updateGGStage(task.server_id, { date_start: startStr, date_end: endStr }).catch(e => {
        alert(e.error || 'Ошибка сохранения')
        renderData()
      })
    }
  })

  // Двойной клик → модалка редактирования пункта
  g.attachEvent('onBeforeLightbox', function(id) {
    const task = g.getTask(id)
    if (task && task.server_id && task.type !== g.config.types.milestone) {
      emit('edit-stage', task.server_id)
    }
    return false // отменяем стандартный lightbox
  })
}

// ── Применение конфигурации масштаба (без render) ───────────────────────

function applyScaleConfig(scale) {
  const g = window.gantt
  if (!g) return

  switch (scale) {
    case 'day':
      g.config.scales = [
        { unit: 'month', step: 1, format: '%M %Y' },
        { unit: 'day', step: 1, format: '%d' },
      ]
      g.config.min_column_width = 28
      break
    case 'week':
      g.config.scales = [
        { unit: 'month', step: 1, format: '%M %Y' },
        { unit: 'week', step: 1, format: '%d' },
      ]
      g.config.min_column_width = 60
      break
    case 'month':
      g.config.scales = [
        { unit: 'year', step: 1, format: '%Y' },
        { unit: 'month', step: 1, format: '%M' },
      ]
      g.config.min_column_width = 50
      break
    case 'quarter':
      g.config.scales = [
        { unit: 'year', step: 1, format: '%Y' },
        { unit: 'quarter', step: 1, format: function(date) {
          const q = Math.floor(date.getMonth() / 3) + 1
          return 'Q' + q
        }},
      ]
      g.config.min_column_width = 70
      break
    default: // year
      g.config.scales = [
        { unit: 'year', step: 1, format: '%Y' },
      ]
      g.config.min_column_width = 80
  }
}

// ── Переключение масштаба ───────────────────────────────────────────────

function setScale(scale) {
  currentScale.value = scale
  localStorage.setItem('gg_gantt_scale', scale)
  applyScaleConfig(scale)
  if (window.gantt) window.gantt.render()
}

// ── Авто-высота строк (из gantt_common.js) ──────────────────────────────

function autoFitRowHeights() {
  const g = window.gantt
  if (!g) return
  const skipCols = new Set(['add', 'start_date', 'end_date', 'duration'])
  const cols = g.config.columns.filter(c => !skipCols.has(c.name))
  const measure = document.createElement('div')
  measure.style.cssText = 'position:absolute;visibility:hidden;white-space:normal;word-break:break-word;' +
    'line-height:1.4;font:inherit;padding:4px 0;box-sizing:border-box;'
  document.body.appendChild(measure)

  g.eachTask(task => {
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

// ── Отрисовка данных ────────────────────────────────────────────────────

function renderData() {
  const g = window.gantt
  if (!g || !props.schedule) return

  const tasks = []
  const links = []
  const stagesList = props.schedule.stages || []
  const milestonesList = props.schedule.milestones || []
  const deps = props.schedule.dependencies || []

  // Пункты (stages) -> задачи Ганта
  stagesList.forEach(s => {
    if (!s.date_start || !s.date_end) return
    const isParent = stagesList.some(c => c.parent_stage_id === s.id)
    tasks.push({
      id: 'stage_' + s.id,
      server_id: s.id,
      text: s.name,
      start_date: s.date_start,
      end_date: s.date_end,
      parent: s.parent_stage_id ? 'stage_' + s.parent_stage_id : 0,
      type: isParent ? g.config.types.project : g.config.types.task,
      open: true,
    })
  })

  // Вехи -> milestone-тип
  milestonesList.forEach(m => {
    if (!m.date) return
    tasks.push({
      id: 'ms_' + m.id,
      server_id: m.id,
      text: m.name,
      start_date: m.date,
      duration: 0,
      parent: m.stage_id ? 'stage_' + m.stage_id : 0,
      type: g.config.types.milestone,
    })
  })

  // Зависимости -> links
  const depTypeMap = { FS: '0', SS: '1', FF: '2', SF: '3' }
  deps.forEach(d => {
    links.push({
      id: 'dep_' + d.id,
      source: 'stage_' + d.predecessor_id,
      target: 'stage_' + d.successor_id,
      type: depTypeMap[d.dep_type] || '0',
      lag: d.lag_days || 0,
    })
  })

  g.clearAll()
  g.parse({ data: tasks, links: links })

  // Авто-высота строк + масштаб
  autoFitRowHeights()
  setScale(currentScale.value)
}

// ── Инициализация при монтировании ──────────────────────────────────────

async function initGantt() {
  try {
    await loadGanttLib()
    ganttLoaded = true
    setupGantt()
    renderData()
  } catch (e) {
    console.error('GGGanttView: ошибка загрузки gantt', e)
    loadError.value = true
  }
}

// При переключении на Гант-вид загружаем библиотеку (lazy) или рендерим
watch(() => props.active, (isActive) => {
  if (!isActive) return
  if (!ganttLoaded) {
    initGantt()
  } else {
    nextTick(() => renderData())
  }
})

// При изменении данных расписания — перерисовываем (если Гант активен)
watch(() => props.schedule, () => {
  if (props.active && ganttLoaded) {
    nextTick(() => renderData())
  }
}, { deep: true })

onMounted(() => {
  // Если вид уже активен при монтировании — загружаем сразу
  if (props.active) {
    initGantt()
  }
})

onBeforeUnmount(() => {
  // Очищаем gantt при размонтировании
  if (window.gantt && ganttInited) {
    try { window.gantt.clearAll() } catch (e) { /* ignore */ }
  }
})
</script>
