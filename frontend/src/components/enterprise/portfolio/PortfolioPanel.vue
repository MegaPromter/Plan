<template>
  <!-- Панель «Портфель проектов» -->
  <div class="ent-panel">
    <!-- Тулбар -->
    <div class="ent-toolbar">
      <div class="ent-toolbar-left">
        <span
          v-if="hasActiveFilters"
          class="filters-active-badge"
          style="cursor:pointer;"
          title="Сбросить все фильтры"
          @click="clearAllFilters"
        >
          &#10005; Фильтры
        </span>
      </div>
      <div v-if="store.role === 'admin'" class="ent-toolbar-right">
        <button class="btn btn-primary btn-sm" @click="showCreateModal = true">
          <i class="fas fa-plus"></i> Создать проект
        </button>
      </div>
    </div>

    <!-- Справка -->
    <details class="ent-help">
      <summary class="ent-help-toggle">
        <i class="fas fa-info-circle"></i> Справка по параметрам проекта
      </summary>
      <div class="ent-help-body">
        <div class="ent-help-section">
          <div class="ent-help-title">Статус — текущее состояние проекта в жизненном цикле</div>
          <div class="ent-help-grid">
            <span class="status-badge status-badge--prospective">Перспективный</span><span>Проект на рассмотрении, решение о запуске не принято</span>
            <span class="status-badge status-badge--approved">Утверждён</span><span>Решение принято, ресурсы выделяются</span>
            <span class="status-badge status-badge--active">Активный</span><span>Работы ведутся по плану</span>
            <span class="status-badge status-badge--suspended">Приостановлен</span><span>Работы временно остановлены, проект возобновится</span>
            <span class="status-badge status-badge--deferred">Отложен</span><span>Запуск перенесён на неопределённый срок</span>
            <span class="status-badge status-badge--closed">Закрыт</span><span>Работы завершены, результат сдан</span>
            <span class="status-badge status-badge--cancelled">Отменён</span><span>Проект прекращён без результата</span>
          </div>
        </div>
        <div class="ent-help-section">
          <div class="ent-help-title">Приоритет — очерёдность выделения ресурсов</div>
          <div class="ent-help-grid">
            <span class="priority-badge priority-badge--critical">Критический</span><span>Срочный, ресурсы в первую очередь</span>
            <span class="priority-badge priority-badge--high">Высокий</span><span>Важный, ресурсы во вторую очередь</span>
            <span class="priority-badge priority-badge--medium">Средний</span><span>Плановый, стандартное распределение</span>
            <span class="priority-badge priority-badge--low">Низкий</span><span>Может ждать, ресурсы по остаточному принципу</span>
          </div>
          <div class="ent-help-note">
            Номер приоритета (1, 2, 3...) определяет порядок внутри категории.
            1 = самый важный. Проекты сортируются сначала по номеру, затем по наименованию.
          </div>
        </div>
      </div>
    </details>

    <!-- Таблица или пустое состояние -->
    <PortfolioTable
      v-if="sortedProjects.length"
      :projects="sortedProjects"
      :is-writer="store.isWriter"
      :sort-state="sort.state"
      :filters="mf.filters"
      :get-filter-values="getFilterValues"
      @sort="sort.toggle"
      @filter="onFilter"
      @clear-filter="mf.clearFilter"
      @edit-project="openEdit"
    />
    <div v-else class="empty-state">
      <i class="fas fa-folder-open"></i>
      <p>Нет проектов</p>
      <button
        v-if="store.role === 'admin'"
        class="btn btn-primary btn-sm"
        style="margin-top:8px;"
        @click="showCreateModal = true"
      >
        <i class="fas fa-plus"></i> Создать первый проект
      </button>
    </div>

    <!-- Модалка создания проекта -->
    <ProjectCreateModal
      :show="showCreateModal"
      :employees="store.employees.value"
      @close="showCreateModal = false"
      @saved="onProjectSaved"
    />

    <!-- Модалка редактирования проекта -->
    <ProjectEditModal
      :show="showEditModal"
      :project="editingProject"
      :employees="store.employees.value"
      @close="showEditModal = false"
      @saved="onProjectSaved"
    />
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'
import { ENTERPRISE_STORE_KEY } from '../../../stores/useEnterpriseStore.js'
import { STATUS_LABELS, PRIORITY_LABELS, PRIORITY_ORDER } from '../../../constants/enterprise.js'
import { useSort } from '../../../composables/useSort.js'
import { fetchPortfolio } from '../../../api/enterprise.js'
import PortfolioTable from './PortfolioTable.vue'
import ProjectCreateModal from './ProjectCreateModal.vue'
import ProjectEditModal from './ProjectEditModal.vue'

