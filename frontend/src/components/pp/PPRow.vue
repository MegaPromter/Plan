<template>
  <!--
    Строка ПП-таблицы с инлайн-редактированием.
    Каждая ячейка может быть: readonly-текст, <input>, <select>, date.
    При изменении — вызывается handleCellChange → API PUT → подсветка.
    Каскадные дропдауны: dept → sector_head → executor.
  -->
  <tr
    :data-id="row.id"
    :class="rowStatusClass"
  >
    <!-- № (порядковый номер) -->
    <td data-col-idx="0">
      <!-- Чекбокс в режиме массового выделения -->
      <label v-if="bulkMode" style="display:flex;align-items:center;gap:4px;cursor:pointer;">
        <input
          type="checkbox"
          :checked="isSelected"
          @change="$emit('toggle-select', row.id)"
        >
        <span>{{ index + 1 }}</span>
      </label>
      <span v-else>{{ index + 1 }}</span>
    </td>

    <!-- row_code: всегда read-only (из ЕТБД) -->
    <td :data-col-idx="CI.row_code" :data-label="CL.row_code" style="font-size:12px;padding:4px 6px;">
      {{ row.row_code || '' }}
    </td>

    <!-- work_order: всегда read-only (из ЕТБД) -->
    <td :data-col-idx="CI.work_order" :data-label="CL.work_order" style="font-size:12px;padding:4px 6px;">
      {{ row.work_order || '' }}
    </td>

    <!-- stage_num → дропдаун PPStage (или read-only) -->
    <td :data-col-idx="CI.stage_num" :data-label="CL.stage_num">
      <select
        v-if="editable"
        class="cell-edit"
        :value="row.pp_stage_id || ''"
        @change="onPPStageChange($event.target.value)"
        :ref="el => cellRefs['pp_stage'] = el"
      >
        <option value="">--</option>
        <option
          v-for="s in ppStages"
          :key="s.id"
          :value="String(s.id)"
        >{{ s.stage_number ? s.stage_number + '. ' + s.name : s.name }}</option>
      </select>
      <span v-else style="font-size:12px;">{{ row.pp_stage_name || row.stage_num || '' }}</span>
    </td>

    <!-- milestone_num -->
    <td :data-col-idx="CI.milestone_num" :data-label="CL.milestone_num">
      <input
        v-if="editable"
        class="cell-edit cell-num"
        :value="row.milestone_num || ''"
        @change="onFieldChange('milestone_num', $event.target.value, $event.target)"
        @keydown="onKeydown($event, 'milestone_num')"
        :ref="el => cellRefs['milestone_num'] = el"
      >
      <span v-else style="font-size:12px;">{{ row.milestone_num || '' }}</span>
    </td>

    <!-- work_num -->
    <td :data-col-idx="CI.work_num" :data-label="CL.work_num">
      <input
        v-if="editable"
        class="cell-edit cell-num"
        :value="row.work_num || ''"
        @change="onFieldChange('work_num', $event.target.value, $event.target)"
        @keydown="onKeydown($event, 'work_num')"
        :ref="el => cellRefs['work_num'] = el"
      >
      <span v-else style="font-size:12px;">{{ row.work_num || '' }}</span>
    </td>

    <!-- work_designation -->
    <td :data-col-idx="CI.work_designation" :data-label="CL.work_designation">
      <input
        v-if="editable"
        class="cell-edit"
        :value="row.work_designation || ''"
        @change="onFieldChange('work_designation', $event.target.value, $event.target)"
        @keydown="onKeydown($event, 'work_designation')"
        :ref="el => cellRefs['work_designation'] = el"
      >
      <span v-else style="font-size:12px;">{{ row.work_designation || '' }}</span>
    </td>

    <!-- work_name -->
    <td :data-col-idx="CI.work_name" :data-label="CL.work_name">
      <input
        v-if="editable"
        class="cell-edit"
        :value="row.work_name || ''"
        @change="onFieldChange('work_name', $event.target.value, $event.target)"
        @keydown="onKeydown($event, 'work_name')"
        :ref="el => cellRefs['work_name'] = el"
      >
      <span v-else style="font-size:12px;">{{ row.work_name || '' }}</span>
    </td>

    <!-- date_start -->
    <td :data-col-idx="CI.date_start" :data-label="CL.date_start">
      <input
        v-if="editable"
        type="date"
        class="cell-edit"
        :value="row.date_start || ''"
        @change="onFieldChange('date_start', $event.target.value, $event.target)"
        :ref="el => cellRefs['date_start'] = el"
      >
      <span v-else style="font-size:12px;">{{ row.date_start || '' }}</span>
    </td>

    <!-- date_end -->
    <td :data-col-idx="CI.date_end" :data-label="CL.date_end">
      <input
        v-if="editable"
        type="date"
        class="cell-edit"
        :value="row.date_end || ''"
        @change="onFieldChange('date_end', $event.target.value, $event.target)"
        :ref="el => cellRefs['date_end'] = el"
      >
      <span v-else style="font-size:12px;">{{ row.date_end || '' }}</span>
    </td>

    <!-- sheets_a4 -->
    <td :data-col-idx="CI.sheets_a4" :data-label="CL.sheets_a4">
      <input
        v-if="editable"
        class="cell-edit cell-num"
        :value="row.sheets_a4 || ''"
        @change="onLaborFieldChange('sheets_a4', $event.target.value, $event.target)"
        @keydown="onKeydown($event, 'sheets_a4')"
        :ref="el => cellRefs['sheets_a4'] = el"
      >
      <span v-else style="font-size:12px;">{{ row.sheets_a4 || '' }}</span>
    </td>

    <!-- norm -->
    <td :data-col-idx="CI.norm" :data-label="CL.norm">
      <input
        v-if="editable"
        class="cell-edit cell-num"
        :value="row.norm || ''"
        @change="onLaborFieldChange('norm', $event.target.value, $event.target)"
        @keydown="onKeydown($event, 'norm')"
        :ref="el => cellRefs['norm'] = el"
      >
      <span v-else style="font-size:12px;">{{ row.norm || '' }}</span>
    </td>

    <!-- coeff -->
    <td :data-col-idx="CI.coeff" :data-label="CL.coeff">
      <input
        v-if="editable"
        class="cell-edit cell-num"
        :value="row.coeff || ''"
        @change="onLaborFieldChange('coeff', $event.target.value, $event.target)"
        @keydown="onKeydown($event, 'coeff')"
        :ref="el => cellRefs['coeff'] = el"
      >
      <span v-else style="font-size:12px;">{{ row.coeff || '' }}</span>
    </td>

    <!-- labor: вычисляемое, read-only при editable (показывает результат) -->
    <td :data-col-idx="CI.labor" :data-label="CL.labor">
      <span style="font-size:12px;">{{ row.labor || '' }}</span>
    </td>

    <!-- center: дропдаун НТЦ -->
    <td :data-col-idx="CI.center" :data-label="CL.center">
      <select
        v-if="editable"
        class="cell-edit"
        :value="row.center || ''"
        @change="onFieldChange('center', $event.target.value, $event.target)"
        :ref="el => cellRefs['center'] = el"
      >
        <option value="">--</option>
        <option
          v-for="d in (dirs.center || [])"
          :key="d.value"
          :value="d.value"
        >{{ d.value }}</option>
      </select>
      <span v-else style="font-size:12px;">{{ row.center || '' }}</span>
    </td>

    <!-- dept: дропдаун отделов (каскадно → sector_head, executor) -->
    <td :data-col-idx="CI.dept" :data-label="CL.dept">
      <select
        v-if="editable"
        class="cell-edit"
        :value="row.dept || ''"
        @change="onDeptChange($event.target.value, $event.target)"
        :ref="el => cellRefs['dept'] = el"
      >
        <option value="">--</option>
        <option
          v-for="d in (dirs.dept || [])"
          :key="d.value"
          :value="d.value"
        >{{ d.value }}</option>
      </select>
      <span v-else style="font-size:12px;">{{ row.dept || '' }}</span>
    </td>

    <!-- sector_head: дропдаун секторов (каскадно → executor) -->
    <td :data-col-idx="CI.sector_head" :data-label="CL.sector_head" style="font-size:12px;padding:4px 6px;">
      <template v-if="editable">
        <select
          class="cell-edit"
          :value="row.sector_head || ''"
          @change="onSectorChange($event.target.value, $event.target)"
          :ref="el => cellRefs['sector_head'] = el"
        >
          <option value="">--</option>
          <!-- Фантомная опция для текущего значения, если оно не в списке -->
          <option
            v-if="row.sector_head && !sectorInList(row.sector_head)"
            :value="row.sector_head"
            selected
          >{{ row.sector_head }}</option>
          <option
            v-for="h in filteredSectors"
            :key="h.value"
            :value="h.value"
            :disabled="isSectorDisabled(h)"
            :style="isSectorDisabled(h) ? { color: 'var(--muted)' } : {}"
          >{{ h.value }}</option>
        </select>
        <!-- ФИО начальника сектора (серый текст под дропдауном) -->
        <div
          v-if="sectorHeadName"
          style="font-size:11px;color:var(--muted);margin-top:2px;padding:0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
        >{{ sectorHeadName }}</div>
      </template>
      <template v-else>
        <span>{{ row.sector_head || '' }}</span>
        <div
          v-if="sectorHeadName"
          style="font-size:11px;color:var(--muted);margin-top:2px;"
        >{{ sectorHeadName }}</div>
      </template>
    </td>

    <!-- executor: дропдаун исполнителей (фильтрован по dept/sector) -->
    <td :data-col-idx="CI.executor" :data-label="CL.executor">
      <select
        v-if="editable"
        class="cell-edit"
        :value="row.executor || ''"
        @change="onFieldChange('executor', $event.target.value, $event.target)"
        :ref="el => cellRefs['executor'] = el"
      >
        <option value="">--</option>
        <!-- Фантомная опция если текущий executor не в отфильтрованном списке -->
        <option
          v-if="row.executor && !executorInList(row.executor)"
          :value="row.executor"
          selected
        >{{ row.executor }}</option>
        <option
          v-for="e in filteredExecutors"
          :key="e.value"
          :value="e.value"
        >{{ e.value }}</option>
      </select>
      <span v-else style="font-size:12px;">{{ row.executor || '' }}</span>
    </td>

    <!-- task_type: дропдаун типа задачи или badge в read-only -->
    <td :data-col-idx="CI.task_type" :data-label="CL.task_type" style="padding:4px 6px;text-align:center;">
      <select
        v-if="editable"
        class="cell-edit"
        :value="row.task_type || defaultTaskType"
        @change="onFieldChange('task_type', $event.target.value, $event.target)"
        :ref="el => cellRefs['task_type'] = el"
      >
        <option
          v-for="d in (dirs.task_type || [])"
          :key="d.value"
          :value="d.value"
        >{{ d.value }}</option>
      </select>
      <span
        v-else-if="row.task_type"
        class="task-type-badge"
        :title="row.task_type"
      >{{ shortTaskType(row.task_type) }}</span>
    </td>

    <!-- Действия: зависимости + удаление -->
    <td data-col-idx="19" style="text-align:center;white-space:nowrap;">
      <!-- Значок зависимостей со счётчиком -->
      <span
        class="dep-badge action-dep"
        :class="{ zero: (row.predecessors_count || 0) === 0 }"
        style="cursor:pointer;margin-right:4px;"
        title="Зависимости"
        @click="$emit('open-deps', { taskId: row.id, taskName: row.work_name || '' })"
      >&#x1F517;</span>
      <!-- Кнопка удаления (только если редактируемо) -->
      <button
        v-if="editable"
        class="btn-delete"
        title="Удалить"
        @click="$emit('delete-row', row.id)"
      >
        <i class="fas fa-times"></i>
      </button>
    </td>
  </tr>
