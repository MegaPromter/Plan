<template>
  <div v-if="visible" class="modal-overlay open" @click.self="$emit('close')">
    <div class="modal-box" style="max-width:480px">
      <div class="modal-header">
        <h2>Редактировать описание</h2>
        <button class="modal-close" @click="$emit('close')">&#10005;</button>
      </div>
      <div class="modal-body">
        <label class="form-label">Описание</label>
        <textarea v-model="text" class="form-input" rows="5"></textarea>
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
import { ref, watch } from 'vue'
import { updateNotice } from '../api/journal.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  noticeId: { type: Number, default: null },
  initialText: { type: String, default: '' },
})

const emit = defineEmits(['close', 'saved'])

const text = ref('')
const saving = ref(false)

watch(() => props.visible, (v) => {
  if (v) text.value = props.initialText
})

async function save() {
  saving.value = true
  try {
    await updateNotice(props.noticeId, { description: text.value })
    emit('saved')
    emit('close')
  } catch (e) {
    window.showToast?.(e.message, 'error')
  } finally {
    saving.value = false
  }
}
</script>
