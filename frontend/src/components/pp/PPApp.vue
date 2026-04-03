<template>
  <!-- Кнопки topbar для лендинга -->
  <Teleport to="#pp-topbar-actions">
    <template v-if="store.currentView.value === 'landing'">
      <button
        v-if="store.isAdmin"
        class="btn btn-primary btn-sm"
        @click="openCreateProjectModal"
      >
        <i class="fas fa-plus" aria-hidden="true"></i> Создать новый производственный план
      </button>
    </template>
  </Teleport>

  <!-- Лендинг: сетка карточек ПП-проектов -->
  <div v-if="store.currentView.value === 'landing'" class="spa-fade-in">
    <div class="page-header">
      <h1>Производственный план</h1>
    </div>

    <div class="pp-projects-grid">
      <!-- Пустое состояние -->
      <div
        v-if="store.projects.value.length === 0"
        style="grid-column: 1 / -1;"
      >
        <div class="empty-state">
          <i class="fas fa-industry empty-state-icon"></i>
          <div class="empty-state-title">Производственных планов пока нет</div>
          <div class="empty-state-desc">
            Создайте первый план, чтобы начать управлять производством
          </div>
          <button
            v-if="store.isAdmin"
            class="btn btn-primary btn-sm"
            @click="openCreateProjectModal"
          >
            <i class="fas fa-plus"></i> Создать план
          </button>
        </div>
      </div>

      <!-- Карточки ПП-проектов -->
      <div
        v-for="p in store.projects.value"
        :key="p.id"
        class="pp-project-card"
        @click="openProject(p.id, p.name)"
      >
        <!-- Привязанный проект УП -->
        <div
          v-if="p.up_project_name"
          style="font-size: 11px; color: var(--accent); font-weight: 500; margin-bottom: 2px;"
        >
          <i class="fas fa-project-diagram" style="margin-right: 3px;"></i>
          {{ p.up_project_name }}
        </div>
        <!-- Привязанное изделие УП -->
        <div
          v-if="p.up_product_name"
          style="font-size: 11px; color: var(--success, #22c55e); font-weight: 500; margin-bottom: 4px;"
        >
          <i class="fas fa-cog" style="margin-right: 3px;"></i>
          {{ p.up_product_name }}
        </div>
        <!-- Название плана -->
        <div class="pp-project-card-name">
          {{ p.name || 'Без названия' }}
        </div>
        <!-- Количество строк -->
        <div class="pp-project-card-count">
          <i class="fas fa-list" style="margin-right: 4px;"></i>
          {{ p.row_count || 0 }} строк
        </div>
        <!-- Кнопки редактирования/удаления (только для администраторов) -->
        <div v-if="store.isAdmin" class="pp-project-card-actions">
          <button
            class="pp-card-btn"
            title="Переименовать"
            @click.stop="editProjectName(p)"
          >
            <i class="fas fa-pen"></i>
          </button>
          <button
            class="pp-card-btn danger"
            title="Удалить"
            @click.stop="deleteProjectConfirm(p)"
          >
            <i class="fas fa-trash"></i>
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Режим просмотра проекта -->
  <div v-if="store.currentView.value === 'project'" class="spa-fade-in">
    <!-- Тулбар: табы, фильтры, действия -->
    <PPToolbar
      :status-counts="statusCounts"
      @go-to-landing="goToLanding"
      @add-row="onAddRow"
      @sync="onSync"
      @toggle-bulk="onToggleBulk"
    />

    <!-- Таблица ПП -->
    <div v-show="store.viewMode.value === 'table'" id="ppTableView">
      <PPTable
        ref="ppTableRef"
        @open-deps="onOpenDeps"
        @delete-row="onDeleteRow"
      />
    </div>

    <!-- Диаграмма Ганта -->
    <PPGanttView
      v-show="store.viewMode.value === 'gantt'"
      :rows="store.rows.value"
      :active="store.viewMode.value === 'gantt'"
    />

    <!-- Плавающая панель массовых действий -->
    <PPBulkBar
      @delete-selected="onBulkDelete"
      @export-csv="onBulkExportCsv"
    />

    <!-- Модалка зависимостей -->
    <PPDepsModal
      :show="showDepsModal"
      :task-id="depsTaskId"
      :task-name="depsTaskName"
      :rows="store.rows.value"
      @close="showDepsModal = false"
      @updated="onDepsUpdated"
    />
  </div>

  <!-- Модалки создания/редактирования проекта -->
  <PPProjectCreateModal
    :show="showCreateModal"
    @close="showCreateModal = false"
    @created="onProjectCreated"
    @opened="onProjectOpened"
  />
  <PPProjectEditModal
    :show="showEditModal"
    :project="editingProject"
    @close="showEditModal = false"
    @saved="onProjectSaved"
  />
