<template>
  <!-- Панель «Сквозной график» -->
  <div class="ent-panel">
    <!-- Тулбар -->
    <div class="ent-toolbar">
      <div class="ent-toolbar-left">
        <button class="project-picker-btn" @click="$emit('open-project-picker')">
          <i class="fas fa-folder-open"></i>
          <span class="picker-label">{{ pickerLabel }}</span>
        </button>
      </div>
      <div v-if="store.isWriter && store.currentCross.value && store.currentCross.value.edit_owner !== 'locked'" class="ent-toolbar-right">
        <button class="btn btn-primary btn-sm" @click="showStageModal = true; editingStage = null">
          <i class="fas fa-plus"></i> Этап
        </button>
        <button class="btn btn-outline btn-sm" @click="onAddMilestone">
          <i class="fas fa-flag"></i> Веха
        </button>
        <button class="btn btn-outline btn-sm" @click="showBaselineCreate = true">
          <i class="fas fa-camera"></i> Снимок
        </button>
      </div>
    </div>

    <!-- Пустое состояние: проект не выбран -->
    <div v-if="!store.selectedProjectId.value" class="empty-state">
      <i class="fas fa-project-diagram"></i>
      <p>Выберите проект для просмотра сквозного графика</p>
    </div>

    <!-- Пустое состояние: Сквозной не создан -->
    <div v-else-if="!store.currentCross.value" class="empty-state">
      <i class="fas fa-project-diagram"></i>
      <p>Сквозной график не создан.</p>
      <button v-if="store.isWriter" class="btn btn-primary btn-sm" @click="onCreateCross">
        <i class="fas fa-plus"></i> Создать из ГГ
      </button>
    </div>

    <!-- Содержимое сквозного графика -->
    <div v-else>
      <!-- Заголовок -->
      <h2 class="ent-section-title" style="font-size:17px; margin-bottom:12px;">
        {{ crossTitle }}
      </h2>

      <!-- Мета-бар: версия, режим, гранулярность -->
      <div class="ent-meta-bar">
        <div class="ent-meta-item">
          <span class="ent-meta-label">Версия:</span>
          <a href="#" class="baseline-version-link" @click.prevent="showBaselineList = true">
            {{ store.currentCross.value.version }}
          </a>
        </div>
        <div class="ent-meta-item">
          <span class="ent-meta-label">Режим:</span>
          <select
            v-if="store.isWriter"
            v-model="editOwner"
            class="edit-owner-select"
            :class="'edit-owner-select--' + editOwner"
          >
            <option value="cross">Сквозной</option>
            <option value="pp">ПП</option>
            <option value="locked">Заблокирован</option>
          </select>
          <span v-else class="edit-lock-badge" :class="'edit-lock-badge--' + store.currentCross.value.edit_owner">
            {{ EDIT_OWNER_LABELS[store.currentCross.value.edit_owner] || store.currentCross.value.edit_owner }}
          </span>
        </div>
        <div class="ent-meta-item">
          <span class="ent-meta-label">Гранулярность:</span>
          <select
            v-if="store.isWriter"
            v-model="granularity"
            class="edit-owner-select"
          >
            <option value="whole">Весь график</option>
            <option value="per_dept">По отделам</option>
          </select>
          <span v-else>{{ store.currentCross.value.granularity === 'whole' ? 'Весь график' : 'По отделам' }}</span>
        </div>
        <button
          v-if="store.isWriter && settingsChanged"
          class="btn btn-primary btn-sm"
          @click="applySettings"
        >
          <i class="fas fa-check"></i> Применить
        </button>
      </div>

      <!-- Таблица пунктов и этапов -->
      <CrossTable
        :cross="store.currentCross.value"
        :is-writer="store.isWriter"
        @edit-stage="onEditStage"
        @delete-stage="onDeleteStage"
        @delete-milestone="onDeleteMilestone"
        @assign-works="onAssignWorks"
        @unlink-work="onUnlinkWork"
      />
    </div>

    <!-- Модалки -->
    <CrossStageModal
      :show="showStageModal"
      :stage="editingStage"
      :cross="store.currentCross.value"
      :project-id="store.selectedProjectId.value"
      @saved="onStageSaved"
      @close="showStageModal = false; editingStage = null"
    />

    <AssignWorksModal
      :show="showAssignWorks"
      :stage-id="assignStageId"
      :stage-name="assignStageName"
      :unassigned="store.currentCross.value?.unassigned_works || []"
      @assigned="onWorksAssigned"
      @close="showAssignWorks = false"
    />

    <!-- Снимки (baselines) -->
    <BaselineCreateModal
      :show="showBaselineCreate"
      :project-id="store.selectedProjectId.value"
      @created="onBaselineCreated"
      @close="showBaselineCreate = false"
    />

    <BaselineListModal
      :show="showBaselineList"
      :project-id="store.selectedProjectId.value"
      :current-cross="store.currentCross.value"
      @close="showBaselineList = false"
    />
  </div>
</template>

<script setup>
/**
 * CrossPanel.vue — панель сквозного графика.
 * Загрузка данных, настройки (edit_owner, granularity),
 * управление модалками этапов, вех, привязки работ и снимков.
 */
import { ref, computed, inject, watch } from 'vue'
import { ENTERPRISE_STORE_KEY } from '../../../stores/useEnterpriseStore.js'
import { EDIT_OWNER_LABELS } from '../../../constants/enterprise.js'
import {
  fetchCross, createCross, updateCrossSettings,
  deleteCrossStage, createCrossMilestone, deleteCrossMilestone as apiDeleteCrossMilestone,
  unlinkWork as apiUnlinkWork,
} from '../../../api/enterprise.js'
import CrossTable from './CrossTable.vue'
import CrossStageModal from './CrossStageModal.vue'
import AssignWorksModal from './AssignWorksModal.vue'
import BaselineCreateModal from '../baselines/BaselineCreateModal.vue'
import BaselineListModal from '../baselines/BaselineListModal.vue'

