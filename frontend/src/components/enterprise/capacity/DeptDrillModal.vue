<template>
  <!-- Помесячная детализация загрузки отдела -->
  <BaseModal
    :show="show"
    :title="(department?.department_name || '') + ' \u2014 помесячная загрузка'"
    max-width="950px"
    @close="$emit('close')"
  >
    <template v-if="department">
      <!-- KPI отдела -->
      <div class="cap-kpi-row" style="margin-bottom:16px;">
        <div class="cap-kpi">
          <span class="cap-kpi-label">Численность</span>
          <span class="cap-kpi-value">{{ department.headcount }}</span>
        </div>
        <div class="cap-kpi">
          <span class="cap-kpi-label">Мощность (год)</span>
          <span class="cap-kpi-value">{{ fmtNum(department.capacity_hours) }} ч</span>
        </div>
        <div class="cap-kpi">
          <span class="cap-kpi-label">Потребность (год)</span>
          <span class="cap-kpi-value">{{ fmtNum(department.demand_hours) }} ч</span>
        </div>
        <div class="cap-kpi">
          <span class="cap-kpi-label">Загрузка</span>
          <span class="cap-kpi-value" :class="'cap-kpi-value--' + department.level">
            {{ department.loading_pct }}%
          </span>
        </div>
        <div class="cap-kpi">
          <span class="cap-kpi-label">Баланс</span>
          <span class="cap-kpi-value" v-html="balanceHtml"></span>
        </div>
      </div>

      <!-- Переключатель: Таблица / График -->
      <div class="cap-drill-toggle" style="margin-bottom:12px;">
        <button
          class="btn btn-sm btn-outline"
          :class="{ active: view === 'table' }"
          @click="view = 'table'"
        >
          <i class="fas fa-table"></i> Таблица
        </button>
        <button
          class="btn btn-sm btn-outline"
          :class="{ active: view === 'chart' }"
          @click="view = 'chart'"
        >
          <i class="fas fa-chart-bar"></i> График
        </button>
      </div>

      <!-- Таблица -->
      <div v-show="view === 'table'">
        <table class="cap-table" style="width:100%;">
          <thead>
            <tr>
              <th style="text-align:left;">Месяц</th>
              <th style="width:140px;">Мощность, ч</th>
              <th style="width:140px;">Потребн., ч</th>
              <th style="width:200px;">Загрузка</th>
              <th style="width:120px;">Баланс</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in monthly" :key="m.month" :class="m.level === 'overload' ? 'cap-month-over' : ''">
              <td style="text-align:left; font-weight:500;">{{ MONTH_NAMES[m.month - 1] }}</td>
              <td>{{ fmtNum(m.capacity) }}</td>
              <td>{{ fmtNum(m.demand) }}</td>
              <td>
                <div class="capacity-cell">
                  <div class="loading-bar" style="width:80px;">
                    <div
                      class="loading-bar-fill"
                      :class="'loading-bar-fill--' + m.level"
                      :style="{ width: Math.min(m.loading_pct, 150) + '%' }"
                    ></div>
                  </div>
                  <span class="capacity-pct" :class="'capacity-pct--' + m.level">
                    {{ m.loading_pct }}%
                  </span>
                </div>
              </td>
              <td v-html="balanceCell(m.balance)"></td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- График (Chart.js canvas) -->
      <div v-show="view === 'chart'" style="position:relative; height:320px;">
        <canvas ref="chartCanvas"></canvas>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * DeptDrillModal.vue — помесячная детализация загрузки отдела.
 * Два режима: таблица и Chart.js график (bar+line).
 */
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { MONTH_NAMES } from '../../../constants/enterprise.js'
import BaseModal from '../../BaseModal.vue'

const props = defineProps({
  show:       { type: Boolean, required: true },
  department: { type: Object, default: null },
})

defineEmits(['close'])

const view = ref('table')
const chartCanvas = ref(null)
let chartInstance = null

const monthly = computed(() => props.department?.monthly || [])

// Баланс год (HTML)
const balanceHtml = computed(() => {
  if (!props.department) return '\u2014'
  const b = props.department.capacity_hours - props.department.demand_hours
  return b >= 0
    ? `<span style="color:var(--success)">+${fmtNum(b)} ч</span>`
    : `<span style="color:var(--danger)">${fmtNum(b)} ч</span>`
})

/** Форматирование баланса месяца (HTML) */
function balanceCell(bal) {
  return bal >= 0
    ? `<span style="color:var(--success)">+${fmtNum(bal)}</span>`
    : `<span style="color:var(--danger);font-weight:600">${fmtNum(bal)}</span>`
}

function fmtNum(n) {
  return (n || 0).toLocaleString('ru-RU')
}

// Сброс вида при открытии
watch(() => props.show, (v) => {
  if (v) view.value = 'table'
})

// Рендер графика при переключении на chart
watch(view, async (v) => {
  if (v === 'chart') {
    await nextTick()
    renderChart()
  }
})

function renderChart() {
  if (!chartCanvas.value || !monthly.value.length) return

  // Динамический импорт Chart.js (должен быть доступен глобально или через CDN)
  if (typeof Chart === 'undefined') {
    console.warn('DeptDrillModal: Chart.js не загружен')
    return
  }

  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }

  const labels = monthly.value.map(m => MONTH_NAMES[m.month - 1].slice(0, 3))
  const demands = monthly.value.map(m => m.demand)
  const capacities = monthly.value.map(m => m.capacity)

  chartInstance = new Chart(chartCanvas.value, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Потребн. (ч)',
          data: demands,
          backgroundColor: 'rgba(59,130,246,0.5)',
          borderColor: 'rgba(59,130,246,0.8)',
          borderWidth: 1,
          borderRadius: 3,
          order: 2,
        },
        {
          label: 'Мощность (ч)',
          data: capacities,
          type: 'line',
          borderColor: '#dc2626',
          backgroundColor: 'transparent',
          borderWidth: 2,
          borderDash: [6, 3],
          pointBackgroundColor: '#dc2626',
          pointRadius: 4,
          tension: 0.1,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { usePointStyle: true, font: { size: 13 } } },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString('ru-RU')} ч`,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { callback: v => v.toLocaleString('ru-RU') },
          title: { display: true, text: 'Часы', font: { size: 12 } },
        },
        x: { grid: { display: false } },
      },
    },
  })
}

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }
})
</script>
