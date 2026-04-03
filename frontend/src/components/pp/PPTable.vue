<template>
  <!--
    PPTable — главная таблица производственного плана.
    Включает:
    - 3-строчный заголовок (основные столбцы, подстолбцы, фильтры)
    - Ленивую chunk-отрисовку строк (useLazyScroll)
    - Инлайн-редактирование через PPRow
    - Инлайн-добавление через PPAddRow
    - Строку пустого состояния
    - Счётчик строк в подвале
  -->
  <div ref="tableWrap" class="pp-table-wrap" :class="'pp-view-' + store.columnViewMode.value">
    <table class="pp-table" id="ppTable">
      <thead>
        <!-- ═══ Первая строка заголовков (основные столбцы, часть с rowspan=2) ═══ -->
        <tr>
          <th style="width:40px;" rowspan="2" data-col-idx="0">&#8470;</th>
          <th style="width:100px;" rowspan="2" data-col-idx="1"
              class="sortable" @click="onSort('row_code')">
            Код строки <SortIcon :state="sort.state" col="row_code" />
          </th>
          <th style="width:110px;" rowspan="2" data-col-idx="2"
              class="sortable" @click="onSort('work_order')">
            Наряд-заказ <SortIcon :state="sort.state" col="work_order" />
          </th>
          <th style="width:90px;" rowspan="2" data-col-idx="3"
              class="sortable" @click="onSort('stage_num')">
            &#8470; этапа <SortIcon :state="sort.state" col="stage_num" />
          </th>
          <th style="width:100px;" rowspan="2" data-col-idx="4"
              class="sortable" @click="onSort('milestone_num')">
            &#8470; вехи <SortIcon :state="sort.state" col="milestone_num" />
          </th>
          <th style="width:90px;" rowspan="2" data-col-idx="5"
              class="sortable" @click="onSort('work_num')">
            &#8470; работы <SortIcon :state="sort.state" col="work_num" />
          </th>
          <!-- Группа «Группа» (colspan=2) -->
          <th colspan="2" style="text-align:center;">Группа</th>
          <!-- Группа «Сроки» (colspan=2) -->
          <th colspan="2" style="text-align:center;">Сроки</th>
          <!-- Группа «Расчёт трудозатрат» (colspan=4) -->
          <th style="width:500px;" colspan="4" data-col-group="labor">Расчёт трудозатрат</th>
          <th style="width:100px;" rowspan="2" data-col-idx="14"
              class="sortable" @click="onSort('ntc_center')">
            Подразделение <SortIcon :state="sort.state" col="ntc_center" />
          </th>
          <th style="width:60px;" rowspan="2" data-col-idx="15"
              class="sortable" @click="onSort('department')">
            Отдел <SortIcon :state="sort.state" col="department" />
          </th>
          <th style="width:130px;" rowspan="2" data-col-idx="16"
              class="sortable" @click="onSort('sector')">
            Сектор /<br>Нач. сектора <SortIcon :state="sort.state" col="sector" />
          </th>
          <th style="width:140px;" rowspan="2" data-col-idx="17"
              class="sortable" @click="onSort('executor')">
            Разработчик <SortIcon :state="sort.state" col="executor" />
          </th>
          <th style="width:120px;" rowspan="2" data-col-idx="18"
              class="sortable" @click="onSort('task_type')">
            Тип задачи <SortIcon :state="sort.state" col="task_type" />
          </th>
          <th style="width:70px;" rowspan="2" data-col-idx="19">Действия</th>
        </tr>

        <!-- ═══ Вторая строка заголовков: подстолбцы ═══ -->
        <tr>
          <th style="width:300px;" data-col-idx="6"
              class="sortable" @click="onSort('work_designation')">
            Обозначение <SortIcon :state="sort.state" col="work_designation" />
          </th>
          <th style="width:350px;" data-col-idx="7"
              class="sortable" @click="onSort('work_name')">
            Наименование <SortIcon :state="sort.state" col="work_name" />
          </th>
          <th style="width:110px;" data-col-idx="8"
              class="sortable" @click="onSort('date_start')">
            Начало <SortIcon :state="sort.state" col="date_start" />
          </th>
          <th style="width:110px;" data-col-idx="9"
              class="sortable" @click="onSort('date_end')">
            Окончание <SortIcon :state="sort.state" col="date_end" />
          </th>
          <th style="width:100px;" data-col-idx="10">Ф, А4</th>
          <th style="width:100px;" data-col-idx="11">Норматив</th>
          <th style="width:100px;" data-col-idx="12">Коэфф</th>
          <th style="width:130px;" data-col-idx="13">Плановая<br>трудоёмкость</th>
        </tr>

        <!-- ═══ Третья строка: мультифильтры ═══ -->
        <tr class="filter-row">
          <!-- № — без фильтра -->
          <th data-col-idx="0"></th>
          <!-- Мультифильтры для каждой фильтруемой колонки -->
          <th data-col-idx="1">
            <FilterDropdown col="row_code" :values="mfValues('row_code')"
              :active="isFilterActive('row_code')" @apply="onFilter('row_code', $event)" />
          </th>
          <th data-col-idx="2">
            <FilterDropdown col="work_order" :values="mfValues('work_order')"
              :active="isFilterActive('work_order')" @apply="onFilter('work_order', $event)" />
          </th>
          <th data-col-idx="3">
            <FilterDropdown col="stage_num" :values="mfValues('stage_num')"
              :active="isFilterActive('stage_num')" @apply="onFilter('stage_num', $event)" />
          </th>
          <th data-col-idx="4">
            <FilterDropdown col="milestone_num" :values="mfValues('milestone_num')"
              :active="isFilterActive('milestone_num')" @apply="onFilter('milestone_num', $event)" />
          </th>
          <th data-col-idx="5">
            <FilterDropdown col="work_num" :values="mfValues('work_num')"
              :active="isFilterActive('work_num')" @apply="onFilter('work_num', $event)" />
          </th>
          <th data-col-idx="6">
            <FilterDropdown col="work_designation" :values="mfValues('work_designation')"
              :active="isFilterActive('work_designation')" @apply="onFilter('work_designation', $event)" />
          </th>
          <th data-col-idx="7">
            <FilterDropdown col="work_name" :values="mfValues('work_name')"
              :active="isFilterActive('work_name')" @apply="onFilter('work_name', $event)" />
          </th>
          <th data-col-idx="8">
            <FilterDropdown col="date_start" :values="mfDateValues('date_start')"
              :active="isFilterActive('date_start')" @apply="onFilter('date_start', $event)" />
          </th>
          <th data-col-idx="9">
            <FilterDropdown col="date_end" :values="mfDateValues('date_end')"
              :active="isFilterActive('date_end')" @apply="onFilter('date_end', $event)" />
          </th>
          <!-- Столбцы расчёта: без фильтров -->
          <th data-col-idx="10"></th>
          <th data-col-idx="11"></th>
          <th data-col-idx="12"></th>
          <th data-col-idx="13"></th>
          <!-- Подразделение, отдел, сектор, разработчик, тип задачи -->
          <th data-col-idx="14">
            <FilterDropdown col="center" :values="mfValues('center')"
              :active="isFilterActive('center')" @apply="onFilter('center', $event)" />
          </th>
          <th data-col-idx="15">
            <FilterDropdown col="dept" :values="mfValues('dept')"
              :active="isFilterActive('dept')" @apply="onFilter('dept', $event)" />
          </th>
          <th data-col-idx="16">
            <FilterDropdown col="sector_head" :values="mfValues('sector_head')"
              :active="isFilterActive('sector_head')" @apply="onFilter('sector_head', $event)" />
          </th>
          <th data-col-idx="17">
            <FilterDropdown col="executor" :values="mfValues('executor')"
              :active="isFilterActive('executor')" @apply="onFilter('executor', $event)" />
          </th>
          <th data-col-idx="18">
            <FilterDropdown col="task_type" :values="mfValues('task_type')"
              :active="isFilterActive('task_type')" @apply="onFilter('task_type', $event)" />
          </th>
          <!-- Действия — без фильтра -->
          <th data-col-idx="19"></th>
        </tr>
      </thead>

      <tbody>
        <!-- Строка добавления (если активна) -->
        <PPAddRow
          v-if="addingRow"
          @saved="onRowSaved"
          @cancel="addingRow = false"
        />

        <!-- Пустое состояние -->
        <tr v-if="renderedItems.length === 0 && !addingRow">
          <td colspan="20" style="text-align:center;padding:40px;">
            <div class="empty-state">
              <i class="fas fa-inbox empty-state-icon"></i>
              <div class="empty-state-title">Нет записей</div>
              <div class="empty-state-desc">
                Попробуйте изменить фильтры или добавьте новую строку
              </div>
              <button
                v-if="store.isWriter"
                class="btn btn-primary btn-sm"
                @click="addingRow = true"
              >
                <i class="fas fa-plus"></i> Добавить строку
              </button>
            </div>
          </td>
        </tr>

        <!-- Строки таблицы (lazy-rendered) -->
        <PPRow
          v-for="(row, idx) in renderedItems"
          :key="row.id"
          :row="row"
          :index="getGlobalIndex(row)"
          :bulk-mode="store.bulkMode.value"
          :is-selected="store.bulkSelected.has(row.id)"
          @cell-change="handleCellChange"
          @open-deps="$emit('open-deps', $event)"
          @delete-row="$emit('delete-row', $event)"
          @toggle-select="toggleBulkSelect"
        />

        <!-- Спиннер подгрузки -->
        <tr v-if="renderedItems.length > 0 && !allLoaded">
          <td colspan="20" class="scroll-spinner">
            <i class="fas fa-spinner"></i>
            Загружено {{ renderedItems.length }} из {{ filteredRows.length }}...
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
/**
 * PPTable — таблица производственного плана.
 *
 * Получает все строки из store.rows, применяет фильтрацию (colFilters +
 * statusFilter + period + dept), сортировку, и лениво отрисовывает
 * через useLazyScroll.
 *
 * Инлайн-редактирование: PPRow эмитит cell-change → handleCellChange
 * делает PUT API → подсвечивает ячейку зелёным/красным → обновляет store.rows.
 */
