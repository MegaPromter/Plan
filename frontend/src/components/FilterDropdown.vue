<template>
  <div class="mf-wrap">
    <button
      class="mf-trigger"
      :class="{ active: active }"
      @click.stop="open = !open"
    >
      {{ label }}
    </button>
    <div v-if="open" class="mf-dropdown" @click.stop>
      <div class="mf-actions">
        <button class="mf-action-btn" @click="selectAll">Все</button>
        <button class="mf-action-btn" @click="selectNone">Сброс</button>
      </div>
      <div class="mf-list">
        <label v-for="v in values" :key="v" class="mf-option">
          <input type="checkbox" :checked="selected.has(v)" @change="toggle(v)">
          <span>{{ v }}</span>
        </label>
      </div>
      <div class="mf-footer">
        <button class="btn btn-primary btn-sm" @click="apply">Применить</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  col: { type: String, required: true },
  values: { type: Array, default: () => [] },
  active: { type: Boolean, default: false },
})

const emit = defineEmits(['apply'])

const open = ref(false)
const selected = ref(new Set())

const label = computed(() => {
  if (selected.value.size === 0) return '\u25BC'
  if (selected.value.size === 1) return [...selected.value][0]
  return selected.value.size + ' выбрано'
})

function toggle(val) {
  const s = new Set(selected.value)
  if (s.has(val)) s.delete(val); else s.add(val)
  selected.value = s
}
function selectAll() { selected.value = new Set(props.values) }
function selectNone() { selected.value = new Set() }
function apply() {
  emit('apply', selected.value.size > 0 ? selected.value : null)
  open.value = false
}

// Закрытие по клику вне дропдауна
function onDocClick() { open.value = false }
onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))
</script>

<style scoped>
.mf-dropdown {
  position: absolute;
  z-index: 100;
  background: var(--surface, #fff);
  border: 1px solid var(--border, #ddd);
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  min-width: 160px;
  max-height: 300px;
  display: flex;
  flex-direction: column;
}
.mf-actions { display: flex; gap: 4px; padding: 6px 8px; border-bottom: 1px solid var(--border, #ddd); }
.mf-action-btn { font-size: 11px; cursor: pointer; background: none; border: none; color: var(--primary); }
.mf-list { overflow-y: auto; max-height: 200px; padding: 4px 8px; }
.mf-option { display: flex; align-items: center; gap: 6px; padding: 2px 0; font-size: 13px; cursor: pointer; }
.mf-footer { padding: 6px 8px; border-top: 1px solid var(--border, #ddd); text-align: right; }
</style>
