<template>
  <!-- Панель фильтра по периоду: год с навигацией + 12 кнопок месяцев -->
  <div class="pp-period-bar">
    <span class="pp-cal-label">Период:</span>

    <!-- Блок выбора года: стрелки ‹ › вокруг числа -->
    <div class="pp-cal-block">
      <button class="pp-cal-nav" @click="changeYear(-1)">&lsaquo;</button>
      <div class="pp-cal-display">{{ store.selectedYear.value }}</div>
      <button class="pp-cal-nav" @click="changeYear(1)">&rsaquo;</button>
    </div>

    <!-- 12 кнопок месяцев -->
    <div class="pp-cal-months">
      <span
        v-for="(name, idx) in MONTH_NAMES_SHORT"
        :key="idx"
        class="pp-cal-month"
        :class="{ active: store.selectedMonth.value === idx + 1 }"
        @click="selectMonth(idx + 1)"
      >{{ name }}</span>
    </div>

    <!-- Кнопка сброса периода -->
    <span class="pp-cal-clear" @click="clearPeriod">Показать все</span>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'
import { MONTH_NAMES_SHORT } from '../../constants/pp.js'

const store = inject(PP_STORE_KEY)

const emit = defineEmits(['change'])

/** Переключить год на delta (+1 / -1) */
function changeYear(delta) {
  store.selectedYear.value += delta
  emit('change')
}

/**
 * Выбрать/отменить месяц.
 * Повторный клик по активному месяцу — сброс (null = все месяцы).
 */
function selectMonth(month) {
  store.selectedMonth.value =
    store.selectedMonth.value === month ? null : month
  emit('change')
}

/** Сбросить фильтр периода */
function clearPeriod() {
  store.selectedMonth.value = null
  store.selectedYear.value = new Date().getFullYear()
  emit('change')
}
</script>