</template>

<script setup>
import { ref, provide, onMounted, onUnmounted, computed } from 'vue'
import { createPPStore, PP_STORE_KEY } from '../../stores/usePPStore.js'
import { getRowStatus } from '../../constants/pp.js'
import {
  fetchDirectories,
  fetchPPProjects,
  fetchPPRows,
  fetchProjectStages,
  deletePPProject as apiDeleteProject,
  deletePPRow,
  syncToTasks as apiSyncToTasks,
} from '../../api/pp.js'

// ── Дочерние компоненты ─────────────────────────────────────────────────
import PPToolbar from './PPToolbar.vue'
import PPTable from './PPTable.vue'
import PPGanttView from './PPGanttView.vue'
import PPBulkBar from './PPBulkBar.vue'
import PPDepsModal from './PPDepsModal.vue'
import PPProjectCreateModal from './PPProjectCreateModal.vue'
import PPProjectEditModal from './PPProjectEditModal.vue'

// ── Props ────────────────────────────────────────────────────────────────
const props = defineProps({
  config: { type: Object, default: () => ({}) },
})

// ── Создаём хранилище с конфигом из Django ──────────────────────────────
const store = createPPStore(props.config)

// Пробрасываем store дочерним компонентам
provide(PP_STORE_KEY, store)

// ── Refs для дочерних компонентов ───────────────────────────────────────
const ppTableRef = ref(null)

// ── Модалка зависимостей ────────────────────────────────────────────────
const showDepsModal = ref(false)
const depsTaskId = ref(null)
const depsTaskName = ref('')

// ── Модалка создания ПП-проекта ─────────────────────────────────────────
const showCreateModal = ref(false)

// ── Модалка редактирования ПП-проекта ───────────────────────────────────
const showEditModal = ref(false)
const editingProject = ref(null)

// ── Вычисляемые свойства ────────────────────────────────────────────────

/**
 * Подсчёт статусов для панели (без учёта статус-фильтра,
 * но с учётом колоночных фильтров — аналогично _ppRowsWithoutStatusFilter).
 */
const statusCounts = computed(() => {
  let done = 0, overdue = 0, inwork = 0
  const allRows = store.rows.value
  // Фильтрация по colFilters (без statusFilter)
  const filtered = allRows.filter(row => {
    for (const [col, val] of Object.entries(store.colFilters)) {
      if (col.startsWith('mf_')) {
        const field = col.slice(3)
        if (val.size > 0) {
          if (field === 'date_end' || field === 'date_start') {
            const cellVal = (row[field] || '').slice(0, 7)
            if (!val.has(cellVal)) return false
          } else if (field === 'pp_stage' || field === 'stage_num') {
            if (!val.has(row.pp_stage_name || '')) return false
          } else {
            if (!val.has(row[field] || '')) return false
          }
        }
      }
    }
    return true
  })
  filtered.forEach(row => {
    const s = getRowStatus(row)
    if (s === 'done') done++
    else if (s === 'overdue') overdue++
    else inwork++
  })
  return { total: filtered.length, done, overdue, inwork }
})

// ── Действия ────────────────────────────────────────────────────────────

