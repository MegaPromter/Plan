<template>
  <!-- Статус-панель: четыре компактных pill-кнопки (Все / Выполнено / Просрочено / В работе) -->
  <div v-if="counts.total > 0" class="status-pills">
    <button
      class="sp sp-all"
      :class="{ active: store.statusFilter.value === 'all' }"
      @click="toggle('all')"
    >
      Все <span class="num">{{ counts.total }}</span>
    </button>
    <button
      class="sp sp-done"
      :class="{ active: store.statusFilter.value === 'done' }"
      @click="toggle('done')"
    >
      &#x2713; <span class="num">{{ counts.done }}</span>
    </button>
    <button
      class="sp sp-overdue"
      :class="{ active: store.statusFilter.value === 'overdue' }"
      @click="toggle('overdue')"
    >
      &#x26A0; <span class="num">{{ counts.overdue }}</span>
    </button>
    <button
      class="sp sp-inwork"
      :class="{ active: store.statusFilter.value === 'inwork' }"
      @click="toggle('inwork')"
    >
      &#x27F3; <span class="num">{{ counts.inwork }}</span>
    </button>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'

const props = defineProps({
  /**
   * Подсчёт статусов. Передаётся из родителя, чтобы учитывать
   * colFilters (без statusFilter) — аналогично _ppRowsWithoutStatusFilter().
   * Формат: { total, done, overdue, inwork }
   */
  counts: { type: Object, required: true },
})

const store = inject(PP_STORE_KEY)

/** Toggle: повторный клик на активный статус — возврат к 'all' */
function toggle(status) {
  store.statusFilter.value =
    store.statusFilter.value === status ? 'all' : status
}
</script>
