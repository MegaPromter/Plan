<template>
  <div v-if="visible" class="modal-overlay open" @click.self="$emit('close')">
    <div class="modal-box" style="max-width:520px">
      <div class="modal-header">
        <h2>{{ editId ? 'Редактировать извещение' : 'Добавить извещение' }}</h2>
        <button class="modal-close" @click="$emit('close')">&#10005;</button>
      </div>
      <div class="modal-body" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div>
          <label class="form-label">ИИ/ПИ</label>
          <select v-model="form.ii_pi" class="form-input" @change="onIiPiChange">
            <option value="">--</option>
            <option value="ИИ">ИИ</option>
            <option value="ПИ">ПИ</option>
          </select>
        </div>
        <div>
          <label class="form-label">Номер изв.</label>
          <input v-model="form.notice_number" class="form-input" type="text">
        </div>
        <div>
          <label class="form-label">Дата выпуска</label>
          <input v-model="form.date_issued" class="form-input" type="date" :max="today">
        </div>
        <div>
          <label class="form-label">Срок действия</label>
          <input v-model="form.date_expires" class="form-input" type="date" :disabled="form.ii_pi === 'ИИ'">
        </div>
        <div>
          <label class="form-label">Отдел</label>
          <input v-model="form.dept" class="form-input" type="text" placeholder="код отдела">
        </div>
        <div>
          <label class="form-label">Сектор</label>
          <input v-model="form.sector" class="form-input" type="text">
        </div>
        <div>
          <label class="form-label">Разработчик</label>
          <input v-model="form.executor" class="form-input" type="text">
        </div>
        <div>
          <label class="form-label">Статус</label>
          <select v-model="form.status" class="form-input">
            <option value="active">Действует</option>
            <option value="expired">Просрочено</option>
            <option value="closed_no">Погашено без внесения</option>
            <option value="closed_yes">Погашено с внесением</option>
          </select>
        </div>
        <div style="grid-column:1/-1">
          <label class="form-label">Наименование</label>
          <input v-model="form.subject" class="form-input" type="text">
        </div>
        <div style="grid-column:1/-1">
          <label class="form-label">Обозначение</label>
          <input v-model="form.doc_designation" class="form-input" type="text">
        </div>
        <div style="grid-column:1/-1">
          <label class="form-label">Описание</label>
          <textarea v-model="form.description" class="form-input" rows="3"></textarea>
        </div>
      </div>
      <div class="modal-footer" style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-outline" @click="$emit('close')">Отмена</button>
        <button class="btn btn-primary" @click="save" :disabled="saving">
          {{ saving ? 'Сохранение...' : 'Сохранить' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { createNotice, updateNotice } from '../api/journal.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  editId: { type: Number, default: null },
  editData: { type: Object, default: null },
})

const emit = defineEmits(['close', 'saved'])

const today = new Date().toISOString().slice(0, 10)
const saving = ref(false)

const form = reactive({
  ii_pi: '', notice_number: '', date_issued: '', date_expires: '',
  dept: '', sector: '', executor: '', subject: '',
  doc_designation: '', description: '', status: 'active',
})

let savedDateExpires = ''

function onIiPiChange() {
  if (form.ii_pi === 'ИИ') {
    savedDateExpires = form.date_expires
    form.date_expires = ''
  } else if (!form.date_expires && savedDateExpires) {
    form.date_expires = savedDateExpires
  }
}

// При открытии модала — заполняем форму
watch(() => props.visible, (v) => {
  if (!v) return
  if (props.editData) {
    Object.assign(form, {
      ii_pi: props.editData.ii_pi || '',
      notice_number: props.editData.notice_number || '',
      date_issued: props.editData.date_issued || '',
      date_expires: props.editData.date_expires || '',
      dept: props.editData.dept || '',
      sector: props.editData.sector || '',
      executor: props.editData.executor || '',
      subject: props.editData.subject || '',
      doc_designation: props.editData.doc_designation || '',
      description: props.editData.description || '',
      status: props.editData.status_raw || props.editData.status || 'active',
    })
  } else {
    Object.keys(form).forEach(k => { form[k] = k === 'status' ? 'active' : '' })
  }
})

async function save() {
  saving.value = true
  try {
    if (props.editId) {
      await updateNotice(props.editId, { ...form })
    } else {
      await createNotice({ ...form })
    }
    emit('saved')
    emit('close')
  } catch (e) {
    window.showToast?.(e.message, 'error')
  } finally {
    saving.value = false
  }
}
</script>