/** Переключение статус-фильтра (toggle) */
function toggleStatus(status) {
  store.statusFilter.value =
    store.statusFilter.value === status ? 'all' : status
}

/**
 * Открыть конкретный ПП-проект (перейти к таблице).
 * Загружает строки плана и этапы привязанного проекта УП.
 */
async function openProject(id, name) {
  store.currentProjectId.value = id
  store.currentProjectName.value = name || ''
  store.currentView.value = 'project'
  store.viewMode.value = 'table'
  store.setProjectUrl(id)

  store.loading.value = true
  try {
    // Определяем ID привязанного проекта УП (для загрузки этапов)
    const projObj = store.projects.value.find(
      p => String(p.id) === String(id)
    )
    const upId = projObj && projObj.up_project_id

    // Параллельно загружаем строки и этапы
    const [rows, stages] = await Promise.all([
      fetchPPRows(id),
      upId ? fetchProjectStages(upId).catch(() => []) : Promise.resolve([]),
    ])
    store.rows.value = rows
    store.ppStages.value = stages

    // Восстанавливаем фильтры из URL
    store.restoreFiltersFromUrl()

    // Дефолтный фильтр по отделу (не-admin при первом открытии)
    const filterKey = 'pp_dept_filter_cleared_' + id
    const wasCleared = sessionStorage.getItem(filterKey)
    if (
      !store.isAdmin &&
      store.userDept &&
      !wasCleared &&
      !store.colFilters['mf_dept']
    ) {
      store.mfSelections['dept'] = new Set([store.userDept])
      store.colFilters['mf_dept'] = new Set([store.userDept])
    }
  } catch (e) {
    console.error('PPApp: ошибка загрузки проекта', e)
  } finally {
    store.loading.value = false
  }
}

/** Возврат на лендинг */
function goToLanding() {
  store.currentProjectId.value = null
  store.currentProjectName.value = ''
  store.currentView.value = 'landing'
  store.setProjectUrl(null)

  // Сброс фильтров проекта
  store.selectedMonth.value = null
  store.selectedYear.value = new Date().getFullYear()
  store.selectedDepts.clear()
  store.statusFilter.value = 'all'
}

// ── CRUD ПП-проектов ────────────────────────────────────────────────────

/** Открыть модальное окно создания нового ПП-плана */
function openCreateProjectModal() {
  showCreateModal.value = true
}

/** Редактировать название и привязку ПП-проекта */
function editProjectName(project) {
  editingProject.value = project
  showEditModal.value = true
}

/** Удалить ПП-проект с подтверждением */
async function deleteProjectConfirm(project) {
  if (!confirm(`Удалить план «${project.name || 'Без названия'}» и все его строки?`)) return
  try {
    await apiDeleteProject(project.id)
    store.projects.value = store.projects.value.filter(p => p.id !== project.id)
  } catch (e) {
    alert(e.error || 'Ошибка удаления')
  }
}

// ── Обработчики событий дочерних компонентов ────────────────────────────

/** Добавить строку — прокручивает к форме добавления в таблице */
function onAddRow() {
  if (ppTableRef.value && ppTableRef.value.showAddRow) {
    ppTableRef.value.showAddRow()
  }
}

/** Открыть модалку зависимостей для задачи */
function onOpenDeps({ taskId, taskName }) {
  depsTaskId.value = taskId
  depsTaskName.value = taskName || ''
  showDepsModal.value = true
}

/** Зависимости обновлены — перезагружаем строки */
async function onDepsUpdated() {
  if (store.currentProjectId.value) {
    try {
      const rows = await fetchPPRows(store.currentProjectId.value)
      store.rows.value = rows
    } catch (e) {
      console.error('PPApp: ошибка обновления строк после зависимостей', e)
    }
  }
}

/** Проект создан — обновляем список и открываем */
function onProjectCreated(project) {
  store.projects.value.push(project)
  showCreateModal.value = false
}

/** Проект открыт из модалки создания (выбрали существующий) */
function onProjectOpened(project) {
  showCreateModal.value = false
  openProject(project.id, project.name)
}

