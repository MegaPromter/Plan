<template>
  <!-- Модалка создания вехи ГГ -->
  <BaseModal
    :show="show"
    title="Новая веха"
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

      <div class="form-group">
        <label class="form-label">Дата</label>
        <input v-model="form.date" type="date" class="form-input">
      </div>

      <div class="form-group">
        <label class="form-label">Пункт</label>
        <select v-model="form.stage_id" class="form-input">
          <option :value="null">-- без привязки --</option>
          <option v-for="s in stages" :key="s.id" :value="s.id">
            {{ s.name }}
          </option>
        </select>
      </div>
    </form>

    <template #footer>
      <div style="display:flex; gap:8px; justify-content:flex-end;">
        <button class="btn btn-secondary" @click="$emit('close')">Отмена</button>
        <button class="btn btn-primary" :disabled="saving" @click="onSave">
          {{ saving ? 'Сохранение...' : 'Создать' }}
        </button>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, reactive, watch, nextTick } from 'vue'
import BaseModal from '../../BaseModal.vue'
import { createGGMilestone } from '../../../api/enterprise.js'

const props = defineProps({
  show:       { type: Boolean, required: true },
  scheduleId: { type: Number, default: null },
  projectId:  { type: Number, default: null },
  stages:     { type: Array, default: () => [] },
})

const emit = defineEmits(['saved', 'close'])

const nameInput = ref(null)
const saving = ref(false)

const form = reactive({
  name: '',
  date: '',
  stage_id: null,
})

// Сброс формы при открытии
watch(() => props.show, (val) => {
  if (!val) return
  form.name = ''
  form.date = ''
  form.stage_id = null
  nextTick(() => nameInput.value?.focus())
})

async function onSave() {
  const name = form.name.trim()
  if (!name) {
    alert('Название обязательно')
    return
  }

  const body = { name }
  if (form.date) body.date = form.date
  if (form.stage_id) body.stage_id = form.stage_id

  saving.value = true
  try {
    await createGGMilestone(props.projectId, body)
    emit('saved')
  } catch (e) {
    alert(e.error || 'Ошибка создания')
  } finally {
    saving.value = false
  }
}
</script>