</template>

<script setup>
/**
 * PPRow — строка ПП-таблицы с инлайн-редактированием.
 *
 * Основная логика:
 * 1. Каждая ячейка — input/select/readonly на основе типа колонки и прав
 * 2. При change — вызывается emit('cell-change', rowId, field, value)
 * 3. Каскадные дропдауны: dept → sector_head → executor
 * 4. Авто-расчёт labor при изменении sheets_a4/norm/coeff
 * 5. Визуальная подсветка ячейки (saving/saved/error) управляется родителем
 * 6. Tab-навигация между ячейками (keydown)
 */
import { computed, inject, reactive } from 'vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'
import { PP_COL_IDX, PP_COL_LABELS } from '../../constants/pp.js'
import { getRowStatus } from '../../constants/pp.js'

const props = defineProps({
  row: { type: Object, required: true },
  index: { type: Number, required: true },
  bulkMode: { type: Boolean, default: false },
  isSelected: { type: Boolean, default: false },
})

const emit = defineEmits([
  'cell-change',
  'open-deps',
  'delete-row',
  'toggle-select',
])

const store = inject(PP_STORE_KEY)

// Короткие ссылки
const CI = PP_COL_IDX
const CL = PP_COL_LABELS
const dirs = computed(() => store.dirs.value)
const ppStages = computed(() => store.ppStages.value)

