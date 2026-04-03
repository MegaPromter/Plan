<template>
  <!-- Бейдж статуса проекта -->
  <span class="status-badge" :class="'status-badge--' + status">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'
import { STATUS_LABELS } from '../constants/enterprise.js'

const props = defineProps({
  status: { type: String, required: true },
})

// Человекочитаемая метка; если статус неизвестен — выводим как есть
const label = computed(() => STATUS_LABELS[props.status] || props.status)
</script>
