<template>
  <!-- Модалка списка снимков (baselines) с возможностью сравнения -->
  <BaseModal
    :show="show && currentView === 'list'"
    title="Снимки (Baselines)"
    max-width="780px"
    @close="$emit('close')"
  >
    <div style="overflow-x:auto;">
      <!-- Кнопка сравнения двух выбранных -->
      <div v-if="baselines.length >= 2" style="margin-bottom:10px;">
        <button
          class="btn btn-outline btn-sm"
          :disabled="checkedIds.length !== 2"
          @click="compareTwoSelected"
        >
          <i class="fas fa-columns"></i> Сравнить выбранные
        </button>
        <span class="text-muted" style="font-size:12px; margin-left:8px;">
          {{ compareHint }}
        </span>
      </div>

      <table class="baseline-table">
        <thead>
          <tr>
            <th style="width:32px;"></th>
            <th>Версия</th>
            <th>Дата</th>
            <th>Автор</th>
            <th>Комментарий</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="baselines.length">
            <tr v-for="b in baselines" :key="b.id">
              <td>
                <label class="baseline-check">
                  <input
                    type="checkbox"
                    :value="b.id"
                    v-model="checkedIds"
                    @change="onCheckChange"
                  />
                  <span></span>
                </label>
              </td>
              <td><strong>v{{ b.version }}</strong></td>
              <td>{{ formatDate(b.created_at) }}</td>
              <td>{{ b.created_by || '\u2014' }}</td>
              <td>{{ b.comment || '\u2014' }}</td>
              <td>
                <button class="btn btn-ghost btn-sm" @click="onView(b.id)" title="Просмотр">
                  <i class="fas fa-eye"></i>
                </button>
                <button class="btn btn-ghost btn-sm" @click="onCompareWithCurrent(b.id, b.version)" title="Сравнить с текущим">
                  <i class="fas fa-not-equal"></i>
                </button>
                <button
                  v-if="isWriter"
                  class="btn btn-ghost btn-sm btn-danger-text"
                  @click="onDelete(b.id)"
                  title="Удалить"
                >
                  <i class="fas fa-trash"></i>
                </button>
              </td>
            </tr>
          </template>
          <tr v-else>
            <td colspan="6" class="text-center text-muted">Нет снимков</td>
          </tr>
        </tbody>
      </table>
    </div>
  </BaseModal>

  <!-- Просмотр одного снимка -->
  <BaselineViewModal
    :show="show && currentView === 'view'"
    :baseline="viewBaseline"
    @back="currentView = 'list'"
    @close="$emit('close')"
  />

  <!-- Сравнение двух снимков -->
  <BaselineCompareModal
    :show="show && currentView === 'compare'"
    :left="compareLeft"
    :right="compareRight"
    :right-is-current="compareRightIsCurrent"
    @back="currentView = 'list'"
    @close="$emit('close')"
  />
</template>

<script setup>
/**
 * BaselineListModal.vue — список снимков с навигацией к просмотру и сравнению.
 * Поддерживает три внутренних вида: list, view, compare.
 */
import { ref, watch, inject, computed } from 'vue'
import { ENTERPRISE_STORE_KEY } from '../../../stores/useEnterpriseStore.js'
import { fetchBaselines, fetchBaseline, deleteBaseline } from '../../../api/enterprise.js'
import BaseModal from '../../BaseModal.vue'
import BaselineViewModal from './BaselineViewModal.vue'
import BaselineCompareModal from './BaselineCompareModal.vue'

const props = defineProps({
  show:         { type: Boolean, required: true },
  projectId:    { type: [Number, String], default: null },
  currentCross: { type: Object, default: null },
})

const emit = defineEmits(['close'])

const store = inject(ENTERPRISE_STORE_KEY)
const isWriter = computed(() => store.isWriter)

// ── Состояние ──────────────────────────────────────────────────────────
const baselines = ref([])
const currentView = ref('list') // 'list' | 'view' | 'compare'
const checkedIds = ref([])

// Просмотр
const viewBaseline = ref(null)

// Сравнение
const compareLeft = ref(null)
const compareRight = ref(null)
const compareRightIsCurrent = ref(false)

// ── Загрузка при открытии ──────────────────────────────────────────────
watch(() => props.show, async (v) => {
  if (v && props.projectId) {
    currentView.value = 'list'
    checkedIds.value = []
    await loadBaselines()
  }
})

async function loadBaselines() {
  try {
    const data = await fetchBaselines(props.projectId)
    baselines.value = data.baselines || []
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

// ── Подсказка для сравнения ────────────────────────────────────────────

const compareHint = computed(() => {
  if (checkedIds.value.length === 2) {
    const b1 = baselines.value.find(b => b.id === checkedIds.value[0])
    const b2 = baselines.value.find(b => b.id === checkedIds.value[1])
    return `v${b1?.version} \u2194 v${b2?.version}`
  }
  return 'Выберите 2 снимка для сравнения'
})

/** Ограничение: максимум 2 чекбокса (FIFO) */
function onCheckChange() {
  if (checkedIds.value.length > 2) {
    checkedIds.value = checkedIds.value.slice(-2)
  }
}

// ── Действия ───────────────────────────────────────────────────────────

async function onView(id) {
  try {
    const data = await fetchBaseline(id)
    viewBaseline.value = data.baseline
    currentView.value = 'view'
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

async function onCompareWithCurrent(id, version) {
  if (!props.currentCross) return
  try {
    const data = await fetchBaseline(id)
    compareLeft.value = data.baseline
    // Виртуальный правый снимок из текущего состояния
    compareRight.value = {
      version: props.currentCross.version,
      created_at: new Date().toISOString(),
      created_by: '',
      entries: [{
        data: {
          _type: 'schedule_state',
          stages: props.currentCross.stages || [],
          milestones: props.currentCross.milestones || [],
        }
      }],
    }
    compareRightIsCurrent.value = true
    currentView.value = 'compare'
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

async function compareTwoSelected() {
  if (checkedIds.value.length !== 2) return
  // Сортируем по версии (меньшая = left)
  const sorted = [...checkedIds.value].sort((a, b) => {
    const ba = baselines.value.find(x => x.id === a)
    const bb = baselines.value.find(x => x.id === b)
    return (ba?.version || 0) - (bb?.version || 0)
  })
  try {
    const [dataA, dataB] = await Promise.all([
      fetchBaseline(sorted[0]),
      fetchBaseline(sorted[1]),
    ])
    compareLeft.value = dataA.baseline
    compareRight.value = dataB.baseline
    compareRightIsCurrent.value = false
    currentView.value = 'compare'
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

async function onDelete(id) {
  if (!confirm('Удалить снимок?')) return
  try {
    await deleteBaseline(id)
    await loadBaselines()
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

// ── Утилиты ────────────────────────────────────────────────────────────

function formatDate(iso) {
  if (!iso) return '\u2014'
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>
