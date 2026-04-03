<template>
  <!--
    PPProjectEditModal — редактирование названия и привязки ПП-проекта.
    Порт из production_plan.js: editProjectName().
  -->
  <BaseModal
    :show="show"
    title="Редактировать производственный план"
    max-width="440px"
    @close="$emit('close')"
  >
    <!-- Название плана -->
    <div class="modal-form-group">
      <label>Название плана</label>
      <input
        ref="nameInputRef"
        v-model="planName"
        type="text"
        :style="nameError ? 'border-color: var(--danger);' : ''"
        @keydown.enter="doSave"
      >
    </div>

    <!-- Привязка к проекту УП -->
    <div v-if="upProjectsList.length > 0" class="modal-form-group">
      <label>Привязать к проекту (УП)</label>
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

    <!-- Выбор изделия -->
    <div
      v-if="upProjectsList.length > 0 && products.length > 0"
      class="modal-form-group"
    >
      <label>Изделие проекта</label>
      <select v-model="selectedProductId">
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

    <template #footer>
      <button class="btn btn-outline btn-sm" @click="$emit('close')">Отмена</button>
      <button
        class="btn btn-primary btn-sm"
        :disabled="saving"
        @click="doSave"
      >
        Сохранить
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * PPProjectEditModal — редактирование названия ПП-проекта и привязки к УП.
 *
 * Props:
 *   project — объект ПП-проекта { id, name, up_project_id, up_product_id }
 *
 * При смене проекта УП / изделия — авто-перестраивает имя через
 * store.buildPPName(), аналогично legacy editProjectName().
 */
import { ref, computed, watch, inject, nextTick } from 'vue'
import BaseModal from '../BaseModal.vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'
import { updatePPProject, fetchUpProjects } from '../../api/pp.js'

// ── Props / Emits ───────────────────────────────────────────────────────
const props = defineProps({
  show:    { type: Boolean, required: true },
  project: { type: Object, default: null },
})

const emit = defineEmits(['close', 'saved'])

// ── Store ───────────────────────────────────────────────────────────────
const store = inject(PP_STORE_KEY)

// ── Состояние формы ─────────────────────────────────────────────────────
const nameInputRef = ref(null)
const planName = ref('')
const nameError = ref(false)
const saving = ref(false)

const selectedUpProjectId = ref('')
const selectedProductId = ref('')
const upProjectsList = ref([])

// ── Вычисляемые свойства ────────────────────────────────────────────────

const selectedUpProject = computed(() => {
  if (!selectedUpProjectId.value) return null
  return upProjectsList.value.find(
    p => String(p.id) === selectedUpProjectId.value
  ) || null
})

const products = computed(() => {
  const proj = selectedUpProject.value
  return proj && proj.products ? proj.products : []
})

// ── При открытии: предзаполнить форму текущими значениями ────────────────

watch(() => props.show, async (visible) => {
  if (!visible || !props.project) return

  // Сброс ошибки
  nameError.value = false
  saving.value = false

  // Загружаем проекты УП
  try {
    upProjectsList.value = await fetchUpProjects()
    store.upProjects.value = upProjectsList.value
  } catch (e) {
    console.error('PPProjectEditModal: ошибка загрузки проектов УП', e)
  }

  // Предзаполняем форму
  planName.value = props.project.name || ''
  selectedUpProjectId.value = props.project.up_project_id
    ? String(props.project.up_project_id) : ''
  selectedProductId.value = props.project.up_product_id
    ? String(props.project.up_product_id) : ''

  // Автофокус
  await nextTick()
  if (nameInputRef.value) nameInputRef.value.focus()
})

// ── Обработчик смены УП-проекта ─────────────────────────────────────────

function onUpProjectChange() {
  // Сброс изделия
  selectedProductId.value = ''
  // Авто-перестройка имени (опционально — пользователь может переименовать вручную)
  // Не перезаписываем если пользователь уже отредактировал вручную
}

// ── Сохранение ──────────────────────────────────────────────────────────

async function doSave() {
  const name = planName.value.trim()
  if (!name) {
    nameError.value = true
    return
  }
  nameError.value = false
  saving.value = true

  try {
    const body = { name }
    if (selectedUpProjectId.value) {
      body.up_project_id = Number(selectedUpProjectId.value)
    } else {
      body.up_project_id = null
    }
    if (selectedProductId.value) {
      body.up_product_id = Number(selectedProductId.value)
    } else {
      body.up_product_id = null
    }

    const result = await updatePPProject(props.project.id, body)
    emit('saved', { id: props.project.id, ...body, ...result })
    emit('close')
  } catch (err) {
    const msg = err && err.error ? err.error : 'Ошибка сохранения'
    alert(msg)
  } finally {
    saving.value = false
  }
}
</script>