import { ref, computed, inject, watch, nextTick, onMounted } from 'vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'
import { getRowStatus, PP_COL_IDX, PP_VIEW_HIDDEN, formatYearMonth } from '../../constants/pp.js'
import { updatePPField } from '../../api/pp.js'
import { useSort } from '../../composables/useSort.js'
import { useLazyScroll } from '../../composables/useLazyScroll.js'
import FilterDropdown from '../FilterDropdown.vue'
import SortIcon from '../SortIcon.vue'
import PPRow from './PPRow.vue'
import PPAddRow from './PPAddRow.vue'

const store = inject(PP_STORE_KEY)

const emit = defineEmits(['open-deps', 'delete-row'])

// ── Состояние ────────────────────────────────────────────────────────────
const addingRow = ref(false)
const tableWrap = ref(null)

// ── Сортировка ──────────────────────────────────────────────────────────
const sort = useSort()

function onSort(col) {
  sort.toggle(col)
  // Синхронизируем с store (для статус-панели и др.)
  store.sortState.col = sort.state.col
  store.sortState.dir = sort.state.dir
}

// ── Фильтрация ──────────────────────────────────────────────────────────

/** Уникальные значения для мультифильтра обычного столбца */
function mfValues(col) {
  const vals = new Set()
  store.rows.value.forEach(row => {
    // Для stage_num — используем pp_stage_name
    const v = (col === 'stage_num')
      ? String(row.pp_stage_name || row[col] || '')
      : String(row[col] || '')
    if (v) vals.add(v)
  })
  return [...vals].sort((a, b) => a.localeCompare(b, 'ru'))
}

