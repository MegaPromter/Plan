<template>
  <!-- Полоса загрузки мощности (capacity) -->
  <div class="loading-bar">
    <div class="loading-bar__fill" :class="levelClass" :style="{ width: barWidth }"></div>
    <span class="loading-bar__label">{{ Math.round(value) }}%</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },   // текущая загрузка (%)
  max:   { type: Number, default: 100 },  // максимальная шкала (для визуала)
})

// Ширина заполнения: ограничиваем 100% по визуалу
const barWidth = computed(() => {
  const pct = Math.min((props.value / props.max) * 100, 100)
  return Math.max(pct, 0) + '%'
})

// Цветовой класс: зелёный < 80%, жёлтый 80-100%, красный > 100%
const levelClass = computed(() => {
  if (props.value > 100) return 'loading-bar__fill--danger'
  if (props.value >= 80) return 'loading-bar__fill--warning'
  return 'loading-bar__fill--ok'
})
</script>

<style scoped>
.loading-bar {
  position: relative;
  height: 20px;
  background: var(--bg-secondary, #e9ecef);
  border-radius: 4px;
  overflow: hidden;
  min-width: 80px;
}

.loading-bar__fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.loading-bar__fill--ok      { background: #28a745; }
.loading-bar__fill--warning  { background: #ffc107; }
.loading-bar__fill--danger   { background: #dc3545; }

.loading-bar__label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #333;
  pointer-events: none;
}
</style>
