<template>
  <!--
    PPProjectCreateModal — модал создания / открытия ПП-проекта.
    Два режима: «Открыть существующий» и «Создать новый».
    Порт из production_plan.js: openCreateProjectModal().
  -->
  <BaseModal
    :show="show"
    title="Производственный план"
    max-width="480px"
    @close="$emit('close')"
  >
    <!-- Секция «Открыть существующий» (если есть проекты) -->
    <div v-if="existingProjects.length > 0">
      <div class="modal-form-group">
        <label>Открыть существующий план</label>
        <select v-model="existingId">
          <option value="">-- выберите из списка --</option>
          <option
            v-for="p in existingProjects"
            :key="p.id"
            :value="String(p.id)"
          >
            {{ p.name || 'Без названия' }}
          </option>
        </select>
      </div>
      <div style="text-align: center; color: var(--muted); font-size: 13px; margin: 12px 0;">
        -- или --
      </div>
    </div>

    <!-- Секция «Создать новый план» -->
    <div style="font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 12px;">
      Создать новый план
    </div>

    <!-- Привязка к проекту УП -->
    <div v-if="upProjectsList.length > 0" class="modal-form-group">
      <label>Проект (из модуля УП)</label>
      <select v-model="selectedUpProjectId" @change="onUpProjectChange">
        <option value="">-- не привязывать --</option>
        <option
          v-for="p in upProjectsList"
          :key="p.id"
          :value="String(p.id)"
        >
          {{ p.name_short || p.name_full }}
        </option>
      </select>
    </div>

    <!-- Выбор изделия (показывается если у проекта есть изделия) -->
    <div
      v-if="upProjectsList.length > 0 && products.length > 0"
      class="modal-form-group"
    >
      <label>Изделие проекта</label>
      <select v-model="selectedProductId" @change="onProductChange">
        <option value="">-- весь проект --</option>
        <option
          v-for="pr in products"
          :key="pr.id"
          :value="String(pr.id)"
        >
          {{ pr.name }}{{ pr.code ? ' (' + pr.code + ')' : '' }}
        </option>
      </select>
    </div>

    <!-- Название плана (автозаполняется) -->
    <div class="modal-form-group">
      <label>Название плана</label>
      <input
        ref="nameInputRef"
        v-model="planName"
        type="text"
        placeholder="Производственный план подразделения НТЦ-... по проекту ..."
        :style="nameError ? 'border-color: var(--danger);' : ''"
        @keydown.enter="doCreate"
      >
    </div>

    <template #footer>
      <button class="btn btn-outline btn-sm" @click="$emit('close')">Отмена</button>
      <button
        v-if="existingProjects.length > 0"
        class="btn btn-secondary btn-sm"
        @click="doOpen"
      >
        Открыть
      </button>
      <button
        class="btn btn-primary btn-sm"
        :disabled="creating"
        @click="doCreate"
      >
        Создать
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * PPProjectCreateModal — создание нового или открытие существующего ПП-плана.
 *
 * При выборе проекта УП автоматически формирует название плана через
 * store.buildPPName(). При выборе изделия — обновляет название.
 *
 * Порт логики из production_plan.js: openCreateProjectModal().
 */
import { ref, computed, watch, inject, nextTick } from 'vue'
import BaseModal from '../BaseModal.vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'
import { createPPProject, fetchUpProjects } from '../../api/pp.js'

// ── Props / Emits ───────────────────────────────────────────────────────
const props = defineProps({
  show: { type: Boolean, required: true },
})

const emit = defineEmits(['close', 'created', 'opened'])

// ── Store ───────────────────────────────────────────────────────────────
const store = inject(PP_STORE_KEY)

// ── Состояние формы ─────────────────────────────────────────────────────
const nameInputRef = ref(null)
const planName = ref('')
const nameError = ref(false)
const creating = ref(false)

// Режим «Открыть существующий»
const existingId = ref('')

// Привязка к УП
const selectedUpProjectId = ref('')
const selectedProductId = ref('')

// Список проектов УП (загружается при открытии модала)
const upProjectsList = ref([])

// ── Вычисляемые свойства ────────────────────────────────────────────────

/** Существующие ПП-проекты из store */
const existingProjects = computed(() => store.projects.value)

/** Выбранный проект УП */
const selectedUpProject = computed(() => {
  if (!selectedUpProjectId.value) return null
  return upProjectsList.value.find(
    p => String(p.id) === selectedUpProjectId.value
  ) || null
})

/** Изделия выбранного проекта УП */
const products = computed(() => {
  const proj = selectedUpProject.value
  return proj && proj.products ? proj.products : []
})

/** Выбранное изделие */
const selectedProduct = computed(() => {
  if (!selectedProductId.value) return null
  return products.value.find(
    pr => String(pr.id) === selectedProductId.value
  ) || null
})

// ── При открытии модала: загрузить проекты УП ───────────────────────────

watch(() => props.show, async (visible) => {
  if (!visible) return
  // Сброс формы
  planName.value = ''
  nameError.value = false
  existingId.value = ''
  selectedUpProjectId.value = ''
  selectedProductId.value = ''
  creating.value = false

  // Загрузка проектов УП
  try {
    upProjectsList.value = await fetchUpProjects()
    // Обновляем и в store для других компонентов
    store.upProjects.value = upProjectsList.value
  } catch (e) {
    console.error('PPProjectCreateModal: ошибка загрузки проектов УП', e)
  }

  // Автофокус на поле имени
  await nextTick()
  if (nameInputRef.value) nameInputRef.value.focus()
})

// ── Обработчики выбора УП-проекта / изделия ─────────────────────────────

function onUpProjectChange() {
  // Сброс выбора изделия при смене проекта
  selectedProductId.value = ''
  // Автогенерация названия
  planName.value = store.buildPPName(selectedUpProject.value, null)
}

function onProductChange() {
  // Обновить название с учётом изделия
  planName.value = store.buildPPName(selectedUpProject.value, selectedProduct.value)
}

// ── Открыть существующий ─────────────────────────────────────────────────

function doOpen() {
  if (!existingId.value) return
  const proj = existingProjects.value.find(
    p => String(p.id) === existingId.value
  )
  if (proj) {
    emit('opened', proj)
    emit('close')
  }
}

// ── Создать новый ────────────────────────────────────────────────────────

async function doCreate() {
  const name = planName.value.trim()
  if (!name) {
    nameError.value = true
    return
  }
  nameError.value = false
  creating.value = true

  try {
    const data = { name }
    if (selectedUpProjectId.value) data.up_project_id = Number(selectedUpProjectId.value)
    if (selectedProductId.value) data.up_product_id = Number(selectedProductId.value)
    const result = await createPPProject(data)
    emit('created', result)
    emit('close')
  } catch (err) {
    const msg = err && err.error ? err.error : 'Ошибка создания плана'
    alert(msg)
  } finally {
    creating.value = false
  }
}
</script>
