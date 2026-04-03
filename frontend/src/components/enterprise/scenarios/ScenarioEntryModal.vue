<template>
  <!-- Модалка добавления записи в сценарий -->
  <BaseModal
    :show="show"
    title="Добавить запись"
    max-width="520px"
    @close="$emit('close')"
  >
    <form @submit.prevent="onSave">
      <!-- Название работы -->
      <div class="form-group">
        <label class="form-label">Название работы</label>
        <input v-model="form.name" type="text" class="form-input" required placeholder="Описание работы" />
      </div>

      <!-- Отдел -->
      <div class="form-group">
        <label class="form-label">Отдел</label>
        <input v-model="form.department" type="text" class="form-input" placeholder="Отдел" />
      </div>

      <!-- Трудоёмкость -->
      <div class="form-group">
        <label class="form-label">Трудоёмкость, ч</label>
        <input v-model.number="form.labor" type="number" class="form-input" step="0.01" min="0" placeholder="0" />
      </div>

      <!-- Даты -->
      <div style="display:flex; gap:12px;">
        <div class="form-group" style="flex:1;">
          <label class="form-label">Начало</label>
          <input v-model="form.date_start" type="date" class="form-input" />
        </div>
        <div class="form-group" style="flex:1;">
          <label class="form-label">Окончание</label>
          <input v-model="form.date_end" type="date" class="form-input" />
        </div>
      </div>
    </form>

    <template #footer>
      <button class="btn btn-outline btn-sm" @click="$emit('close')">Отмена</button>
      <button class="btn btn-primary btn-sm" :disabled="saving" @click="onSave">
        <i v-if="saving" class="fas fa-spinner fa-spin"></i>
        Добавить
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * ScenarioEntryModal.vue — модалка добавления записи (entry) в сценарий.
 * Поля: name, department, labor, date_start, date_end.
 */
import { ref, watch } from 'vue'
import { createScenarioEntry } from '../../../api/enterprise.js'
import BaseModal from '../../BaseModal.vue'

const props = defineProps({
  show:       { type: Boolean, required: true },
  scenarioId: { type: [Number, String], required: true },
})

const emit = defineEmits(['saved', 'close'])

const saving = ref(false)
const form = ref({ name: '', department: '', labor: null, date_start: '', date_end: '' })

// Сброс формы при открытии
watch(() => props.show, (v) => {
  if (v) {
    form.value = { name: '', department: '', labor: null, date_start: '', date_end: '' }
  }
})

async function onSave() {
  const name = form.value.name.trim()
  if (!name) { alert('Укажите название работы'); return }

  saving.value = true
  try {
    const data = { name }
    if (form.value.department.trim()) data.department = form.value.department.trim()
    if (form.value.labor != null && form.value.labor !== '') data.labor = parseFloat(form.value.labor)
    if (form.value.date_start) data.date_start = form.value.date_start
    if (form.value.date_end) data.date_end = form.value.date_end

    await createScenarioEntry(props.scenarioId, { data })
    emit('saved')
  } catch (e) {
    alert(e.error || 'Ошибка')
  } finally {
    saving.value = false
  }
}
</script>
