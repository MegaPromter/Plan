<template>
  <EntTabs :current-tab="store.currentTab.value" @switch-tab="onSwitchTab" />

  <!-- v-show для сохранения DOM Ганта между переключениями -->
  <div v-show="store.currentTab.value === 'portfolio'">
    <PortfolioPanel />
  </div>
  <div v-show="store.currentTab.value === 'gg'">
    <GGPanel @open-project-picker="openPicker('gg')" />
  </div>
  <div v-show="store.currentTab.value === 'cross'">
    <CrossPanel @open-project-picker="openPicker('cross')" />
  </div>
  <div v-show="store.currentTab.value === 'capacity'">
    <CapacityPanel @open-project-picker="openPicker('capacity')" />
  </div>
  <div v-show="store.currentTab.value === 'scenarios'">
    <ScenariosPanel @open-project-picker="openPicker('scenarios')" />
  </div>

  <!-- Модалка выбора проекта (общая) -->
  <ProjectPickerModal
    :show="showProjectPicker"
    :projects="store.projectsList.value"
    :current-project-id="pickerCurrentId"
    allow-clear
    @select="onPickerSelect"
    @clear="onPickerClear"
    @close="showProjectPicker = false"
  />
</template>

<script setup>
import { ref, provide, onMounted } from 'vue'
import { createEnterpriseStore, ENTERPRISE_STORE_KEY } from '../../stores/useEnterpriseStore.js'
import { useHashRouter } from '../../composables/useHashRouter.js'
import { fetchPortfolio } from '../../api/enterprise.js'
import EntTabs from './EntTabs.vue'
import PortfolioPanel from './portfolio/PortfolioPanel.vue'
import GGPanel from './gg/GGPanel.vue'
import CrossPanel from './cross/CrossPanel.vue'
import CapacityPanel from './capacity/CapacityPanel.vue'
import ScenariosPanel from './scenarios/ScenariosPanel.vue'
import ProjectPickerModal from './ProjectPickerModal.vue'

// Конфигурация из Django-шаблона (вставляется как JSON в #page-config)
const cfgEl = document.getElementById('page-config')
const cfg = cfgEl ? JSON.parse(cfgEl.textContent) : {}

// Создаём хранилище с конфигом из Django
const store = createEnterpriseStore({
  role: cfg.role || 'user',
  isWriter: cfg.is_writer || false,
  employees: cfg.employees || [],
})

// Пробрасываем store всем дочерним компонентам
provide(ENTERPRISE_STORE_KEY, store)

// Инициализируем hash-роутер (восстанавливает вкладку и проект из URL)
const { restore } = useHashRouter(store)

// ── Модалка выбора проекта (общая для ГГ, Сквозного, Загрузки, Сценариев) ──
const showProjectPicker = ref(false)
const pickerContext = ref('gg') // 'gg' | 'cross' | 'capacity' | 'scenarios'

/** Текущий проект для подсветки в пикере зависит от контекста */
const pickerCurrentId = ref(null)

function openPicker(ctx) {
  pickerContext.value = ctx
  // Для capacity и scenarios — свои projectId
  if (ctx === 'capacity') {
    pickerCurrentId.value = store.capacityProjectId.value
  } else if (ctx === 'scenarios') {
    pickerCurrentId.value = store.scenarioProjectId.value
  } else {
    pickerCurrentId.value = store.selectedProjectId.value
  }
  showProjectPicker.value = true
}

function onPickerSelect(projectId) {
  if (pickerContext.value === 'capacity') {
    store.capacityProjectId.value = projectId
  } else if (pickerContext.value === 'scenarios') {
    store.scenarioProjectId.value = projectId
  } else {
    store.selectedProjectId.value = projectId
  }
  showProjectPicker.value = false
}

function onPickerClear() {
  if (pickerContext.value === 'capacity') {
    store.capacityProjectId.value = null
  } else if (pickerContext.value === 'scenarios') {
    store.scenarioProjectId.value = null
  } else {
    store.selectedProjectId.value = null
  }
  showProjectPicker.value = false
}

// Переключение вкладок
function onSwitchTab(tab) {
  store.currentTab.value = tab
}

// Загружаем портфель при монтировании
onMounted(async () => {
  try {
    const data = await fetchPortfolio()
    store.portfolioData.value = data.projects || []
  } catch (e) {
    console.error('EnterpriseApp: ошибка загрузки портфеля', e)
  }
})
</script>
