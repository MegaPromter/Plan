<template>
  <!-- Панель «Генеральный график» -->
  <div class="ent-panel">
    <!-- Тулбар -->
    <div class="ent-toolbar">
      <div class="ent-toolbar-left">
        <button class="project-picker-btn" @click="$emit('open-project-picker')">
          <i class="fas fa-folder-open"></i>
          <span class="picker-label">{{ pickerLabel }}</span>
        </button>
      </div>
      <div v-if="store.isWriter && store.currentGG.value" class="ent-toolbar-right">
        <button class="btn btn-primary btn-sm" @click="showStageModal = true">
          <i class="fas fa-plus"></i> Пункт
        </button>
        <button class="btn btn-outline btn-sm" @click="showMilestoneModal = true">
          <i class="fas fa-flag"></i> Веха
        </button>
      </div>
    </div>

    <!-- Пустое состояние: проект не выбран -->
    <div v-if="!store.selectedProjectId.value" class="empty-state">
      <i class="fas fa-stream"></i>
      <p>Выберите проект для просмотра генерального графика</p>
    </div>

    <!-- Пустое состояние: ГГ не создан -->
    <div v-else-if="!store.currentGG.value" class="empty-state">
      <i class="fas fa-stream"></i>
      <p>ГГ не создан.</p>
      <button v-if="store.isWriter" class="btn btn-primary btn-sm" @click="onCreateGG">
        <i class="fas fa-plus"></i> Создать ГГ
      </button>
    </div>

    <!-- Содержимое ГГ -->
    <div v-else>
      <!-- Переключатель Таблица / Гант -->
      <div class="gg-view-toggle">
        <button
          class="btn btn-sm btn-outline"
          :class="{ active: currentView === 'table' }"
          @click="currentView = 'table'"
        >
          <i class="fas fa-table"></i> Таблица
        </button>
        <button
          class="btn btn-sm btn-outline"
          :class="{ active: currentView === 'gantt' }"
          @click="currentView = 'gantt'"
        >
          <i class="fas fa-chart-bar"></i> Гант
        </button>
      </div>

      <!-- Табличный вид -->
      <GGTableView
        v-show="currentView === 'table'"
        :schedule="store.currentGG.value"
        :is-writer="store.isWriter"
        @edit-stage="onEditStage"
        @delete-stage="onDeleteStage"
        @delete-milestone="onDeleteMilestone"
      />

      <!-- Гант-вид (v-show для сохранения DOM) -->
      <GGGanttView
        v-show="currentView === 'gantt'"
        :schedule="store.currentGG.value"
        :is-writer="store.isWriter"
        :active="currentView === 'gantt'"
        @edit-stage="onEditStage"
      />
    </div>

    <!-- Модалка создания/редактирования пункта -->
    <GGStageModal
      :show="showStageModal"
      :stage="editingStage"
      :schedule-id="store.currentGG.value?.id"
      :project-id="store.selectedProjectId.value"
      @saved="onStageSaved"
      @close="showStageModal = false; editingStage = null"
    />

    <!-- Модалка создания вехи -->
    <GGMilestoneModal
      :show="showMilestoneModal"
      :schedule-id="store.currentGG.value?.id"
      :project-id="store.selectedProjectId.value"
      :stages="store.currentGG.value?.stages || []"
      @saved="onMilestoneSaved"
      @close="showMilestoneModal = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, inject, watch } from 'vue'
import { ENTERPRISE_STORE_KEY } from '../../../stores/useEnterpriseStore.js'
import { fetchGG, createGG, deleteGGStage, deleteGGMilestone } from '../../../api/enterprise.js'
import GGTableView from './GGTableView.vue'
import GGGanttView from './GGGanttView.vue'
import GGStageModal from './GGStageModal.vue'
import GGMilestoneModal from './GGMilestoneModal.vue'

const store = inject(ENTERPRISE_STORE_KEY)

defineEmits(['open-project-picker'])

// ── Состояние вида ──────────────────────────────────────────────────────
const currentView = ref('table')
const showStageModal = ref(false)
const showMilestoneModal = ref(false)
const editingStage = ref(null) // null = создание, object = редактирование

// ── Лейбл кнопки выбора проекта ─────────────────────────────────────────
const pickerLabel = computed(() => {
  if (!store.selectedProjectId.value) return 'Выберите проект...'
  const p = store.projectsList.value.find(x => x.id === store.selectedProjectId.value)
  return p ? (p.name_short || p.name_full) : 'Проект #' + store.selectedProjectId.value
})

// ── Загрузка ГГ при смене проекта ───────────────────────────────────────
watch(() => store.selectedProjectId.value, async (pid) => {
  if (!pid) {
    store.currentGG.value = null
    return
  }
  await loadGG(pid)
})

/** Загрузить ГГ для проекта */
async function loadGG(projectId) {
  try {
    const data = await fetchGG(projectId)
    store.currentGG.value = data.schedule || null
  } catch (e) {
    console.error('GGPanel: loadGG error', e)
    store.currentGG.value = null
  }
}

/** Создать ГГ для выбранного проекта */
async function onCreateGG() {
  const pid = store.selectedProjectId.value
  if (!pid) return
  try {
    await createGG(pid)
    await loadGG(pid)
  } catch (e) {
    alert(e.error || 'Ошибка создания ГГ')
  }
}

// ── Операции с пунктами ─────────────────────────────────────────────────

function onEditStage(id) {
  const s = (store.currentGG.value?.stages || []).find(x => x.id === id)
  if (!s) return
  editingStage.value = { ...s }
  showStageModal.value = true
}

async function onDeleteStage(id) {
  if (!confirm('Удалить пункт?')) return
  try {
    await deleteGGStage(id)
    await loadGG(store.selectedProjectId.value)
  } catch (e) {
    alert(e.error || 'Ошибка удаления')
  }
}

function onStageSaved() {
  showStageModal.value = false
  editingStage.value = null
  loadGG(store.selectedProjectId.value)
}

// ── Операции с вехами ───────────────────────────────────────────────────

async function onDeleteMilestone(id) {
  if (!confirm('Удалить веху?')) return
  try {
    await deleteGGMilestone(id)
    await loadGG(store.selectedProjectId.value)
  } catch (e) {
    alert(e.error || 'Ошибка удаления')
  }
}

function onMilestoneSaved() {
  showMilestoneModal.value = false
  loadGG(store.selectedProjectId.value)
}
</script>
