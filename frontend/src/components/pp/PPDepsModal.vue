<template>
  <!-- Модальное окно зависимостей задачи ПП -->
  <BaseModal
    :show="show"
    :title="''"
    max-width="720px"
    @close="$emit('close')"
  >
    <!-- Кастомный заголовок с именем задачи и датами -->
    <template #default>
      <div style="margin: -8px 0 12px;">
        <div style="font-size: 17px; font-weight: 600;">
          Зависимости: {{ taskLabel }}
        </div>
        <div style="font-size: 15px; font-weight: 600; color: var(--text2); margin-top: 4px;">
          Сроки: {{ formattedDates }}
        </div>
      </div>

      <!-- ── Предшественники ──────────────────────────────────────────── -->
      <div class="deps-section-title">
        &#x2B05; Предшественники
        <span style="color: var(--muted); font-weight: 400; font-size: 13px;">
          {{ predecessors.length ? `(${predecessors.length})` : '' }}
        </span>
      </div>

      <!-- Таблица предшественников -->
      <div v-if="predecessors.length === 0" style="color: var(--muted); font-size: 14px; padding: 8px 0;">
        Нет предшественников
      </div>
      <table v-else class="deps-table">
        <thead>
          <tr>
            <th>Задача</th>
            <th>Тип</th>
            <th>Лаг</th>
            <th>Даты</th>
            <th v-if="isWriter" style="width: 40px;"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="d in predecessors"
            :key="d.id"
            :style="d.conflict ? 'background: rgba(229,62,62,0.08);' : ''"
          >
            <td>{{ d.work_name || d.work_num || '#' + d.work_id }}</td>
            <td><span class="dep-type-badge">{{ d.dep_type }}</span></td>
            <td style="font-family: var(--mono);">{{ d.lag_days }}д</td>
            <td
              :style="{
                fontSize: '13px',
                color: d.conflict ? 'var(--danger, #e53e3e)' : 'var(--text2)',
                fontWeight: d.conflict ? '600' : 'normal',
              }"
            >
              {{ fmtDate(d.date_start) }} &rarr; {{ fmtDate(d.date_end) }}{{ d.conflict ? ' \u26A0' : '' }}
            </td>
            <td v-if="isWriter">
              <button class="btn-delete" title="Удалить" @click="doDeleteDep(d.id)">&times;</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Форма добавления предшественника -->
      <div v-if="isWriter" class="deps-add-form">
        <div style="flex: 1; min-width: 200px;">
          <label>Задача-предшественник</label>
          <SearchDropdown
            v-model="predSelected"
            :items="availableTasks"
            placeholder="Поиск задачи..."
            style="margin-top: 4px;"
          />
        </div>
        <div>
          <label>Тип связи</label>
          <select v-model="predDepType" style="margin-top: 4px;">
            <option v-for="t in DEP_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </div>
        <div>
          <label>Лаг (дней)</label>
          <input
            v-model.number="predLag"
            type="number"
            min="-365"
            max="365"
            style="width: 70px; margin-top: 4px;"
          >
        </div>
        <button class="btn btn-primary btn-sm" style="margin-top: 18px;" @click="doAddPredecessor">
          Добавить
        </button>
      </div>

      <!-- ── Последователи ────────────────────────────────────────────── -->
      <div class="deps-section-title" style="margin-top: 24px;">
        &#x27A1; Последователи
        <span style="color: var(--muted); font-weight: 400; font-size: 13px;">
          {{ successors.length ? `(${successors.length})` : '' }}
        </span>
      </div>

      <!-- Таблица последователей -->
      <div v-if="successors.length === 0" style="color: var(--muted); font-size: 14px; padding: 8px 0;">
        Нет последователей
      </div>
      <table v-else class="deps-table">
        <thead>
          <tr>
            <th>Задача</th>
            <th>Тип</th>
            <th>Лаг</th>
            <th>Даты</th>
            <th v-if="isWriter" style="width: 40px;"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="d in successors"
            :key="d.id"
            :style="d.conflict ? 'background: rgba(229,62,62,0.08);' : ''"
          >
            <td>{{ d.work_name || d.work_num || '#' + d.work_id }}</td>
            <td><span class="dep-type-badge">{{ d.dep_type }}</span></td>
            <td style="font-family: var(--mono);">{{ d.lag_days }}д</td>
            <td
              :style="{
                fontSize: '13px',
                color: d.conflict ? 'var(--danger, #e53e3e)' : 'var(--text2)',
                fontWeight: d.conflict ? '600' : 'normal',
              }"
            >
              {{ fmtDate(d.date_start) }} &rarr; {{ fmtDate(d.date_end) }}{{ d.conflict ? ' \u26A0' : '' }}
            </td>
            <td v-if="isWriter">
              <button class="btn-delete" title="Удалить" @click="doDeleteDep(d.id)">&times;</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Форма добавления последователя -->
      <div v-if="isWriter" class="deps-add-form">
        <div style="flex: 1; min-width: 200px;">
          <label>Задача-последователь</label>
          <SearchDropdown
            v-model="succSelected"
            :items="availableTasks"
            placeholder="Поиск задачи..."
            style="margin-top: 4px;"
          />
        </div>
        <div>
          <label>Тип связи</label>
          <select v-model="succDepType" style="margin-top: 4px;">
            <option v-for="t in DEP_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </div>
        <div>
          <label>Лаг (дней)</label>
          <input
            v-model.number="succLag"
            type="number"
            min="-365"
            max="365"
            style="width: 70px; margin-top: 4px;"
          >
        </div>
        <button class="btn btn-primary btn-sm" style="margin-top: 18px;" @click="doAddSuccessor">
          Добавить
        </button>
      </div>

      <!-- ── Панель выравнивания ──────────────────────────────────────── -->
      <div
        v-if="alignBarVisible"
        class="deps-align-bar"
        style="margin-top: 16px;"
      >
        <span style="font-size: 20px;">{{ hasConflict ? '\u26A0\uFE0F' : '' }}</span>
        <span
          style="flex: 1; font-size: 14px;"
          :style="{ color: hasConflict ? 'var(--danger, #e53e3e)' : 'var(--success, #38a169)' }"
        >
          {{ hasConflict ? '\u26A0 \u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d \u043a\u043e\u043d\u0444\u043b\u0438\u043a\u0442 \u0441\u0440\u043e\u043a\u043e\u0432' : '\u2713 \u0414\u0430\u0442\u044b \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0443\u044e\u0442 \u0437\u0430\u0432\u0438\u0441\u0438\u043c\u043e\u0441\u0442\u044f\u043c' }}
        </span>
        <!-- Кнопка выравнивания по предшественникам (cascade=false) -->
        <button
          v-if="hasConflict && hasPredConflict && isWriter"
          class="btn btn-primary btn-sm"
          @click="doAlign(false)"
        >
          Выровнять по предшественникам
        </button>
        <!-- Кнопка выравнивания последователей (cascade=true) -->
        <button
          v-if="hasConflict && hasSuccConflict && isWriter"
          class="btn btn-primary btn-sm"
          @click="doAlign(true)"
        >
          Выровнять последователей
        </button>
      </div>

      <!-- Сообщение о результате выравнивания -->
      <div v-if="alignMessage" style="margin-top: 8px; font-size: 14px; color: var(--success, #38a169);">
        {{ alignMessage }}
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * PPDepsModal — модальное окно зависимостей задачи ПП.
 *
 * Показывает предшественников и последователей, позволяет добавлять/удалять
 * зависимости, а также выравнивать даты (с каскадом или без).
 *
 * Порт логики из production_plan.js: openPPDepsModal, ppLoadDeps,
 * ppRenderPreds/ppRenderSuccs, ppAddPredecessor, ppAddSuccessor,
 * ppDeleteDep, ppAlignDates.
 */