// Рефы на DOM-элементы ячеек (для Tab-навигации и подсветки)
const cellRefs = reactive({})

// ── Права на редактирование ────────────────────────────────────────────
const editable = computed(() =>
  store.isWriter && store.canModifyRow(props.row.dept, props.row.sector_head)
)

// ── CSS-класс строки по статусу ────────────────────────────────────────
const rowStatusClass = computed(() => {
  const st = getRowStatus(props.row)
  if (st === 'done') return 'row-done'
  if (st === 'overdue') return 'row-overdue'
  return 'row-inwork'
})

// ── Каскадные фильтрации ──────────────────────────────────────────────

/** Секторы, отфильтрованные по выбранному отделу строки */
const filteredSectors = computed(() => {
  const allHeads = dirs.value.sector_head || []
  const deptVal = props.row.dept || ''
  if (!deptVal) return allHeads
  const deptEntry = (dirs.value.dept || []).find(d => d.value === deptVal)
  return deptEntry ? allHeads.filter(h => h.parent_id === deptEntry.id) : allHeads
})

/** Проверяем что текущий сектор есть в отфильтрованном списке */
function sectorInList(val) {
  return filteredSectors.value.some(h => h.value === val)
}

/** Нач. сектора чужого сектора — disabled для sector_head */
function isSectorDisabled(h) {
  if (store.isAdmin || store.userRole === 'dept_head' || store.userRole === 'dept_deputy') return false
  if (!store.userSector) return false
  return h.value !== store.userSector
}