const store = inject(ENTERPRISE_STORE_KEY)

// ── Сортировка ──────────────────────────────────────────────────────────────
const sort = useSort()
// По умолчанию сортируем по приоритету
sort.state.col = 'priority'
sort.state.dir = 'asc'

// ── Мультифильтры ───────────────────────────────────────────────────────────
// Хранилище активных фильтров: { col: Set([values]) }
const mfFilters = ref({})
const mf = {
  filters: mfFilters,
  clearFilter(col) {
    const f = { ...mfFilters.value }
    delete f[col]
    mfFilters.value = f
  },
  clearAll() {
    mfFilters.value = {}
  },
}

const hasActiveFilters = computed(() => Object.keys(mfFilters.value).length > 0)

function clearAllFilters() {
  mf.clearAll()
}

// Извлечение значения столбца для фильтрации/сортировки
function getCellValue(p, col) {
  if (col === 'name') return p.name_full || p.name_short || ''
  if (col === 'code') return p.code || ''
  if (col === 'status') return STATUS_LABELS[p.status] || p.status || ''
  if (col === 'priority_category') return PRIORITY_LABELS[p.priority_category] || ''
  if (col === 'chief') return p.chief_designer ? p.chief_designer.name : ''
  return ''
}

// Уникальные значения для дропдаунов фильтров
function getFilterValues(col) {
  const vals = new Set()
  store.portfolioData.value.forEach(p => {
    const v = getCellValue(p, col)
    if (v) vals.add(v)
  })
  return [...vals].sort((a, b) => a.localeCompare(b, 'ru'))
}

// Применение фильтра из дропдауна
function onFilter(col, selectedSet) {
  const f = { ...mfFilters.value }
  if (!selectedSet || selectedSet.size === 0) {
    delete f[col]
  } else {
    f[col] = selectedSet
  }
  mfFilters.value = f
}

// Получение значения для сортировки — повторяет логику оригинального enterprise.js
function getSortVal(p, col) {
  if (col === 'name') return (p.name_full || p.name_short || '').toLowerCase()
  if (col === 'code') return (p.code || '').toLowerCase()
  if (col === 'status') return STATUS_LABELS[p.status] || p.status || ''
  if (col === 'priority') {
    // Сначала по категории (critical=0..low=3), потом по номеру
    const cat = PRIORITY_ORDER[p.priority_category] != null ? PRIORITY_ORDER[p.priority_category] : 99
    const num = p.priority_number != null ? p.priority_number : 9999
    return cat * 10000 + num
  }
  if (col === 'chief') return p.chief_designer ? p.chief_designer.name.toLowerCase() : ''
  if (col === 'pp_count') return p.pp_count || 0
  if (col === 'sp_count') return p.sp_count || 0
  if (col === 'labor_total') return p.labor_total || 0
  return ''
}

// Отфильтрованные + отсортированные проекты
const sortedProjects = computed(() => {
  // Фильтрация
  let list = store.portfolioData.value.filter(p => {
    for (const [col, sel] of Object.entries(mfFilters.value)) {
      if (!sel || sel.size === 0) continue
      const v = getCellValue(p, col)
      if (!sel.has(v)) return false
    }
    return true
  })

  // Сортировка
  list = sort.applySortToArray(list, getSortVal)

  return list
})

// ── Модалки ─────────────────────────────────────────────────────────────────
const showCreateModal = ref(false)
const showEditModal = ref(false)
const editingProject = ref(null)

function openEdit(id) {
  const p = store.portfolioData.value.find(x => x.id === id)
  if (!p) return
  editingProject.value = p
  showEditModal.value = true
}

// Перезагрузка портфеля после создания/редактирования
async function onProjectSaved() {
  showCreateModal.value = false
  showEditModal.value = false
  try {
    const data = await fetchPortfolio()
    store.portfolioData.value = data.projects || []
  } catch (e) {
    console.error('PortfolioPanel: ошибка перезагрузки портфеля', e)
  }
}
</script>
