<template>
  <!-- Панель «Загрузка / Мощность» -->
  <div class="ent-panel">
    <!-- Тулбар: год, режим, проект -->
    <div class="ent-toolbar">
      <div class="ent-toolbar-left">
        <select v-model="store.capacityYear.value" class="form-select form-select-sm" @change="loadData">
          <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
        </select>
        <select v-model="store.capacityMode.value" class="form-select form-select-sm" @change="loadData">
          <option value="actual">Фактическая численность</option>
          <option value="staff">Штатная численность</option>
        </select>
        <button class="project-picker-btn" @click="$emit('open-project-picker')">
          <i class="fas fa-folder-open"></i>
          <span class="picker-label">{{ projectLabel }}</span>
        </button>
      </div>
    </div>

    <!-- Фильтр по НТЦ-центрам (чипы) -->
    <div v-if="centers.length" class="cap-chips">
      <button
        class="cap-chip"
        :class="{ active: !store.capacityFilterCenter.value }"
        @click="setFilter(null)"
      >Все</button>
      <button
        v-for="c in centers"
        :key="c.center_id"
        class="cap-chip"
        :class="{ active: store.capacityFilterCenter.value === c.center_id }"
        @click="setFilter(c.center_id)"
      >{{ c.center_name }}</button>
    </div>

    <!-- KPI карточки -->
    <CapKpiRow :departments="allFilteredDepts" />

    <!-- Карточки центров -->
    <div v-if="filteredCenters.length || filteredNoCenterDepts.length">
      <CapCenterCard
        v-for="c in filteredCenters"
        :key="c.center_id"
        :center="c"
        @drill="openDrill"
      />
      <CapCenterCard
        v-if="filteredNoCenterDepts.length"
        :center="{ center_name: 'Без НТЦ-центра', departments: filteredNoCenterDepts }"
        @drill="openDrill"
      />
    </div>
    <div v-else class="empty-state">
      <p>Нет данных о загрузке</p>
    </div>

    <!-- Детализация по отделу -->
    <DeptDrillModal
      :show="showDrill"
      :department="drillDept"
      @close="showDrill = false"
    />
  </div>
</template>

<script setup>
/**
 * CapacityPanel.vue — панель загрузки/мощности.
 * Отображает KPI, карточки НТЦ-центров с отделами, фильтрацию и drill-down.
 */
import { ref, computed, inject, onMounted, watch } from 'vue'
import { ENTERPRISE_STORE_KEY } from '../../../stores/useEnterpriseStore.js'
import { fetchCapacity } from '../../../api/enterprise.js'
import CapKpiRow from './CapKpiRow.vue'
import CapCenterCard from './CapCenterCard.vue'
import DeptDrillModal from './DeptDrillModal.vue'

const store = inject(ENTERPRISE_STORE_KEY)

defineEmits(['open-project-picker'])

// ── Состояние ──────────────────────────────────────────────────────────
const showDrill = ref(false)
const drillDept = ref(null)

// Годы для выбора (текущий +/- 2)
const currentYear = new Date().getFullYear()
const years = [currentYear - 2, currentYear - 1, currentYear, currentYear + 1, currentYear + 2]

// ── Вычисляемые ────────────────────────────────────────────────────────

const projectLabel = computed(() => {
  if (!store.capacityProjectId.value) return 'Все проекты'
  const p = store.projectsList.value.find(x => x.id === store.capacityProjectId.value)
  return p ? (p.name_short || p.name_full) : 'Проект'
})

const centers = computed(() => store.capacityData.value.centers || [])
const noCenterDepts = computed(() => store.capacityData.value.no_center_departments || [])

/** Отфильтрованные центры */
const filteredCenters = computed(() => {
  const f = store.capacityFilterCenter.value
  return f ? centers.value.filter(c => c.center_id === f) : centers.value
})

/** Отделы без центра (показываем только если нет фильтра) */
const filteredNoCenterDepts = computed(() => {
  return store.capacityFilterCenter.value ? [] : noCenterDepts.value
})

/** Все отделы для KPI (после фильтрации) */
const allFilteredDepts = computed(() => {
  return filteredCenters.value.flatMap(c => c.departments).concat(filteredNoCenterDepts.value)
})

// ── Загрузка данных ────────────────────────────────────────────────────

async function loadData() {
  try {
    const data = await fetchCapacity({
      year: store.capacityYear.value,
      mode: store.capacityMode.value,
      project_id: store.capacityProjectId.value || undefined,
    })
    store.capacityData.value = data
  } catch (e) {
    console.error('CapacityPanel: loadCapacity error', e)
  }
}

// Перезагрузка при смене проекта загрузки
watch(() => store.capacityProjectId.value, () => loadData())

onMounted(() => loadData())

// ── Методы ─────────────────────────────────────────────────────────────

function setFilter(centerId) {
  store.capacityFilterCenter.value = store.capacityFilterCenter.value === centerId ? null : centerId
}

function openDrill(deptId) {
  const allDepts = centers.value.flatMap(c => c.departments).concat(noCenterDepts.value)
  const dept = allDepts.find(d => d.department_id === deptId)
  if (!dept || !dept.monthly) return
  drillDept.value = dept
  showDrill.value = true
}
</script>
