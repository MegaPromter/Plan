<template>
  <!--
    PPStatsDropdown — выпадающее окно статистики ПП.
    Показывает: количество разработчиков, план/выполнено трудоёмкости.
    Порт из production_plan.js: togglePPStats().
  -->
  <span class="pp-stats-wrap" style="position: relative; display: inline-block;">
    <button
      class="btn btn-outline btn-sm"
      @click.stop="toggle"
    >
      <i class="fas fa-chart-pie" aria-hidden="true"></i> Статистика
    </button>
    <div
      v-show="open"
      ref="dropdownRef"
      class="pp-stats-dropdown open"
    >
      <div class="pp-stats-row">
        <span class="pp-stats-label">Разработчиков</span>
        <span class="pp-stats-val">{{ executorCount }}</span>
      </div>
      <div class="pp-stats-row">
        <span class="pp-stats-label">Трудоёмкость план / выполнено</span>
        <span class="pp-stats-val">{{ fmtLabor(totalLabor) }} / {{ fmtLabor(doneLabor) }}</span>
      </div>
    </div>
  </span>
</template>

<script setup>
/**
 * PPStatsDropdown — компактная статистика ПП-плана.
 *
 * Считает по ВСЕМ строкам проекта (без учёта фильтров):
 * - Количество уникальных разработчиков
 * - Общая трудоёмкость (план) и выполненная (has_reports)
 *
 * Закрывается при клике вне дропдауна.
 */
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'

// ── Store ───────────────────────────────────────────────────────────────
const store = inject(PP_STORE_KEY)

// ── Состояние ───────────────────────────────────────────────────────────
const open = ref(false)
const dropdownRef = ref(null)

// ── Вычисляемые свойства ────────────────────────────────────────────────

/** Количество уникальных разработчиков */
const executorCount = computed(() => {
  const executors = new Set()
  store.rows.value.forEach(r => {
    if (r.executor) executors.add(r.executor)
  })
  return executors.size
})

/** Общая трудоёмкость (план) */
const totalLabor = computed(() => {
  let total = 0
  store.rows.value.forEach(r => {
    const lab = parseFloat(r.labor)
    if (!isNaN(lab)) total += lab
  })
  return total
})

/** Выполненная трудоёмкость (строки с has_reports) */
const doneLabor = computed(() => {
  let done = 0
  store.rows.value.forEach(r => {
    const lab = parseFloat(r.labor)
    if (!isNaN(lab) && r.has_reports) done += lab
  })
  return done
})

// ── Утилиты ─────────────────────────────────────────────────────────────

/** Форматирование числа: целое без десятичных, иначе 2 знака */
function fmtLabor(val) {
  return val % 1 === 0 ? val : val.toFixed(2)
}

// ── Toggle / закрытие ───────────────────────────────────────────────────

function toggle() {
  open.value = !open.value
}

function onDocClick(e) {
  // Закрыть дропдаун если клик вне обёртки
  if (!e.target.closest('.pp-stats-wrap')) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))
</script>