/** Проект отредактирован — обновляем в списке */
function onProjectSaved(updated) {
  if (updated && updated.id) {
    const idx = store.projects.value.findIndex(p => p.id === updated.id)
    if (idx >= 0) store.projects.value[idx] = { ...store.projects.value[idx], ...updated }
  }
  showEditModal.value = false
  editingProject.value = null
}

// ── Синхронизация, bulk, удаление строк ─────────────────────────────────

/** Синхронизация ПП → СП */
async function onSync() {
  if (!store.currentProjectId.value) return
  try {
    const ids = store.rows.value.map(r => r.id)
    await apiSyncToTasks({ project_id: store.currentProjectId.value, ids })
    alert('Синхронизация завершена')
  } catch (e) {
    alert(e.error || 'Ошибка синхронизации')
  }
}

/** Переключение bulk-режима */
function onToggleBulk() {
  store.bulkMode.value = !store.bulkMode.value
  if (!store.bulkMode.value) {
    store.bulkSelected.clear()
  }
}

/** Удалить одну строку ПП */
async function onDeleteRow(rowId) {
  if (!confirm('Удалить эту строку?')) return
  try {
    await deletePPRow(rowId)
    store.rows.value = store.rows.value.filter(r => r.id !== rowId)
  } catch (e) {
    alert(e.error || 'Ошибка удаления')
  }
}

/** Массовое удаление строк */
async function onBulkDelete(ids) {
  try {
    await Promise.all(ids.map(id => deletePPRow(id)))
    const idSet = new Set(ids)
    store.rows.value = store.rows.value.filter(r => !idSet.has(r.id))
    store.bulkSelected.clear()
  } catch (e) {
    alert(e.error || 'Ошибка массового удаления')
  }
}

/** Экспорт выделенных строк в CSV */
function onBulkExportCsv() {
  const ids = new Set(store.bulkSelected)
  const rows = store.rows.value.filter(r => ids.has(r.id))
  if (!rows.length) return
  // Формируем CSV
  const headers = ['ID', 'Код', 'Наряд-заказ', 'Наименование', 'Отдел', 'Начало', 'Окончание']
  const csvRows = rows.map(r =>
    [r.id, r.row_code || '', r.work_order || '', r.work_name || '', r.dept || '', r.date_start || '', r.date_end || '']
      .map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',')
  )
  const csv = [headers.join(','), ...csvRows].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'pp_export.csv'
  a.click()
  URL.revokeObjectURL(url)
}

// ── Навигация браузера (Назад/Вперёд) ──────────────────────────────────

function onPopState() {
  const pid = store.readProjectFromUrl()
  if (pid) {
    const proj = store.projects.value.find(
      p => String(p.id) === String(pid)
    )
    if (proj) {
      openProject(proj.id, proj.name)
    } else {
      goToLanding()
    }
  } else {
    goToLanding()
  }
}

onMounted(async () => {
  // Слушаем popstate для навигации Назад/Вперёд
  window.addEventListener('popstate', onPopState)

  store.loading.value = true
  try {
    // Параллельно загружаем справочники и список ПП-проектов
    const [dirs, projects] = await Promise.all([
      fetchDirectories(),
      fetchPPProjects(),
    ])
    store.dirs.value = dirs
    store.projects.value = projects

    // Если в URL есть project_id — открываем план напрямую (прямая ссылка)
    const urlProjectId = store.readProjectFromUrl()
    if (urlProjectId) {
      const proj = projects.find(
        p => String(p.id) === String(urlProjectId)
      )
      if (proj) {
        await openProject(proj.id, proj.name)
      }
      // Если ID не найден — остаёмся на лендинге (currentView уже 'landing')
    }
  } catch (e) {
    console.error('PPApp: ошибка инициализации', e)
  } finally {
    store.loading.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('popstate', onPopState)
})

// Экспортируем для дочерних компонентов через provide
// и для обратной совместимости с legacy-кодом
defineExpose({ store, openProject, goToLanding })
</script>
