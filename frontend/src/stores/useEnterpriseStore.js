/**
 * Хранилище состояния модуля «Управление предприятием».
 *
 * Использует Vue 3 Composition API (reactive/ref/computed).
 * Создаётся один раз в корневом компоненте и пробрасывается
 * дочерним через provide/inject.
 *
 * @param {Object} config — конфигурация из Django #page-config JSON:
 *   - role: строка роли пользователя
 *   - isWriter: boolean — может ли редактировать
 *   - employees: массив { id, name } для селектов ГК
 */
import { ref, reactive, computed } from 'vue'

export const ENTERPRISE_STORE_KEY = Symbol('enterpriseStore')

export function createEnterpriseStore(config = {}) {
  // ── Пользователь ──────────────────────────────────────────────────────
  const role = config.role || 'user'
  const isWriter = !!config.isWriter
  const employees = ref(config.employees || [])

  // ── Портфель ──────────────────────────────────────────────────────────
  const portfolioData = ref([])

  /** Список проектов для селектов (ГГ, Сквозной, Загрузка, Сценарии) */
  const projectsList = computed(() =>
    portfolioData.value.map(p => ({
      id: p.id,
      name: p.name_short || p.name_full,
      name_full: p.name_full,
      name_short: p.name_short,
      code: p.code,
      status: p.status,
      priority_category: p.priority_category,
      priority_number: p.priority_number,
      chief_designer: p.chief_designer,
    }))
  )

  // ── Навигация ─────────────────────────────────────────────────────────
  const currentTab = ref('portfolio')
  const selectedProjectId = ref(null)

  // ── ГГ (Генеральный график) ───────────────────────────────────────────
  const currentGG = ref(null)

  // ── Сквозной график ───────────────────────────────────────────────────
  const currentCross = ref(null)

  // ── Загрузка / мощность ───────────────────────────────────────────────
  const capacityData = ref({ centers: [], no_center_departments: [] })
  const capacityYear = ref(new Date().getFullYear())
  const capacityMode = ref('annual')
  const capacityProjectId = ref(null)
  const capacityFilterCenter = ref(null)

  // ── Сценарии ──────────────────────────────────────────────────────────
  const scenariosList = ref([])
  const currentScenario = ref(null)
  const scenarioFilterStatus = ref('')
  const scenarioProjectId = ref(null)

  // ── Снимки (baselines) ────────────────────────────────────────────────
  const baselinesCache = ref([])

  return {
    // Пользователь
    role,
    isWriter,
    employees,

    // Портфель
    portfolioData,
    projectsList,

    // Навигация
    currentTab,
    selectedProjectId,

    // ГГ
    currentGG,

    // Сквозной
    currentCross,

    // Загрузка
    capacityData,
    capacityYear,
    capacityMode,
    capacityProjectId,
    capacityFilterCenter,

    // Сценарии
    scenariosList,
    currentScenario,
    scenarioFilterStatus,
    scenarioProjectId,

    // Снимки
    baselinesCache,
  }
}
