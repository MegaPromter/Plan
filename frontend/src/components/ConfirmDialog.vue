<template>
  <!-- Диалог подтверждения (замена нативного confirm()) -->
  <BaseModal
    :show="show"
    title="Подтверждение"
    max-width="400px"
    @close="cancel"
  >
    <p style="margin:0;white-space:pre-line">{{ message }}</p>

    <template #footer>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-outline" @click="cancel">{{ cancelText }}</button>
        <button class="btn btn-primary" @click="confirm">{{ confirmText }}</button>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import BaseModal from './BaseModal.vue'

const props = defineProps({
  show:        { type: Boolean, default: false },
  message:     { type: String, default: 'Вы уверены?' },
  confirmText: { type: String, default: 'Да' },
  cancelText:  { type: String, default: 'Отмена' },
})

const emit = defineEmits(['confirm', 'cancel', 'update:show'])

function confirm() {
  emit('confirm')
  emit('update:show', false)
}

function cancel() {
  emit('cancel')
  emit('update:show', false)
}
</script>