/** ФИО начальника сектора (серый текст под select'ом) */
const sectorHeadName = computed(() => {
  const val = props.row.sector_head
  if (!val) return ''
  const sh = (dirs.value.sector_head || []).find(h => h.value === val)
  return sh ? (sh.head_name || '') : ''
})

/** Исполнители, отфильтрованные по сектору (если задан) или отделу */
const filteredExecutors = computed(() => {
  const allEmps = dirs.value.employees || []
  const sectorFilter = props.row.sector_head || ''
  const deptFilter = props.row.dept || ''
  if (sectorFilter) return allEmps.filter(e => e.sector === sectorFilter)
  if (deptFilter) return allEmps.filter(e => e.dept === deptFilter)
  return allEmps
})

/** Проверяем что текущий executor есть в отфильтрованном списке */
function executorInList(val) {
  return filteredExecutors.value.some(e => e.value === val)
}

/** Дефолтный тип задачи */
const defaultTaskType = computed(() => {
  const types = dirs.value.task_type || []
  return types.length ? types[0].value : 'Выпуск нового документа'
})

/** Сокращённое отображение типа задачи (для badge) */
function shortTaskType(val) {
  if (!val) return ''
  // Первые 20 символов + многоточие
  return val.length > 20 ? val.slice(0, 20) + '...' : val
}

// ── Обработчики изменений ────────────────────────────────────────────

/**
 * Общий обработчик изменения поля.
 * Защита от повторного PUT (если значение не изменилось).
 */
function onFieldChange(field, value, inputEl) {
  // Защита от повторного PUT
  if (inputEl && inputEl._ppLastSaved === value) return
  if (inputEl) inputEl._ppLastSaved = value
  emit('cell-change', props.row.id, field, value)
}

/**
 * При смене отдела: отправить PUT + сбросить sector_head и executor.
 * Родитель (PPTable) обновляет row.dept, row.sector_head, row.executor.
 */
function onDeptChange(value, inputEl) {
  if (inputEl) inputEl._ppLastSaved = value
  emit('cell-change', props.row.id, 'dept', value)
}

/**
 * При смене сектора: отправить PUT + обновить ФИО под select.
 * Родитель обновляет row.sector_head.
 */
function onSectorChange(value, inputEl) {
  if (inputEl) inputEl._ppLastSaved = value
  emit('cell-change', props.row.id, 'sector_head', value)
}

/**
 * При смене PPStage: отправить PUT с pp_stage,
 * родитель обновит row.pp_stage_id / pp_stage_name / row_code / work_order.
 */
function onPPStageChange(value) {
  emit('cell-change', props.row.id, 'pp_stage', value)
}

/**
 * Изменение поля расчёта трудоёмкости (sheets_a4 / norm / coeff).
 * Отправляем PUT поля + затем PUT labor (авто-расчёт).
 */
function onLaborFieldChange(field, value, inputEl) {
  if (inputEl && inputEl._ppLastSaved === value) return
  if (inputEl) inputEl._ppLastSaved = value
  // Эмитим изменение поля — родитель выполнит PUT и авто-расчёт labor
  emit('cell-change', props.row.id, field, value)
}

// ── Tab-навигация между ячейками ──────────────────────────────────────
function onKeydown(e, field) {
  if (e.key === 'Tab') {
    e.preventDefault()
    // Эмитим change перед переходом
    onFieldChange(field, e.target.value, e.target)
    moveFocus(e.target, !e.shiftKey)
  }
}

/** Перемещение фокуса к следующей/предыдущей .cell-edit ячейке */
function moveFocus(current, forward) {
  const td = current.closest('td')
  if (!td) return
  let nextTd = forward ? td.nextElementSibling : td.previousElementSibling
  while (nextTd) {
    const el = nextTd.querySelector('.cell-edit')
    if (el) { el.focus(); if (el.tagName !== 'SELECT') el.select(); return }
    nextTd = forward ? nextTd.nextElementSibling : nextTd.previousElementSibling
  }
  // Переход в соседнюю строку
  const tr = td.closest('tr')
  const nextTr = forward ? tr.nextElementSibling : tr.previousElementSibling
  if (!nextTr) return
  const cells = nextTr.querySelectorAll('.cell-edit')
  if (cells.length) {
    const target = forward ? cells[0] : cells[cells.length - 1]
    target.focus()
    if (target.tagName !== 'SELECT') target.select()
  }
}
</script>
