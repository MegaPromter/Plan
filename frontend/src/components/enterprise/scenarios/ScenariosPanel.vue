<template>
  <!-- Панель «Сценарии что-если» -->
  <div class="ent-panel">
    <!-- Тулбар: фильтры + кнопка создания -->
    <div class="ent-toolbar">
      <div class="ent-toolbar-left">
        <select v-model="store.scenarioFilterStatus.value" class="form-select form-select-sm" @change="loadData">
          <option value="">Все статусы</option>
          <option value="draft">Черновик</option>
          <option value="active">Активный</option>
          <option value="archived">Архив</option>
        </select>
        <button class="project-picker-btn" @click="$emit('open-project-picker')">
          <i class="fas fa-folder-open"></i>
          <span class="picker-label">{{ projectLabel }}</span>
        </button>
      </div>
      <div v-if="store.isWriter" class="ent-toolbar-right">
        <button class="btn btn-primary btn-sm" @click="showModal = true; editingScenario = null">
          <i class="fas fa-plus"></i> Новый сценарий
        </button>
      </div>
    </div>

    <!-- Список или детальный вид -->
    <ScenarioListView
      v-if="!store.currentScenario.value"
      :scenarios="store.scenariosList.value"
      :is-writer="store.isWriter"
      @open="onOpenDetail"
      @edit="onEdit"
      @delete="onDelete"
    />

    <ScenarioDetailView
      v-else
      :scenario="store.currentScenario.value"
      :is-writer="store.isWriter"
      @back="store.currentScenario.value = null"
      @edit="onEdit"
      @entry-added="reloadDetail"
      @entry-deleted="reloadDetail"
    />

    <!-- Модалка создания/редактирования сценария -->
    <ScenarioModal
      :show="showModal"
      :scenario="editingScenario"
      :projects="store.projectsList.value"
      @saved="onScenarioSaved"
      @close="showModal = false; editingScenario = null"
    />
  </div>
</template>

<script setup>
/**
 * ScenariosPanel.vue — панель сценариев «что-если».
 * Управляет списком, детальным видом, фильтрами.
 */
import { ref, computed, inject, onMounted, watch } from 'vue'
import { ENTERPRISE_STORE_KEY } from '../../../stores/useEnterpriseStore.js'
import { fetchScenarios, fetchScenario, deleteScenario } from '../../../api/enterprise.js'
import ScenarioListView from './ScenarioListView.vue'
import ScenarioDetailView from './ScenarioDetailView.vue'
import ScenarioModal from './ScenarioModal.vue'

const store = inject(ENTERPRISE_STORE_KEY)

defineEmits(['open-project-picker'])

const showModal = ref(false)
const editingScenario = ref(null)

const projectLabel = computed(() => {
  if (!store.scenarioProjectId.value) return 'Все проекты'
  const p = store.projectsList.value.find(x => x.id === store.scenarioProjectId.value)
  return p ? (p.name_short || p.name_full) : 'Проект'
})

// ── Загрузка ───────────────────────────────────────────────────────────

async function loadData() {
  try {
    const data = await fetchScenarios({
      status: store.scenarioFilterStatus.value || undefined,
      project_id: store.scenarioProjectId.value || undefined,
    })
    store.scenariosList.value = data.scenarios || []
  } catch (e) {
    console.error('ScenariosPanel: loadScenarios error', e)
  }
}

watch(() => store.scenarioProjectId.value, () => loadData())
onMounted(() => loadData())

// ── Действия ───────────────────────────────────────────────────────────

async function onOpenDetail(id) {
  try {
    const data = await fetchScenario(id)
    store.currentScenario.value = data.scenario
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

function onEdit(id) {
  const s = store.scenariosList.value.find(x => x.id === id)
    || (store.currentScenario.value?.id === id ? store.currentScenario.value : null)
  if (!s) return
  editingScenario.value = { ...s }
  showModal.value = true
}

async function onDelete(id) {
  if (!confirm('Удалить сценарий?')) return
  try {
    await deleteScenario(id)
    await loadData()
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}

function onScenarioSaved() {
  showModal.value = false
  editingScenario.value = null
  loadData()
  // Если открыт детальный вид — перезагрузим
  if (store.currentScenario.value) {
    reloadDetail()
  }
}

async function reloadDetail() {
  if (!store.currentScenario.value) return
  try {
    const data = await fetchScenario(store.currentScenario.value.id)
    store.currentScenario.value = data.scenario
  } catch (e) {
    console.error('ScenariosPanel: reloadDetail error', e)
  }
}
</script>
