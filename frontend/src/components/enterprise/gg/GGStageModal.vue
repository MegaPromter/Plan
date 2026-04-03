<template>
  <!-- Модалка создания/редактирования пункта ГГ -->
  <BaseModal
    :show="show"
    :title="stage ? 'Редактирование пункта' : 'Новый пункт'"
    max-width="480px"
    @close="$emit('close')"
  >
    <form @submit.prevent="onSave">
      <div class="form-group">
        <label class="form-label">Название <span class="required">*</span></label>
        <input
          ref="nameInput"
          v-model="form.name"
          type="text"
          class="form-input"
          required
          autocomplete="off"
        >
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Начало</label>
          <input v-model="form.date_start" type="date" class="form-input">
        </div>
        <div class="form-group">
          <label class="form-label">Окончание</label>
          <input v-model="form.date_end" type="date" class="form-input">
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Трудоёмкость</label>
          <input v-model="form.labor" type="number" step="0.01" min="0" class="form-input">
        </div>
        <div class="form-group">
          <label class="form-label">Порядок</label>
          <input v-model="form.order" type="number" min="1" class="form-input">
        </div>
      </div>
    </form>

    <template #footer>
      <div style="display:flex; gap:8px; justify-content:flex-end;">
        <button class="btn btn-secondary" @click="$emit('close')">Отмена</button>
        <button class="btn btn-primary" :disabled="saving" @click="onSave">
          {{ saving ? 'Сохранение...' : 'Сохранить' }}
        </button>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, reactive, watch, nextTick } from 'vue'
import BaseModal from '../../BaseModal.vue'
import { createGGStage, updateGGStage } from '../../../api/enterprise.js'

const props = defineProps({
  show:       { type: Boolean, required: true },
  /** null = создание, object = редактирование */
  stage:      { type: Object, default: null },
  scheduleId: { type: Number, default: null },
  projectId:  { type: Number, default: null },
})

const emit = defineEmits(['saved', 'close'])

const nameInput = ref(null)
const saving = ref(false)

const form = reactive({
  name: '',
  date_start: '',
  date_end: '',
  labor: '',
  order: '',
})

// Сброс/заполнение формы при открытии
watch(() => props.show, (val) => {
  if (!val) return
  if (props.stage) {
    // Режим редактирования
    form.name = props.stage.name || ''
    form.date_start = props.stage.date_start || ''
    form.date_end = props.stage.date_end || ''
    form.labor = props.stage.labor != null ? props.stage.labor : ''
    form.order = props.stage.order != null ? props.stage.order : ''
  } else {
    // Режим создания
    form.name = ''
    form.date_start = ''
    form.date_end = ''
    form.labor = ''
    form.order = ''
  }
  nextTick(() => nameInput.value?.focus())
})

async function onSave() {
  const name = form.name.trim()
  if (!name) {
    alert('Название обязательно')
    return
  }

  const body = { name }
  if (form.date_start) body.date_start = form.date_start
  if (form.date_end) body.date_end = form.date_end
  if (form.labor !== '' && form.labor != null) body.labor = parseFloat(form.labor)
  if (form.order !== '' && form.order != null) body.order = parseInt(form.order)

  saving.value = true
  try {
    if (props.stage) {
      // Обновление существующего пункта
      await updateGGStage(props.stage.id, body)
    } else {
      // Создание нового пункта
      await createGGStage(props.projectId, body)
    }
    emit('saved')
  } catch (e) {
    alert(e.error || 'Ошибка сохранения')
  } finally {
    saving.value = false
  }
}
</script>
