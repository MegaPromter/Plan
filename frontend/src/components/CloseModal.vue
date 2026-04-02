<template>
  <div v-if="visible" class="modal-overlay open" @click.self="$emit('close')">
    <div class="modal-box" style="max-width:440px">
      <div class="modal-header">
        <h2>Погашение извещения</h2>
        <button class="modal-close" @click="$emit('close')">&#10005;</button>
      </div>
      <div class="modal-body" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div style="grid-column:1/-1">
          <label class="form-label">Тип погашения</label>
          <select v-model="form.status" class="form-input">
            <option value="closed_yes">Погашено с внесением</option>
            <option value="closed_no">Погашено без внесения</option>
          </select>
        </div>
        <div style="grid-column:1/-1">
          <label class="form-label">&#8470; документа погашения *</label>
          <input v-model="form.closure_notice_number" class="form-input" type="text" required>
        </div>
        <div>
          <label class="form-label">Дата документа *</label>
          <input v-model="form.closure_date_issued" class="form-input" type="date" :max="today" required>
        </div>
        <div>
          <label class="form-label">Исполнитель *</label>
          <select v-model="form.closure_executor" class="form-input" required>
            <option value="">{{ employeesLoading ? 'Загрузка...' : '— выберите —' }}</option>
            <option v-for="emp in employees" :key="emp.short_name" :value="emp.short_name">
              {{ emp.short_name }}
            </option>
          </select>
        </div>
      </div>
      <div class="modal-footer" style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-outline" @click="$emit('close')">Отмена</button>
        <button class="btn btn-primary" @click="save" :disabled="saving">
          {{ saving ? 'Сохранение...' : 'Погасить' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { updateNotice, fetchDeptEmployees } from '../api/journal.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  noticeId: { type: Number, default: null },
  deptCode: { type: String, default: '' },
})

const emit = defineEmits(['close', 'saved'])

const today = new Date().toISOString().slice(0, 10)
const saving = ref(false)
const employees = ref([])
const employeesLoading = ref(false)

const form = reactive({
  status: 'closed_yes',
  closure_notice_number: '',
  closure_date_issued: '',
  closure_executor: '',
})

// При открытии — загружаем сотрудников отдела
watch(() => props.visible, async (v) => {
  if (!v) return
  form.status = 'closed_yes'
  form.closure_notice_number = ''
  form.closure_date_issued = ''
  form.closure_executor = ''
  employees.value = []
  if (props.deptCode) {
    employeesLoading.value = true
    try {
      employees.value = await fetchDeptEmployees(props.deptCode)
    } catch { /* ошибка загрузки */ }
    employeesLoading.value = false
  }
})

async function save() {
  if (!form.closure_notice_number || !form.closure_date_issued || !form.closure_executor) {
    window.showToast?.('Заполните все обязательные поля', 'warning')
    return
  }
  saving.value = true
  try {
    await updateNotice(props.noticeId, { ...form })
    emit('saved')
    emit('close')
  } catch (e) {
    window.showToast?.(e.message, 'error')
  } finally {
    saving.value = false
  }
}
</script>
