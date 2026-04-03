<template>
  <!--
    Инлайн-строка для добавления новой записи в ПП-таблицу.
    Рендерится как <tr> в начале tbody с подсветкой.
    Поддерживает:
    - все типы ячеек (select / text / date / number)
    - авто-расчёт трудоёмкости (sheets_a4 * norm * coeff)
    - каскадные дропдауны (dept → sector_head → executor)
    - Enter/Escape для сохранения/отмены
    - заполнение row_code / work_order из PPStage при смене этапа
  -->
  <tr
    class="pp-add-row"
    :style="{
      background: 'rgba(59,130,246,0.07)',
      outline: '2px solid rgba(59,130,246,0.3)',
    }"
  >
    <!-- Порядковый номер: знак + -->
    <td data-col-idx="0" style="color:var(--accent);font-weight:600;">+</td>

    <!-- row_code: read-only, заполняется из PPStage -->
    <td :data-col-idx="colIdx.row_code" style="font-size:11px;color:var(--muted);padding:4px 6px;">
      {{ newRow.row_code || 'авто' }}
    </td>

    <!-- work_order: read-only, заполняется из PPStage -->
    <td :data-col-idx="colIdx.work_order" style="font-size:11px;color:var(--muted);padding:4px 6px;">
      {{ newRow.work_order || 'авто' }}
    </td>

    <!-- stage_num → дропдаун PPStage -->
    <td :data-col-idx="colIdx.stage_num">
      <select class="cell-edit" v-model="newRow.pp_stage_id" @change="onPPStageChange">
        <option value="">--</option>
        <option
          v-for="s in store.ppStages.value"
          :key="s.id"
          :value="String(s.id)"
        >{{ s.stage_number ? s.stage_number + '. ' + s.name : s.name }}</option>
      </select>
    </td>

    <!-- milestone_num -->
    <td :data-col-idx="colIdx.milestone_num">
      <input
        class="cell-edit cell-num"
        v-model="newRow.milestone_num"
        @keydown="onKeydown"
      >
    </td>

    <!-- work_num -->
    <td :data-col-idx="colIdx.work_num">
      <input
        class="cell-edit cell-num"
        v-model="newRow.work_num"
        @keydown="onKeydown"
      >
    </td>

    <!-- work_designation -->
    <td :data-col-idx="colIdx.work_designation">
      <input
        class="cell-edit"
        v-model="newRow.work_designation"
        @keydown="onKeydown"
      >
    </td>

    <!-- work_name -->
    <td :data-col-idx="colIdx.work_name">
      <input
        ref="firstInput"
        class="cell-edit"
        v-model="newRow.work_name"
        placeholder="Наименование"
        @keydown="onKeydown"
      >
    </td>

    <!-- date_start -->
    <td :data-col-idx="colIdx.date_start">
      <input type="date" class="cell-edit" v-model="newRow.date_start" @keydown="onKeydown">
    </td>

    <!-- date_end -->
    <td :data-col-idx="colIdx.date_end">
      <input type="date" class="cell-edit" v-model="newRow.date_end" @keydown="onKeydown">
    </td>

    <!-- sheets_a4 -->
    <td :data-col-idx="colIdx.sheets_a4">
      <input
        class="cell-edit cell-num"
        v-model="newRow.sheets_a4"
        @input="calcLabor"
        @keydown="onKeydown"
      >
    </td>

    <!-- norm -->
    <td :data-col-idx="colIdx.norm">
      <input
        class="cell-edit cell-num"
        v-model="newRow.norm"
        @input="calcLabor"
        @keydown="onKeydown"
      >
    </td>

    <!-- coeff -->
    <td :data-col-idx="colIdx.coeff">
      <input
        class="cell-edit cell-num"
        v-model="newRow.coeff"
        @input="calcLabor"
        @keydown="onKeydown"
      >
    </td>

    <!-- labor: вычисляемое, но можно ввести вручную -->
    <td :data-col-idx="colIdx.labor">
      <input class="cell-edit cell-num" v-model="newRow.labor" @keydown="onKeydown">
    </td>

    <!-- center: дропдаун НТЦ -->
    <td :data-col-idx="colIdx.center">
      <select class="cell-edit" v-model="newRow.center">
        <option value="">--</option>
        <option
          v-for="d in (store.dirs.value.center || [])"
          :key="d.value"
          :value="d.value"
        >{{ d.value }}</option>
      </select>
    </td>

    <!-- dept: дропдаун отделов (каскадно влияет на sector_head и executor) -->
    <td :data-col-idx="colIdx.dept">
      <select class="cell-edit" v-model="newRow.dept" @change="onDeptChange">
        <option value="">--</option>
        <option
          v-for="d in (store.dirs.value.dept || [])"
          :key="d.value"
          :value="d.value"
        >{{ d.value }}</option>
      </select>
    </td>

    <!-- sector_head: дропдаун секторов (каскадно влияет на executor) -->
    <td :data-col-idx="colIdx.sector_head">
      <select class="cell-edit" v-model="newRow.sector_head" @change="onSectorChange">
        <option value="">--</option>
        <option
          v-for="h in filteredSectors"
          :key="h.value"
          :value="h.value"
        >{{ h.value }}</option>
      </select>
    </td>

    <!-- executor: дропдаун исполнителей (фильтрованный по dept/sector) -->
    <td :data-col-idx="colIdx.executor">
      <select class="cell-edit" v-model="newRow.executor">
        <option value="">--</option>
        <option
          v-for="e in filteredExecutors"
          :key="e.value"
          :value="e.value"
        >{{ e.value }}</option>
      </select>
    </td>

    <!-- task_type: дропдаун типа задачи -->
    <td :data-col-idx="colIdx.task_type">
      <select class="cell-edit" v-model="newRow.task_type">
        <option
          v-for="d in (store.dirs.value.task_type || [])"
          :key="d.value"
          :value="d.value"
        >{{ d.value }}</option>
      </select>
    </td>

    <!-- Действия: Сохранить (✓) и Отмена (✕) -->
    <td data-col-idx="19" style="text-align:center;white-space:nowrap;">
      <button
        class="pp-add-save"
        title="Сохранить строку"
        :disabled="saving"
        @click="save"
      >{{ saving ? '...' : '\u2713' }}</button>
      <button
        class="pp-add-cancel"
        title="Отмена"
        @click="$emit('cancel')"
      >&times;</button>
    </td>
  </tr>
