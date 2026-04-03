<template>
  <!-- Модалка редактирования enterprise-полей проекта -->
  <BaseModal :show="show" title="Редактирование проекта" max-width="500px" @close="$emit('close')">
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
        {{ saving ? 'Сохранение...' : 'Сохранить' }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import BaseModal from '../../BaseModal.vue'
import { updateProject } from '../../../api/enterprise.js'

const props = defineProps({
  show:      { type: Boolean, required: true },
  project:   { type: Object, default: null },
  employees: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'saved'])

const saving = ref(false)

const form = reactive({
  chief_designer_id: '',
  status: 'active',
  priority_category: '',
  priority_number: null,
})

// Заполнение формы при открытии / смене проекта
watch(
  () => [props.show, props.project],
  ([show, proj]) => {
    if (show && proj) {
      form.chief_designer_id = proj.chief_designer ? proj.chief_designer.id : ''
      form.status = proj.status || 'active'
      form.priority_category = proj.priority_category || ''
      form.priority_number = proj.priority_number || null
    }
  },
  { immediate: true }
)

async function save() {
  if (!props.project) return

  saving.value = true
  try {
    await updateProject(props.project.id, {
      status: form.status,
      priority_category: form.priority_category || null,
      priority_number: form.priority_number || null,
      chief_designer_id: form.chief_designer_id ? Number(form.chief_designer_id) : null,
    })
    emit('saved')
  } catch (e) {
    alert(e.error || 'Ошибка сохранения')
  } finally {
    saving.value = false
  }
}
</script>