const store = inject(ENTERPRISE_STORE_KEY)

defineEmits(['open-project-picker'])

// ── Состояние ──────────────────────────────────────────────────────────
const showStageModal = ref(false)
const editingStage = ref(null)
const showAssignWorks = ref(false)
const assignStageId = ref(null)
const assignStageName = ref('')
const showBaselineCreate = ref(false)
const showBaselineList = ref(false)

// Настройки режима/гранулярности (локальные копии для отслеживания изменений)
const editOwner = ref('cross')
const granularity = ref('whole')

// ── Вычисляемые ────────────────────────────────────────────────────────

const pickerLabel = computed(() => {
  if (!store.selectedProjectId.value) return 'Выберите проект...'
  const p = store.projectsList.value.find(x => x.id === store.selectedProjectId.value)
  return p ? (p.name_short || p.name_full) : 'Проект #' + store.selectedProjectId.value
})

const crossTitle = computed(() => {
  const p = store.projectsList.value.find(x => x.id === store.selectedProjectId.value)
  return p
    ? 'Сквозной график по проекту ' + (p.name_short || p.name_full)
    : 'Сквозной график'
})

/** Есть ли несохранённые изменения настроек */
const settingsChanged = computed(() => {
  const c = store.currentCross.value
  if (!c) return false
  return editOwner.value !== c.edit_owner || granularity.value !== c.granularity
})

// ── Загрузка при смене проекта ─────────────────────────────────────────

watch(() => store.selectedProjectId.value, async (pid) => {
  if (!pid) {
    store.currentCross.value = null
    return
  }
  await loadCross(pid)
})

/** Синхронизация локальных настроек при обновлении данных */
watch(() => store.currentCross.value, (c) => {
  if (c) {
    editOwner.value = c.edit_owner || 'cross'
    granularity.value = c.granularity || 'whole'
  }
})

// ── Методы ─────────────────────────────────────────────────────────────

async function loadCross(projectId) {
  try {
    const data = await fetchCross(projectId)
    store.currentCross.value = data.schedule || null
  } catch (e) {
    console.error('CrossPanel: loadCross error', e)
    store.currentCross.value = null
  }
}

async function onCreateCross() {
  const pid = store.selectedProjectId.value
  if (!pid) return
  try {
    await createCross(pid, { from_gg: true })
    await loadCross(pid)
  } catch (e) {
    alert(e.error || 'Ошибка создания')
  }
}

async function applySettings() {
  const pid = store.selectedProjectId.value
  if (!pid) return

  const body = {}
  const c = store.currentCross.value
  if (editOwner.value !== c.edit_owner) body.edit_owner = editOwner.value
  if (granularity.value !== c.granularity) body.granularity = granularity.value
  if (!Object.keys(body).length) return

  // Подтверждение блокировки
  if (body.edit_owner === 'locked') {
    if (!confirm('Заблокировать график? Редактирование станет невозможным.')) {
      editOwner.value = c.edit_owner
      return
    }
  }

  try {
    await updateCrossSettings(pid, body)
    if (body.edit_owner) c.edit_owner = body.edit_owner
    if (body.granularity) c.granularity = body.granularity
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

// ── Этапы ──────────────────────────────────────────────────────────────

function onEditStage(id) {
  const s = (store.currentCross.value?.stages || []).find(x => x.id === id)
  if (!s) return
  editingStage.value = { ...s }
  showStageModal.value = true
}

async function onDeleteStage(id) {
  if (!confirm('Удалить этап?')) return
  try {
    await deleteCrossStage(id)
    await loadCross(store.selectedProjectId.value)
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

function onStageSaved() {
  showStageModal.value = false
  editingStage.value = null
  loadCross(store.selectedProjectId.value)
}

// ── Вехи ───────────────────────────────────────────────────────────────

async function onAddMilestone() {
  const name = prompt('Название вехи:')
  if (!name) return
  const pid = store.selectedProjectId.value
  try {
    await createCrossMilestone(pid, { name })
    await loadCross(pid)
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

async function onDeleteMilestone(id) {
  if (!confirm('Удалить веху?')) return
  try {
    await apiDeleteCrossMilestone(id)
    await loadCross(store.selectedProjectId.value)
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

// ── Привязка работ ─────────────────────────────────────────────────────

function onAssignWorks(stageId) {
  const unassigned = store.currentCross.value?.unassigned_works || []
  if (!unassigned.length) {
    alert('Нет неназначенных работ ПП')
    return
  }
  const stage = (store.currentCross.value?.stages || []).find(s => s.id === stageId)
  assignStageId.value = stageId
  assignStageName.value = stage ? stage.name : String(stageId)
  showAssignWorks.value = true
}

function onWorksAssigned() {
  showAssignWorks.value = false
  loadCross(store.selectedProjectId.value)
}

async function onUnlinkWork({ stageId, workId }) {
  if (!confirm('Отвязать работу от этапа?')) return
  try {
    await apiUnlinkWork(stageId, workId)
    await loadCross(store.selectedProjectId.value)
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

// ── Снимки ─────────────────────────────────────────────────────────────

function onBaselineCreated() {
  showBaselineCreate.value = false
  loadCross(store.selectedProjectId.value)
}
</script>