</template>

<script setup>
import { ref, reactive, computed, inject, onMounted, nextTick } from 'vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'
import { PP_COL_IDX } from '../../constants/pp.js'
import { createPPRow } from '../../api/pp.js'

const store = inject(PP_STORE_KEY)

const emit = defineEmits(['saved', 'cancel'])

const colIdx = PP_COL_IDX

const saving = ref(false)
const firstInput = ref(null)

// ── Значение начальника сектора по умолчанию (для sector_head) ─────────
function getDefaultSectorHead() {
  if (store.userRole === 'sector_head' && store.userSector) {
    const heads = store.dirs.value.sector_head || []
    const match = heads.find(
      h => h.value === store.userSector || h.value === store.userSectorName
    )
    if (match) return match.value
    return store.userSectorName || store.userSector
  }
  return ''
}

// ── Дефолтный НТЦ (центр) ──────────────────────────────────────────────
function getDefaultCenter() {
  if (
    ['dept_head', 'dept_deputy', 'sector_head'].includes(store.userRole) &&
    store.userCenter
  ) {
    return store.userCenter
  }
  return ''
}

// ── Дефолтный тип задачи ───────────────────────────────────────────────
function getDefaultTaskType() {
  const types = store.dirs.value.task_type || []
  return types.length ? types[0].value : 'Выпуск нового документа'
}

// ── Реактивные данные новой строки ─────────────────────────────────────
const newRow = reactive({
  row_code: '',
  work_order: '',
  pp_stage_id: '',
  milestone_num: '',
  work_num: '',
  work_designation: '',
  work_name: '',
  date_start: '',
  date_end: '',
  sheets_a4: '',
  norm: '',
  coeff: '',
  labor: '',
  center: getDefaultCenter(),
  dept: store.userDept || '',
  sector_head: getDefaultSectorHead(),
  executor: '',
  task_type: getDefaultTaskType(),
})

