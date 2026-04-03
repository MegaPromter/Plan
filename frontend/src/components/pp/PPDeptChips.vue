<template>
  <!-- Панель чипов отделов: фильтрация по отделу через клик по чипу -->
  <div class="pp-dept-bar">
    <span style="font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;">
      Отдел:
    </span>
    <div style="display:flex;gap:4px;flex-wrap:wrap;">
      <!-- Чип «Все» — сброс фильтра по отделам -->
      <span
        class="pp-dept-chip"
        :class="{ active: store.selectedDepts.size === 0 }"
        @click="selectAll"
      >Все</span>

      <!-- Чипы для каждого отдела, встречающегося в строках -->
      <span
        v-for="dept in availableDepts"
        :key="dept"
        class="pp-dept-chip"
        :class="{ active: store.selectedDepts.has(dept) }"
        @click="toggleDept(dept)"
      >{{ dept }}</span>
    </div>
  </div>
</template>

<script setup>
import { inject, computed } from 'vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'

const store = inject(PP_STORE_KEY)

const emit = defineEmits(['change'])

/** Собираем уникальные отделы из всех строк (сортировка по алфавиту) */
const availableDepts = computed(() => {
  const depts = new Set()
  store.rows.value.forEach(row => {
    if (row.dept) depts.add(row.dept)
  })
  return [...depts].sort((a, b) => a.localeCompare(b, 'ru'))
})

/** Переключить выбор конкретного отдела */
function toggleDept(dept) {
  if (store.selectedDepts.has(dept)) {
    store.selectedDepts.delete(dept)
  } else {
    store.selectedDepts.add(dept)
  }
  emit('change')
}

/** Показать все отделы (сброс) */
function selectAll() {
  store.selectedDepts.clear()
  emit('change')
}
</script>
