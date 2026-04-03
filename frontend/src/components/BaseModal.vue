<template>
  <!-- Универсальная обёртка для модальных окон -->
  <Teleport to="body">
    <div v-if="show" class="modal-overlay open" @mousedown.self="$emit('close')">
      <div class="modal-box" :style="{ maxWidth }">
        <div class="modal-header">
          <h2>{{ title }}</h2>
          <button class="modal-close" @click="$emit('close')">&#10005;</button>
        </div>
        <div class="modal-body">
          <slot />
        </div>
        <div class="modal-footer" v-if="$slots.footer">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  show:     { type: Boolean, required: true },
  title:    { type: String, default: '' },
  maxWidth: { type: String, default: '520px' },
})

const emit = defineEmits(['close'])

// Закрытие по ESC
function onKeydown(e) {
  if (e.key === 'Escape' && props.show) {
    emit('close')
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>
