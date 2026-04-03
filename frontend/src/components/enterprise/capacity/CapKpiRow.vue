<template>
  <!-- Строка KPI-карточек загрузки/мощности -->
  <div class="cap-kpi-row">
    <div class="cap-kpi">
      <span class="cap-kpi-label">Сотрудников</span>
      <span class="cap-kpi-value">{{ totalHead }}</span>
      <span class="cap-kpi-sub">в {{ departments.length }} отд.</span>
    </div>
    <div class="cap-kpi">
      <span class="cap-kpi-label">Мощность</span>
      <span class="cap-kpi-value">{{ fmtNum(totalCap) }} ч</span>
    </div>
    <div class="cap-kpi">
      <span class="cap-kpi-label">Потребность</span>
      <span class="cap-kpi-value">{{ fmtNum(totalDem) }} ч</span>
    </div>
    <div class="cap-kpi">
      <span class="cap-kpi-label">Загрузка</span>
      <span class="cap-kpi-value" :class="'cap-kpi-value--' + level">{{ avgPct.toFixed(1) }}%</span>
    </div>
    <div class="cap-kpi">
      <span class="cap-kpi-label">Перегрузка</span>
      <span class="cap-kpi-value" :class="overloaded ? 'cap-kpi-value--overload' : ''">{{ overloaded }}</span>
      <span class="cap-kpi-sub">из {{ departments.length }}</span>
    </div>
  </div>
</template>

<script setup>
/**
 * CapKpiRow.vue — строка KPI-карточек для панели загрузки.
 * Показывает сводку: сотрудники, мощность, потребность, % загрузки, перегрузка.
 */
import { computed } from 'vue'

const props = defineProps({
  departments: { type: Array, default: () => [] },
})

const totalHead = computed(() => props.departments.reduce((s, d) => s + d.headcount, 0))
const totalCap = computed(() => props.departments.reduce((s, d) => s + d.capacity_hours, 0))
const totalDem = computed(() => props.departments.reduce((s, d) => s + d.demand_hours, 0))
const avgPct = computed(() => totalCap.value > 0 ? (totalDem.value / totalCap.value * 100) : 0)
const overloaded = computed(() => props.departments.filter(d => d.level === 'overload').length)

const level = computed(() => {
  const p = avgPct.value
  if (p < 60) return 'low'
  if (p < 80) return 'normal'
  if (p <= 100) return 'high'
  return 'overload'
})

function fmtNum(n) {
  return n.toLocaleString('ru-RU')
}
</script>
