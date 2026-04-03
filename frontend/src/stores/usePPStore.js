/**
 * Хранилище состояния модуля «Производственный план».
 *
 * Использует Vue 3 Composition API (reactive/ref/computed).
 * Создаётся один раз в корневом компоненте PPApp и пробрасывается
 * дочерним через provide/inject.
 *
 * @param {Object} config — конфигурация из Django #pp-config JSON:
 *   - isWriter: boolean — может ли редактировать
 *   - isAdmin: boolean — администратор
 *   - canApprove: boolean — может утверждать наборы (песочница)
 *   - userRole: строка роли (admin/dept_head/sector_head/...)
 *   - userDept: код отдела пользователя
 *   - userSector: код сектора пользователя
 *   - userSectorName: имя сектора пользователя
 *   - userCenter: код НТЦ-подразделения пользователя
 *   - colSettings: настройки столбцов из профиля
 */
import { ref, computed, reactive } from 'vue'

export const PP_STORE_KEY = Symbol('ppStore')

export function createPPStore(config = {}) {
  // ── Пользователь ──────────────────────────────────────────────────────
  const isWriter = !!config.isWriter
  const isAdmin = !!config.isAdmin
  const canApprove = !!config.canApprove
  const userRole = config.userRole || ''
  const userDept = config.userDept || ''
  const userSector = config.userSector || ''
  const userSectorName = config.userSectorName || ''
  const userCenter = config.userCenter || ''
  const colSettings = ref(config.colSettings || {})

  // ── ПП-проекты (лендинг) ───────────────────────────────────────────────
  const projects = ref([])
  const currentProjectId = ref(null)
  const currentProjectName = ref('')

  // ── Строки текущего ПП-плана ───────────────────────────────────────────
  const rows = ref([])

  // ── Справочные данные (dirs) ───────────────────────────────────────────
  // Объект вида: { dept: [...], center: [...], employees: [...],
  //                sector_head: [...], task_type: [...], ... }
  const dirs = ref({})

  // ── Этапы ПП текущего проекта (из ЕТБД / PPStage) ─────────────────────
  const ppStages = ref([])

  // ── Проекты УП (для привязки при создании/редактировании) ──────────────
  const upProjects = ref([])

  // ── Текущий вид ────────────────────────────────────────────────────────
  // 'landing' — сетка карточек ПП-проектов
  // 'project' — таблица строк конкретного ПП-плана
  const currentView = ref('landing')

  // 'table' | 'gantt' — режим отображения внутри проекта
  const viewMode = ref('table')

  // Режим отображения столбцов (compact/normal/full)
  const columnViewMode = ref(
    (config.colSettings && config.colSettings.pp_view_mode) || 'full'
  )

  // ── Фильтрация ────────────────────────────────────────────────────────
  // Активные колоночные фильтры: { 'mf_dept': Set([...]), 'mf_date_end': Set([...]) }
  const colFilters = reactive({})
  // Текущие выборки в дропдаунах мультифильтров: { 'dept': Set([...]) }
  const mfSelections = reactive({})

  // Статус-фильтр: 'all' | 'done' | 'overdue' | 'inwork'
  const statusFilter = ref('all')

  // Фильтр по периоду (год + месяц)
  const selectedYear = ref(new Date().getFullYear())
  const selectedMonth = ref(null) // null = все месяцы

  // Фильтр по отделам (мульти-чипы)
  const selectedDepts = reactive(new Set())

  // ── Сортировка ────────────────────────────────────────────────────────
  const sortState = reactive({ col: null, dir: 'asc' })

  // ── Массовое выделение (bulk mode) ────────────────────────────────────
  const bulkMode = ref(false)
  const bulkSelected = reactive(new Set())

  // ── Загрузка ──────────────────────────────────────────────────────────
  const loading = ref(false)

  // ── Вычисляемые свойства ──────────────────────────────────────────────

  /** Есть ли хотя бы один активный фильтр */
  const hasActiveFilters = computed(() => Object.keys(colFilters).length > 0)

  /** Текущий объект ПП-проекта (из списка проектов) */
  const currentProject = computed(() => {
    if (!currentProjectId.value) return null
    return projects.value.find(
      p => String(p.id) === String(currentProjectId.value)
    ) || null
  })

  /**
   * Проверяет, может ли текущий пользователь редактировать строку ПП.
   * Логика аналогична makeCanModify() из utils.js.
   * @param {string} rowDept — код отдела строки
   * @param {string} rowSector — код сектора строки
   * @returns {boolean}
   */
  function canModifyRow(rowDept, rowSector) {
    if (!isWriter) return false
    if (isAdmin) return true
    // ntc_head / ntc_deputy — редактируют всё
    if (userRole === 'ntc_head' || userRole === 'ntc_deputy') return true
    // dept_head / dept_deputy — только свой отдел
    if (userRole === 'dept_head' || userRole === 'dept_deputy') {
      return !rowDept || rowDept === userDept
    }
    // sector_head — только свой отдел и свой сектор
    if (userRole === 'sector_head') {
      if (rowDept && rowDept !== userDept) return false
      if (rowSector && rowSector !== userSector && rowSector !== userSectorName) return false
      return true
    }
    // chief_designer — редактируют (как writer)
    if (userRole === 'chief_designer') return true
    return false
  }

  /**
   * Формирует стандартное название ПП:
   * "Производственный план подразделения НТЦ-XX по проекту/изделию ..."
   * @param {Object|null} upProj — объект проекта УП
   * @param {Object|null} prod — объект изделия
   * @returns {string}
   */
  function buildPPName(upProj, prod) {
    const prefix = userCenter
      ? 'Производственный план подразделения ' + userCenter + ' '
      : 'Производственный план '
    if (prod) {
      const prodLabel = prod.name + (prod.code ? ' ' + prod.code : '')
      return prefix + 'по изделию ' + prodLabel
    }
    if (upProj) {
      const projLabel = upProj.name_short || upProj.name_full
      return prefix + 'по проекту ' + projLabel
    }
    return prefix.trimEnd()
  }

  // ── URL-синхронизация ─────────────────────────────────────────────────

  /** Читает project_id из query string для прямых ссылок */
  function readProjectFromUrl() {
    const params = new URLSearchParams(window.location.search)
    return params.get('project_id') || null
  }

  /** Обновляет URL без перезагрузки (pushState) */
  function setProjectUrl(projectId) {
    const url = new URL(window.location)
    if (projectId) {
      url.searchParams.set('project_id', projectId)
    } else {
      url.searchParams.delete('project_id')
    }
    window.history.pushState({}, '', url)
  }

  /** Синхронизирует фильтры ПП (год, месяц, отдел) в URL */
  function syncFiltersToUrl() {
    const url = new URL(window.location)
    // Год
    if (selectedYear.value && selectedYear.value !== new Date().getFullYear()) {
      url.searchParams.set('year', selectedYear.value)
    } else {
      url.searchParams.delete('year')
    }
    // Месяц
    if (selectedMonth.value) {
      url.searchParams.set('month', selectedMonth.value)
    } else {
      url.searchParams.delete('month')
    }
    // Отделы
    if (selectedDepts.size > 0) {
      url.searchParams.set('dept', [...selectedDepts].join(','))
    } else {
      url.searchParams.delete('dept')
    }
    window.history.replaceState({}, '', url)
  }

  /** Восстанавливает фильтры из URL (год, месяц, отдел) */
  function restoreFiltersFromUrl() {
    const params = new URLSearchParams(window.location.search)
    const y = parseInt(params.get('year'))
    if (!isNaN(y)) selectedYear.value = y
    const m = parseInt(params.get('month'))
    if (!isNaN(m) && m >= 1 && m <= 12) selectedMonth.value = m
    const dept = params.get('dept')
    if (dept) {
      dept.split(',').filter(Boolean).forEach(d => selectedDepts.add(d))
    }
  }

  // ── Сброс фильтров ───────────────────────────────────────────────────

  /** Полный сброс всех активных фильтров */
  function clearAllFilters() {
    // Очищаем colFilters
    Object.keys(colFilters).forEach(k => delete colFilters[k])
    // Очищаем mfSelections
    Object.keys(mfSelections).forEach(k => {
      mfSelections[k] = new Set()
    })
    // Сброс статус-фильтра
    statusFilter.value = 'all'
    // Сброс периода
    selectedMonth.value = null
    selectedYear.value = new Date().getFullYear()
    // Сброс отделов
    selectedDepts.clear()
    // Запоминаем что пользователь сбросил фильтр вручную
    if (currentProjectId.value) {
      sessionStorage.setItem(
        'pp_dept_filter_cleared_' + currentProjectId.value, '1'
      )
    }
  }

  return {
    // Пользователь
    isWriter,
    isAdmin,
    canApprove,
    userRole,
    userDept,
    userSector,
    userSectorName,
    userCenter,
    colSettings,

    // ПП-проекты
    projects,
    currentProjectId,
    currentProjectName,
    currentProject,

    // Строки
    rows,

    // Справочники
    dirs,
    ppStages,
    upProjects,

    // Вид
    currentView,
    viewMode,
    columnViewMode,

    // Фильтрация
    colFilters,
    mfSelections,
    statusFilter,
    selectedYear,
    selectedMonth,
    selectedDepts,
    hasActiveFilters,

    // Сортировка
    sortState,

    // Массовое выделение
    bulkMode,
    bulkSelected,

    // Загрузка
    loading,

    // Методы
    canModifyRow,
    buildPPName,
    readProjectFromUrl,
    setProjectUrl,
    syncFiltersToUrl,
    restoreFiltersFromUrl,
    clearAllFilters,
  }
}
