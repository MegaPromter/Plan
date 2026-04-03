<template>
  <!-- Панель вкладок модуля «Управление предприятием» -->
  <div class="ent-tabs" role="tablist">
    <button
      v-for="tab in tabs"
      :key="tab.id"
      class="ent-tab"
      :class="{ active: currentTab === tab.id }"
      role="tab"
      :aria-selected="currentTab === tab.id"
      :aria-controls="'panel-' + tab.id"
      @click="$emit('switchTab', tab.id)"
    >
      <i :class="tab.icon"></i> {{ tab.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  currentTab: { type: String, required: true },
})

defineEmits(['switchTab'])

// Вкладки с иконками — повторяют оригинальный HTML
const tabs = [
  { id: 'portfolio',  icon: 'fas fa-briefcase',       label: 'Портфель проектов' },
  { id: 'gg',         icon: 'fas fa-stream',           label: 'Генеральный график' },
  { id: 'cross',      icon: 'fas fa-project-diagram',  label: 'Сквозной график' },
  { id: 'capacity',   icon: 'fas fa-tachometer-alt',   label: 'Загрузка / Мощность' },
  { id: 'scenarios',  icon: 'fas fa-flask',             label: 'Сценарии «что-если»' },
]
</script>
