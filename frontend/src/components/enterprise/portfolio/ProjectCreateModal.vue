<template>
  <!-- Модалка создания нового проекта -->
  <BaseModal :show="show" title="Новый проект" max-width="500px" @close="$emit('close')">
    <div class="form-group">
      <label>Полное наименование <span style="color:var(--danger)">*</span></label>
      <input v-model="form.name_full" type="text" class="form-input" placeholder="Наименование проекта">
    </div>
    <div class="form-group">
      <label>Краткое наименование</label>
      <input v-model="form.name_short" type="text" class="form-input" placeholder="Сокращение">
    </div>
    <div class="form-group">
      <label>Шифр / код</label>
      <input v-model="form.code" type="text" class="form-input" placeholder="Код проекта">
    </div>
    <div class="form-group">
      <label>Главный конструктор</label>
      <select v-model="form.chief_designer_id" class="form-select">
        <option value="">—</option>
        <option v-for="e in employees" :key="e.id" :value="e.id">{{ e.name }}</option>
      </select>
    </div>
    <div class="form-group">
      <label>Статус</label>
      <select v-model="form.status" class="form-select">
        <option value="prospective">Перспективный</option>
        <option value="approved">Утверждён</option>
        <option value="active">Активный</option>
        <option value="suspended">Приостановлен</option>
        <option value="deferred">Отложен</option>
        <option value="closed">Закрыт</option>
        <option value="cancelled">Отменён</option>
      </select>
    </div>
    <div class="form-group">
      <label>Категория приоритета</label>
      <select v-model="form.priority_category" class="form-select">
        <option value="">—</option>
        <option value="critical">Критический</option>
        <option value="high">Высокий</option>
        <option value="medium">Средний</option>
        <option value="low">Низкий</option>
      </select>
    </div>
    <div class="form-group">
      <label>Номер приоритета</label>
      <input v-model.number="form.priority_number" type="number" class="form-input" min="1" placeholder="—">
    </div>

    <template #footer>
      <button class="btn btn-secondary" @click="$emit('close')">Отмена</button>
      <button class="btn btn-primary" :disabled="saving" @click="save">
        {{ saving ? 'Создание...' : 'Создать' }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import BaseModal from '../../BaseModal.vue'
import { createProject } from '../../../api/enterprise.js'

const props = defineProps({
  show:      { type: Boolean, required: true },
  employees: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'saved'])

const saving = ref(false)

// Начальные значения формы
const defaults = () => ({
  name_full: '',
  name_short: '',
  code: '',
  chief_designer_id: '',
  status: 'active',
  priority_category: '',
  priority_number: null,
})

const form = reactive(defaults())

// Сброс формы при открытии
watch(() => props.show, (val) => {
  if (val) Object.assign(form, defaults())
})

async function save() {
  if (!form.name_full.trim()) {
    alert('Полное наименование обязательно')
    return
  }

  saving.value = true
  try {
    await createProject({
      name_full: form.name_full.trim(),
      name_short: form.name_short.trim(),
      code: form.code.trim(),
      status: form.status,
      priority_category: form.priority_category || null,
      priority_number: form.priority_number || null,
      chief_designer_id: form.chief_designer_id ? Number(form.chief_designer_id) : null,
    })
    emit('saved')
  } catch (e) {
    alert(e.error || 'Ошибка создания проекта')
  } finally {
    saving.value = false
  }
}
</script>