/** Уникальные значения для мультифильтра дат (по YYYY-MM) */
function mfDateValues(col) {
  const vals = new Set()
  store.rows.value.forEach(row => {
    const v = (row[col] || '').slice(0, 7)
    if (v) vals.add(v)
  })
  return [...vals].sort().map(ym => ym)
}

/** Проверяет, активен ли фильтр для столбца */
function isFilterActive(col) {
  const key = 'mf_' + col
  const f = store.colFilters[key]
  return !!(f && f.size > 0)
}

/** Применение мультифильтра: сохраняет Set в store.colFilters */
function onFilter(col, selectedSet) {
  const key = 'mf_' + col
  if (!selectedSet || selectedSet.size === 0) {
    delete store.colFilters[key]
  } else {
    store.colFilters[key] = selectedSet
  }
  store.mfSelections[col] = selectedSet || new Set()
}

// ── Вычисление отфильтрованных строк ────────────────────────────────────

/** Все строки после фильтрации (colFilters + statusFilter + period + dept) */
const filteredRows = computed(() => {
  let result = store.rows.value

  // 1. Фильтр по статусу (done/overdue/inwork)
  if (store.statusFilter.value !== 'all') {
    result = result.filter(r => getRowStatus(r) === store.statusFilter.value)
  }

  // 2. Колоночные фильтры (mf_*)
  const filters = store.colFilters
  if (Object.keys(filters).length > 0) {
    result = result.filter(row => {
      for (const [col, val] of Object.entries(filters)) {
        if (!col.startsWith('mf_')) continue
        const field = col.slice(3)
        if (!val || val.size === 0) continue
        if (field === 'date_end' || field === 'date_start') {
          const cellVal = (row[field] || '').slice(0, 7)
          if (!val.has(cellVal)) return false
        } else if (field === 'pp_stage' || field === 'stage_num') {
          if (!val.has(row.pp_stage_name || '')) return false
        } else {
          if (!val.has(row[field] || '')) return false
        }
      }
      return true
    })
  }

  // 3. Фильтр по периоду (год/месяц)
  if (store.selectedMonth.value) {
    const ym = store.selectedYear.value + '-' +
      String(store.selectedMonth.value).padStart(2, '0')
    result = result.filter(row => {
      const ds = (row.date_start || '').slice(0, 7)
      const de = (row.date_end || '').slice(0, 7)
      return ds <= ym && de >= ym
    })
  }

  // 4. Фильтр по выбранным отделам (чипы)
  if (store.selectedDepts.size > 0) {
    result = result.filter(row => store.selectedDepts.has(row.dept))
  }

  // 5. Сортировка
  if (sort.state.col) {
    result = sort.applySortToArray(result, (row, col) => {
      // Маппинг имён сортировки на поля данных
      const fieldMap = {
        ntc_center: 'center',
        department: 'dept',
        sector: 'sector_head',
      }
      const field = fieldMap[col] || col
      return row[field] || ''
    })
  }

  return result
})

