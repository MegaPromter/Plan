<template>
  <!-- Бейдж приоритета проекта -->
  <span class="priority-badge" :class="'priority-badge--' + category">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'
import { PRIORITY_LABELS } from '../constants/enterprise.js'

const props = defineProps({
  category: { type: String, required: true },
})

// Человекочитаемая метка; если категория неизвестна — выводим как есть
const label = computed(() => PRIORITY_LABELS[props.category] || props.category)
</script>
