<template>
  <!--
    PPToolbar — тулбар режима просмотра ПП-проекта.
    Объединяет: панель периода, чипы отделов, переключатель вида (таблица/Гант),
    статус-панель, статистику, bulk-mode, добавление строки, синхронизацию, сброс фильтров.
    Порт из production_plan_spa.html: #projectActions, #ppPeriodBar, #ppDeptBar, #ppViewTabs.
  -->
  <!-- ── Кнопки действий → Teleport в topbar шапки ──────────────────── -->
  <Teleport to="#pp-topbar-actions">
    <!-- Возврат к списку планов -->
    <button class="btn btn-outline btn-sm" @click="$emit('goToLanding')">
      <i class="fas fa-arrow-left" aria-hidden="true"></i> Все планы
    </button>

    <!-- Синхронизация ПП -> СП -->
    <button class="btn btn-secondary btn-sm" @click="$emit('sync')">
      <i class="fas fa-sync-alt" aria-hidden="true"></i> Синхронизировать с СП
    </button>

    <!-- Добавить строку (только writer) -->
    <button
      v-if="store.isWriter"
      class="btn btn-primary btn-sm"
      @click="$emit('addRow')"
    >
      <i class="fas fa-plus" aria-hidden="true"></i> Добавить строку
    </button>

    <!-- Массовое выделение (только writer) -->
    <button
      v-if="store.isWriter"
      class="btn btn-outline btn-sm"
      :class="{ active: store.bulkMode.value }"
      @click="$emit('toggleBulk')"
    >
      <i class="far fa-check-square" aria-hidden="true"></i> Масс. выд.
    </button>

    <!-- Статистика -->
    <PPStatsDropdown />

    <!-- Кнопка сброса фильтров (показывается если есть активные) -->
    <button
      v-if="store.hasActiveFilters.value"
      class="btn btn-outline btn-sm"
      @click="store.clearAllFilters()"
    >
      <i class="fas fa-times" aria-hidden="true"></i> Сбросить фильтры
      <span style="margin-left: 6px; opacity: 0.7; font-size: 12px;">
        ({{ filteredCount }})
      </span>
    </button>

    <!-- Счётчик строк (если нет активных фильтров) -->
    <span
      v-if="!store.hasActiveFilters.value && store.rows.value.length > 0"
      style="font-size: 12px; color: var(--muted); margin-left: 4px;"
    >
      {{ store.rows.value.length }} строк
    </span>
  </Teleport>

  <div class="pp-toolbar">
    <!-- ── Панель периода (год + месяцы) ──────────────────────────────── -->
    <PPPeriodBar
      v-if="store.rows.value.length > 0"
      @change="onPeriodChange"
    />

    <!-- ── Чипы отделов ──────────────────────────────────────────────── -->
    <PPDeptChips
      v-if="store.rows.value.length > 0"
    />

    <!-- ── Переключатель вида + статус-панель + масштаб Ганта ─────────── -->
    <div class="pp-view-tabs">
      <!-- Вкладки: Таблица / Диаграмма Ганта -->
      <button
        class="pp-view-tab"
        :class="{ active: store.viewMode.value === 'table' }"
        @click="store.viewMode.value = 'table'"
      >
        Таблица
      </button>
      <button
        class="pp-view-tab"
        :class="{ active: store.viewMode.value === 'gantt' }"
        @click="store.viewMode.value = 'gantt'"
      >
        Диаграмма Ганта
      </button>

      <!-- Статус-панель (всегда видна, если есть строки) -->
      <PPStatusPanel
        v-if="store.rows.value.length > 0"
        :counts="statusCounts"
      />

      <!-- Переключатель плотности (компактно / нормально / все колонки) -->
      <div class="density-toggle" style="margin-left: auto;">
        <button
          :class="{ active: store.columnViewMode.value === 'compact' }"
          title="Компактно (10 колонок)"
          @click="setColumnView('compact')"
        >
          <i class="fas fa-compress-alt"></i>
        </button>
        <button
          :class="{ active: store.columnViewMode.value === 'normal' }"
          title="Обычно (15 колонок)"
          @click="setColumnView('normal')"
        >
          <i class="fas fa-bars"></i>
        </button>
        <button
          :class="{ active: store.columnViewMode.value === 'full' }"
          title="Все колонки"
          @click="setColumnView('full')"
        >
          <i class="fas fa-expand-alt"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * PPToolbar — тулбар проекта ПП.
 *
 * Объединяет все элементы управления из верхней части страницы:
 * - Кнопки действий (назад, синхронизация, добавление строки, bulk)
 * - Панель периода (PPPeriodBar)
 * - Чипы отделов (PPDeptChips)
 * - Переключатель вида (таблица / Гант) с масштабом
 * - Статус-панель (PPStatusPanel)
 * - Статистика (PPStatsDropdown)
 * - Переключатель плотности столбцов
 *
 * Props:
 *   filteredCount — количество строк после фильтрации
 *   currentGanttScale — текущий масштаб Ганта
 */
import { inject } from 'vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'
import PPPeriodBar from './PPPeriodBar.vue'
import PPDeptChips from './PPDeptChips.vue'
import PPStatusPanel from './PPStatusPanel.vue'
import PPStatsDropdown from './PPStatsDropdown.vue'

// ── Props / Emits ───────────────────────────────────────────────────────
const props = defineProps({
  /** Подсчёт статусов: { total, done, overdue, inwork } */
  statusCounts: { type: Object, default: () => ({ total: 0, done: 0, overdue: 0, inwork: 0 }) },
  /** Количество строк после фильтрации (для бейджа сброса) */
  filteredCount: { type: Number, default: 0 },
})

const emit = defineEmits([
  'goToLanding',
  'sync',
  'addRow',
  'toggleBulk',
  'columnViewChange',
])

// ── Store ───────────────────────────────────────────────────────────────
const store = inject(PP_STORE_KEY)

// ── Обработчики ─────────────────────────────────────────────────────────

/** Переключение режима плотности столбцов */
function setColumnView(mode) {
  store.columnViewMode.value = mode
  emit('columnViewChange', mode)
  // Сохраняем на сервер
  fetch('/api/col_settings/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
    },
    body: JSON.stringify({ pp_view_mode: mode }),
  }).catch(() => {})
}

/** Обработчик изменения периода */
function onPeriodChange() {
  // Обновляем URL-параметры
  store.syncFiltersToUrl()
}
</script>

<style>
/* Глобальный стиль — Teleport рендерит вне scoped-области */
#pp-topbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
</style>

<style scoped>
.pp-toolbar {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.pp-view-tabs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
</style>