// ── Каскадные фильтры ──────────────────────────────────────────────────

/** Секторы, отфильтрованные по выбранному отделу */
const filteredSectors = computed(() => {
  const allHeads = store.dirs.value.sector_head || []
  if (!newRow.dept) return allHeads
  const deptEntry = (store.dirs.value.dept || []).find(d => d.value === newRow.dept)
  return deptEntry ? allHeads.filter(h => h.parent_id === deptEntry.id) : allHeads
})

/** Исполнители, отфильтрованные по сектору (если задан) или отделу */
const filteredExecutors = computed(() => {
  const allEmps = store.dirs.value.employees || []
  if (newRow.sector_head) {
    return allEmps.filter(e => e.sector === newRow.sector_head)
  }
  if (newRow.dept) {
    return allEmps.filter(e => e.dept === newRow.dept)
  }
  return allEmps
})

// ── Обработчики каскадных зависимостей ─────────────────────────────────

/** При смене отдела: сбросить сектор и исполнителя */
function onDeptChange() {
  newRow.sector_head = ''
  newRow.executor = ''
}

/** При смене сектора: сбросить исполнителя */
function onSectorChange() {
  newRow.executor = ''
}

/** При смене PPStage: подставить row_code и work_order из ЕТБД */
function onPPStageChange() {
  const stg = store.ppStages.value.find(
    s => String(s.id) === String(newRow.pp_stage_id)
  )
  newRow.row_code = stg ? (stg.row_code || '') : ''
  newRow.work_order = stg ? (stg.work_order || '') : ''
}

// ── Авто-расчёт трудоёмкости ───────────────────────────────────────────
function calcLabor() {
  const sheets = parseFloat(String(newRow.sheets_a4).replace(',', '.'))
  const norm = parseFloat(String(newRow.norm).replace(',', '.'))
  const coeff = parseFloat(String(newRow.coeff).replace(',', '.'))
  if (!isNaN(sheets) && !isNaN(norm) && !isNaN(coeff)) {
    newRow.labor = +(sheets * norm * coeff).toFixed(2)
  } else {
    newRow.labor = ''
  }
}

// ── Клавиатурная навигация ─────────────────────────────────────────────
function onKeydown(e) {
  if (e.key === 'Enter') { e.preventDefault(); save() }
  if (e.key === 'Escape') { emit('cancel') }
}

// ── Сохранение строки ──────────────────────────────────────────────────
async function save() {
  // Наименование работы обязательно
  if (!newRow.work_name.trim()) {
    // TODO: заменить на showToast после интеграции
    alert('Укажите наименование работы')
    return
  }

  saving.value = true
  try {
    const body = { project_id: store.currentProjectId.value }
    // Собираем все заполненные поля
    const fields = [
      'work_designation', 'work_name', 'date_start', 'date_end',
      'sheets_a4', 'norm', 'coeff', 'labor',
      'center', 'dept', 'sector_head', 'executor', 'task_type',
      'milestone_num', 'work_num',
    ]
    for (const f of fields) {
      if (newRow[f] !== '' && newRow[f] != null) {
        body[f] = newRow[f]
      }
    }
    // pp_stage передаём как ID
    if (newRow.pp_stage_id) body.pp_stage = newRow.pp_stage_id

    const resp = await createPPRow(body)
    emit('saved', resp)
  } catch (err) {
    console.error('PPAddRow: ошибка сохранения', err)
    alert(err.error || 'Ошибка сохранения строки')
  } finally {
    saving.value = false
  }
}

// ── Автофокус на первое поле ───────────────────────────────────────────
onMounted(() => {
  nextTick(() => {
    if (firstInput.value) firstInput.value.focus()
  })
})
</script>

<style scoped>
.pp-add-save {
  background: var(--success, #22c55e);
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 13px;
  margin-right: 2px;
}
.pp-add-save:disabled { opacity: 0.5; cursor: default; }
.pp-add-cancel {
  background: transparent;
  color: var(--danger, #ef4444);
  border: 1px solid var(--danger, #ef4444);
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 13px;
}
</style>
