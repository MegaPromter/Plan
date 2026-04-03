<template>
  <!-- Модалка выбора проекта (общая для ГГ, Сквозного, Загрузки, Сценариев) -->
  <BaseModal :show="show" title="Выбор проекта" max-width="720px" @close="$emit('close')">
    <!-- Поиск -->
    <div class="picker-search" style="margin: -16px -16px 12px; padding: 12px 16px; border-bottom: 1px solid var(--border);">
      <input
        ref="searchInput"
        v-model="search"
        type="text"
        class="form-input"
        placeholder="Поиск по названию, коду или статусу..."
        autocomplete="off"
      >
    </div>

    <!-- Таблица проектов -->
    <div style="overflow-y: auto; max-height: 55vh; margin: 0 -16px; padding: 0;">
      <table v-if="filtered.length" class="picker-table">
        <thead>
          <tr>
            <th style="width:45px" @click="toggleSort('num')">
              № <span class="sort-arrow">{{ sortArrow('num') }}</span>
            </th>
            <th @click="toggleSort('name')">
              Название <span class="sort-arrow">{{ sortArrow('name') }}</span>
            </th>
            <th style="width:120px" @click="toggleSort('code')">
              Код <span class="sort-arrow">{{ sortArrow('code') }}</span>
            </th>
            <th style="width:130px" @click="toggleSort('status')">
              Статус <span class="sort-arrow">{{ sortArrow('status') }}</span>
            </th>
            <th style="width:120px" @click="toggleSort('priority')">
              Приоритет <span class="sort-arrow">{{ sortArrow('priority') }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(p, i) in filtered"
            :key="p.id"
            :class="{ 'picker-selected': p.id === currentProjectId }"
            @click="$emit('select', p.id)"
          >
            <td>{{ i + 1 }}</td>
            <td><strong>{{ p.name_short || p.name_full }}</strong></td>
            <td style="color:var(--muted)">{{ p.code || '' }}</td>
            <td><StatusBadge :status="p.status || ''" /></td>
            <td><PriorityBadge v-if="p.priority_category" :category="p.priority_category" /></td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state" style="padding:40px 20px;">
        <p>Ничего не найдено</p>
      </div>
    </div>

    <template #footer>
      <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
        <span class="picker-count">Найдено: {{ filtered.length }} из {{ projects.length }}</span>
        <div style="display:flex; gap:8px;">
          <button v-if="allowClear && currentProjectId" class="btn btn-secondary" @click="$emit('clear')">
            Сбросить
          </button>
          <button class="btn btn-secondary" @click="$emit('close')">Отмена</button>
        </div>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import BaseModal from '../BaseModal.vue'
import StatusBadge from '../StatusBadge.vue'
import PriorityBadge from '../PriorityBadge.vue'
import { STATUS_LABELS, PRIORITY_LABELS, PRIORITY_ORDER } from '../../constants/enterprise.js'

const props = defineProps({
  show:             { type: Boolean, required: true },
  projects:         { type: Array, default: () => [] },
  currentProjectId: { type: Number, default: null },
  allowClear:       { type: Boolean, default: false },
})

defineEmits(['select', 'clear', 'close'])

const search = ref('')
const sortCol = ref('priority')
const sortDir = ref('asc')
const searchInput = ref(null)

// Автофокус при открытии
watch(() => props.show, (val) => {
  if (val) {
    search.value = ''
    nextTick(() => searchInput.value?.focus())
  }
})

// Сортировка
function toggleSort(col) {
  if (sortCol.value === col) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortCol.value = col
    sortDir.value = 'asc'
  }
}

function sortArrow(col) {
  if (sortCol.value !== col) return ''
  return sortDir.value === 'asc' ? '\u25B2' : '\u25BC'
}

// Получение значения для сортировки — повторяет логику оригинального enterprise.js
function getSortVal(p, col) {
  if (col === 'num') return p.priority_number || 9999
  if (col === 'name') return (p.name_short || p.name_full || '').toLowerCase()
  if (col === 'code') return (p.code || '').toLowerCase()
  if (col === 'status') return STATUS_LABELS[p.status] || ''
  if (col === 'priority') return PRIORITY_ORDER[p.priority_category] ?? 99
  return ''
}

// Отфильтрованный и отсортированный список
const filtered = computed(() => {
  const q = search.value.toLowerCase()

  // Фильтрация по поисковому запросу
  let list = props.projects.filter(p => {
    if (!q) return true
    const text = [
      p.name_short || '',
      p.name_full || '',
      p.code || '',
      STATUS_LABELS[p.status] || '',
      PRIORITY_LABELS[p.priority_category] || '',
    ].join(' ').toLowerCase()
    return text.includes(q)
  })

  // Сортировка
  const dir = sortDir.value === 'asc' ? 1 : -1
  list = [...list].sort((a, b) => {
    const va = getSortVal(a, sortCol.value)
    const vb = getSortVal(b, sortCol.value)
    if (va < vb) return -1 * dir
    if (va > vb) return 1 * dir
    return 0
  })

  return list
})
</script>