// ── Ленивая отрисовка ───────────────────────────────────────────────────
const CHUNK_SIZE = 50

const {
  renderedItems,
  allRendered: allLoadedRef,
  appendNextChunk,
  reset: resetLazy,
  attachScroll,
} = useLazyScroll(tableWrap, filteredRows, CHUNK_SIZE)

// allLoadedRef теперь computed ref из useLazyScroll
const allLoaded = allLoadedRef

/** Получить глобальный индекс строки (в filteredRows) */
function getGlobalIndex(row) {
  return filteredRows.value.indexOf(row)
}

// useLazyScroll уже подписывается на containerRef — дополнительный watch не нужен

// ── Массовое выделение ──────────────────────────────────────────────────

function toggleBulkSelect(rowId) {
  if (store.bulkSelected.has(rowId)) {
    store.bulkSelected.delete(rowId)
  } else {
    store.bulkSelected.add(rowId)
  }
}

// ── Обработка сохранения новой строки ───────────────────────────────────
function onRowSaved(resp) {
  addingRow.value = false
  // Сбрасываем фильтры, чтобы новая строка была видна
  store.clearAllFilters()
  sort.state.col = null
  // Вставляем новую строку в начало
  if (resp && resp.work) {
    const existing = store.rows.value.findIndex(r => r.id === resp.work.id)
    if (existing >= 0) store.rows.value.splice(existing, 1)
    store.rows.value.unshift(resp.work)
  }
}

// ── Показать строку добавления ──────────────────────────────────────────
function showAddRow() {
  addingRow.value = true
}

// ── Инлайн-редактирование: обработка cell-change от PPRow ───────────────

/**
 * Главный обработчик изменения ячейки.
 * 1. Визуальная синяя подсветка (saving)
 * 2. PUT API
 * 3. Зелёная (успех) или красная (ошибка) подсветка
 * 4. Обновление данных в store.rows
 * 5. Каскадные обновления (dept→sector_head→executor)
 * 6. Авто-расчёт labor при sheets_a4/norm/coeff
 */
async function handleCellChange(rowId, field, value) {
  const rowIdx = store.rows.value.findIndex(r => String(r.id) === String(rowId))
  if (rowIdx < 0) return
  const rowObj = store.rows.value[rowIdx]

  // ── Каскадные обновления: при смене dept → сброс sector_head, executor ──
  if (field === 'dept') {
    rowObj.dept = value
    rowObj.sector_head = ''
    rowObj.executor = ''
  }

  // ── При смене sector_head → сброс executor ──
  if (field === 'sector_head') {
    rowObj.sector_head = value
    rowObj.executor = ''
  }

  // PUT /api/production_plan/<id>/?field=<field>
  try {
    const resp = await updatePPField(rowId, field, value)

    // Обновляем данные строки в store
    if (field === 'pp_stage') {
      rowObj.pp_stage_id = value || null
      const cs = store.ppStages.value.find(s => String(s.id) === String(value))
      rowObj.pp_stage_name = cs ? cs.name : ''
      rowObj.row_code = cs ? (cs.row_code || '') : ''
      rowObj.work_order = cs ? (cs.work_order || '') : ''
    } else if (field !== 'dept' && field !== 'sector_head') {
      // dept и sector_head уже обновлены выше (каскад)
      rowObj[field] = value
    }

    // ── Авто-расчёт трудоёмкости ────────────────────────────────────────
    if (['sheets_a4', 'norm', 'coeff'].includes(field)) {
      await autoCalcLabor(rowObj)
    }
  } catch (err) {
    console.error('PPTable: ошибка сохранения ячейки', err)
  }
}

