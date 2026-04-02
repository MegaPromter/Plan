<template>
  <span v-if="state.col === col" class="sort-icon">
    {{ state.dir === 'asc' ? '\u25B2' : '\u25BC' }}
  </span>
</template>

<script setup>
defineProps({
  state: { type: Object, required: true },
  col: { type: String, required: true },
})
</script>

<style scoped>
.sort-icon { font-size: 10px; opacity: 0.7; margin-left: 2px; }
</style>
