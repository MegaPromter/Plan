<template>
  <!-- Плавающая панель массовых действий: появляется при bulkMode + выделенных строках -->
  <Transition name="bulk-slide">
    <div
      v-if="store.bulkMode.value && store.bulkSelected.size > 0"
      class="pp-bulk-bar"
    >
      <span class="pp-bulk-count">
        Выбрано: <strong>{{ store.bulkSelected.size }}</strong>
      </span>

      <!-- Экспорт выделенных в CSV -->
      <button class="btn btn-outline btn-sm" @click="$emit('export-csv')">
        <i class="fas fa-file-csv" aria-hidden="true"></i> Экспорт CSV
      </button>

      <!-- Удалить выделенные строки (с подтверждением) -->
      <button class="btn btn-danger btn-sm" @click="confirmDelete">
        <i class="fas fa-trash" aria-hidden="true"></i> Удалить
      </button>

      <!-- Снять выделение -->
      <button class="btn btn-outline btn-sm" @click="deselectAll">
        Снять выделение
      </button>
    </div>
  </Transition>
</template>

<script setup>
import { inject } from 'vue'
import { PP_STORE_KEY } from '../../stores/usePPStore.js'

const store = inject(PP_STORE_KEY)

const emit = defineEmits(['delete-selected', 'export-csv'])

/** Подтверждение и удаление выделенных строк */
async function confirmDelete() {
  const count = store.bulkSelected.size
  if (count === 0) return
  // Подтверждение через нативный confirm (заменить на ConfirmDialog.vue позже)
  const ok = window.confirm(`Удалить ${count} выделенных строк?`)
  if (!ok) return
  emit('delete-selected', [...store.bulkSelected])
}

/** Снять всё выделение */
function deselectAll() {
  store.bulkSelected.clear()
}
</script>

<style scoped>
.pp-bulk-bar {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 200;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  background: var(--surface, #fff);
  border: 1px solid var(--border, #ddd);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}
.pp-bulk-count { font-size: 14px; color: var(--text2); }

/* Анимация появления/исчезновения */
.bulk-slide-enter-active,
.bulk-slide-leave-active { transition: all 0.25s ease; }
.bulk-slide-enter-from,
.bulk-slide-leave-to { opacity: 0; transform: translateX(-50%) translateY(20px); }
</style>