/**
 * Автоматический пересчёт и сохранение трудоёмкости.
 * labor = sheets_a4 * norm * coeff (до 2 знаков).
 */
async function autoCalcLabor(rowObj) {
  const sheets = parseFloat(String(rowObj.sheets_a4 || '').replace(',', '.'))
  const norm = parseFloat(String(rowObj.norm || '').replace(',', '.'))
  const coeff = parseFloat(String(rowObj.coeff || '').replace(',', '.'))

  let laborVal = ''
  if (!isNaN(sheets) && !isNaN(norm) && !isNaN(coeff)) {
    laborVal = parseFloat((sheets * norm * coeff).toFixed(2))
  }

  // Сохраняем вычисленную трудоёмкость на сервере
  try {
    await updatePPField(rowObj.id, 'labor', laborVal)
    rowObj.labor = laborVal
  } catch (err) {
    console.error('PPTable: ошибка пересчёта трудоёмкости', err)
  }
}

// ── Пересчёт sticky top для строк thead ────────────────────────────────
function fixStickyTops() {
  const wrap = tableWrap.value
  if (!wrap) return
  // Используем глобальную функцию из utils.js если доступна
  if (typeof _fixStickyHeaderTops === 'function') {
    _fixStickyHeaderTops(wrap)
  } else {
    // Fallback: пересчитываем вручную
    const table = wrap.querySelector('table')
    if (!table) return
    const rows = table.querySelectorAll('thead tr')
    let cumTop = 0
    rows.forEach(row => {
      row.querySelectorAll('th').forEach(th => { th.style.top = cumTop + 'px' })
      cumTop += row.offsetHeight
    })
  }
}

onMounted(() => {
  nextTick(() => {
    fixStickyTops()
    // Повторный вызов через 200ms на случай позднего рендера шрифтов
    setTimeout(fixStickyTops, 200)
  })
})

// ── Подсветка столбцов при смене режима отображения ────────────────────
watch(store.columnViewMode, (newMode, oldMode) => {
  if (newMode === oldMode || !tableWrap.value) return
  // Пересчёт sticky top после смены видимости столбцов
  nextTick(() => { fixStickyTops() })

  const prevHidden = PP_VIEW_HIDDEN[oldMode] || []
  const newHidden  = PP_VIEW_HIDDEN[newMode] || []
  // Столбцы, которые были скрыты, а теперь видимы
  const appeared = prevHidden.filter(i => !newHidden.includes(i))
  if (!appeared.length) return

  nextTick(() => {
    const wrap = tableWrap.value
    if (!wrap) return
    const cells = []
    appeared.forEach(idx => {
      wrap.querySelectorAll(`[data-col-idx="${idx}"]`).forEach(el => cells.push(el))
    })
    // Группа «Расчёт трудозатрат» (colspan-заголовок)
    const laborGroup = wrap.querySelector('th[data-col-group="labor"]')
    if (laborGroup && prevHidden.includes(10) && !newHidden.includes(10)) {
      cells.push(laborGroup)
    }
    if (!cells.length) return
    // JS-fade: box-shadow inset контур 0.7 → 0 за ~1.5s
    let alpha = 0.7
    const steps = 30
    const step = alpha / steps
    const applyShadow = (a) => {
      const shadow = a > 0.01 ? `inset 0 0 0 2px rgba(37,99,235,${a.toFixed(3)})` : ''
      cells.forEach(el => { el.style.boxShadow = shadow })
    }
    applyShadow(alpha)
    const interval = setInterval(() => {
      alpha -= step
      if (alpha <= 0) {
        clearInterval(interval)
        cells.forEach(el => { el.style.boxShadow = '' })
        return
      }
      applyShadow(alpha)
    }, 50)
  })
})

// ── Экспорт для родительского компонента ────────────────────────────────
defineExpose({ showAddRow, filteredRows })
</script>