import { ref, computed, watch, inject } from 'vue'
import BaseModal from '../BaseModal.vue'
import SearchDropdown from './PPSearchDropdown.vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'
import { DEP_TYPES } from '../../constants/pp.js'
import {
  fetchDependencies,
  addDependency,
  deleteDependency,
  alignDates,
} from '../../api/pp.js'

// ── Props / Emits ───────────────────────────────────────────────────────
const props = defineProps({
  show:     { type: Boolean, required: true },
  taskId:   { type: [Number, String], default: null },
  taskName: { type: String, default: '' },
  rows:     { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'updated'])

// ── Store ───────────────────────────────────────────────────────────────
const store = inject(PP_STORE_KEY)
const isWriter = store.isWriter

// ── Состояние зависимостей ──────────────────────────────────────────────
const predecessors = ref([])
const successors = ref([])
const hasConflict = ref(false)
const hasPredConflict = ref(false)
const hasSuccConflict = ref(false)
const alignMessage = ref('')

// ── Формы добавления ────────────────────────────────────────────────────
const predSelected = ref(null)    // id выбранной задачи-предшественника
const predDepType = ref('FS')
const predLag = ref(0)

const succSelected = ref(null)    // id выбранной задачи-последователя
const succDepType = ref('FS')
const succLag = ref(0)

// ── Вычисляемые свойства ────────────────────────────────────────────────

/** Находим текущую строку задачи для отображения дат */
const currentRow = computed(() => {
  if (!props.taskId) return null
  return props.rows.find(r => r.id === Number(props.taskId)) || null
})

/** Метка задачи для заголовка */
const taskLabel = computed(() => {
  if (props.taskName) return props.taskName
  const row = currentRow.value
  if (row) return row.work_name || row.work_num || '#' + row.id
  return '#' + (props.taskId || '')
})

/** Форматированные даты задачи */
const formattedDates = computed(() => {
  const row = currentRow.value
  if (!row) return '\u2014'
  const ds = row.date_start ? fmtDate(row.date_start) : '\u2014'
  const de = row.date_end ? fmtDate(row.date_end) : '\u2014'
  return `${ds} \u2192 ${de}`
})

/** Список задач для выбора (исключая текущую) */
const availableTasks = computed(() => {
  const tid = Number(props.taskId)
  return props.rows
    .filter(r => r.id !== tid)
    .map(r => ({
      id: r.id,
      label: (r.work_name || r.work_num || '#' + r.id) + (r.dept ? ` [${r.dept}]` : ''),
    }))
})

/** Показывать ли панель выравнивания */
const alignBarVisible = computed(() => {
  return predecessors.value.length > 0 || successors.value.length > 0
})

// ── Форматирование дат ──────────────────────────────────────────────────

/** Преобразует «YYYY-MM-DD» → «DD.MM.YYYY» */
function fmtDate(dateStr) {
  if (!dateStr) return '\u2014'
  return dateStr.split('-').reverse().join('.')
}

// ── Загрузка зависимостей при открытии ──────────────────────────────────

watch(() => [props.show, props.taskId], async ([visible, tid]) => {
  if (!visible || !tid) return
  // Сбрасываем состояние при каждом открытии
  alignMessage.value = ''
  predSelected.value = null
  predDepType.value = 'FS'
  predLag.value = 0
  succSelected.value = null
  succDepType.value = 'FS'
  succLag.value = 0
  await loadDeps()
}, { immediate: true })

/** Загрузить зависимости с сервера */
async function loadDeps() {
  if (!props.taskId) return
  try {
    const data = await fetchDependencies(props.taskId)
    predecessors.value = data.predecessors || []
    successors.value = data.successors || []
    hasConflict.value = !!data.has_conflict
    hasPredConflict.value = !!data.has_pred_conflict
    hasSuccConflict.value = !!data.has_succ_conflict
  } catch (e) {
    console.error('PPDepsModal: ошибка загрузки зависимостей', e)
  }
}

// ── Добавление предшественника ──────────────────────────────────────────

async function doAddPredecessor() {
  if (!predSelected.value) return
  try {
    await addDependency(props.taskId, {
      predecessor_id: Number(predSelected.value),
      dep_type: predDepType.value,
      lag_days: predLag.value,
    })
    // Сбрасываем форму
    predSelected.value = null
    predDepType.value = 'FS'
    predLag.value = 0
    // Перезагружаем зависимости
    await loadDeps()
    emit('updated')
  } catch (err) {
    const msg = err && err.error ? err.error : 'Ошибка добавления зависимости'
    alert(msg)
  }
}

// ── Добавление последователя ────────────────────────────────────────────

async function doAddSuccessor() {
  if (!succSelected.value) return
  try {
    // Добавляем зависимость к задаче-последователю,
    // где predecessor_id = текущая задача
    await addDependency(Number(succSelected.value), {
      predecessor_id: Number(props.taskId),
      dep_type: succDepType.value,
      lag_days: succLag.value,
    })
    succSelected.value = null
    succDepType.value = 'FS'
    succLag.value = 0
    await loadDeps()
    emit('updated')
  } catch (err) {
    const msg = err && err.error ? err.error : 'Ошибка добавления зависимости'
    alert(msg)
  }
}

// ── Удаление зависимости ────────────────────────────────────────────────

async function doDeleteDep(depId) {
  if (!confirm('Удалить эту зависимость?')) return
  try {
    await deleteDependency(depId)
    await loadDeps()
    emit('updated')
  } catch (e) {
    alert('Ошибка удаления зависимости')
  }
}

// ── Выравнивание дат ────────────────────────────────────────────────────

async function doAlign(cascade) {
  const msg = cascade
    ? 'Выровнять даты всех последователей по зависимостям?'
    : 'Выровнять даты этой задачи по предшественникам?'
  if (!confirm(msg)) return
  try {
    const data = await alignDates(props.taskId, { cascade })
    alignMessage.value = `Даты выровнены (${data.aligned_count || 0} задач)`
    await loadDeps()
    emit('updated')
  } catch (err) {
    const msg = err && err.error ? err.error : 'Ошибка выравнивания'
    alert(msg)
  }
}
</script>
