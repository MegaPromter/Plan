<template>
  <!-- Модалка создания/редактирования сценария -->
  <BaseModal
    :show="show"
    :title="scenario ? 'Редактировать сценарий' : 'Новый сценарий'"
    max-width="480px"
    @close="$emit('close')"
  >
    <form @submit.prevent="onSave">
      <!-- Название -->
      <div class="form-group">
        <label class="form-label">Название</label>
        <input v-model="form.name" type="text" class="form-input" required placeholder="Название сценария" />
      </div>

      <!-- Проект (опционально) -->
      <div class="form-group">
        <label class="form-label">Проект</label>
        <select v-model="form.project_id" class="form-select">
          <option value="">-- без проекта --</option>
          <option v-for="p in projects" :key="p.id" :value="p.id">
            {{ p.name_short || p.name_full }}
          </option>
        </select>
      </div>

      <!-- Статус (только при редактировании) -->
      <div v-if="scenario" class="form-group">
        <label class="form-label">Статус</label>
        <select v-model="form.status" class="form-select">
          <option value="draft">Черновик</option>
          <option value="active">Активный</option>
          <option value="archived">Архив</option>
        </select>
      </div>
    </form>

    <template #footer>
      <button class="btn btn-outline btn-sm" @click="$emit('close')">Отмена</button>
      <button class="btn btn-primary btn-sm" :disabled="saving" @click="onSave">
        {{ scenario ? 'Сохранить' : 'Создать' }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * ScenarioModal.vue — модалка создания/редактирования сценария.
 */
import { ref, watch } from 'vue'
import { createScenario, updateScenario } from '../../../api/enterprise.js'
import BaseModal from '../../BaseModal.vue'

const props = defineProps({
  show:     { type: Boolean, required: true },
  scenario: { type: Object, default: null },
  projects: { type: Array, default: () => [] },
})

const emit = defineEmits(['saved', 'close'])

const saving = ref(false)
const form = ref({ name: '', project_id: '', status: 'draft' })

// Заполнение формы при открытии
watch(() => props.show, (v) => {
  if (!v) return
  if (props.scenario) {
    form.value = {
      name: props.scenario.name || '',
      project_id: props.scenario.project_id || '',
      status: props.scenario.status || 'draft',
    }
  } else {
    form.value = { name: '', project_id: '', status: 'draft' }
  }
})

async function onSave() {
  const name = form.value.name.trim()
  if (!name) { alert('Укажите название'); return }

  saving.value = true
  try {
    const body = { name }
    if (form.value.project_id) body.project_id = parseInt(form.value.project_id)
    if (props.scenario) body.status = form.value.status

    if (props.scenario) {
      await updateScenario(props.scenario.id, body)
    } else {
      await createScenario(body)
    }
    emit('saved')
  } catch (e) {
    alert(e.error || 'Ошибка')
  } finally {
    saving.value = false
  }
}
</script>
