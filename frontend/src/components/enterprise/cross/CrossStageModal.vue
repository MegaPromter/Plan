<template>
  <!-- Модалка создания/редактирования этапа сквозного графика -->
  <BaseModal
    :show="show"
    :title="stage ? 'Редактирование этапа' : 'Новый этап'"
    max-width="520px"
    @close="$emit('close')"
  >
    <form @submit.prevent="onSave">
      <!-- Пункт ГГ (родительский) -->
      <div class="form-group">
        <label class="form-label">Пункт ГГ</label>
        <select v-model="form.parent_item_id" class="form-select" required>
          <option value="">-- Выберите пункт --</option>
          <option v-for="item in ggItems" :key="item.id" :value="item.id">
            {{ item.order }}. {{ item.name }}
          </option>
        </select>
      </div>

      <!-- Название -->
      <div class="form-group">
        <label class="form-label">Название</label>
        <input v-model="form.name" type="text" class="form-input" required placeholder="Название этапа" />
      </div>

      <!-- Даты -->
      <div style="display:flex; gap:12px;">
        <div class="form-group" style="flex:1;">
          <label class="form-label">Начало</label>
          <input v-model="form.date_start" type="date" class="form-input" />
        </div>
        <div class="form-group" style="flex:1;">
          <label class="form-label">Окончание</label>
          <input v-model="form.date_end" type="date" class="form-input" />
        </div>
      </div>
    </form>

    <template #footer>
      <button class="btn btn-outline btn-sm" @click="$emit('close')">Отмена</button>
      <button class="btn btn-primary btn-sm" :disabled="saving" @click="onSave">
        <i v-if="saving" class="fas fa-spinner fa-spin"></i>
        {{ stage ? 'Сохранить' : 'Создать' }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * CrossStageModal.vue — модалка создания/редактирования этапа сквозного графика.
 * При создании вызывает createCrossStage, при редактировании — updateCrossStage.
 */
import { ref, computed, watch } from 'vue'
import { createCrossStage, updateCrossStage } from '../../../api/enterprise.js'
import BaseModal from '../../BaseModal.vue'

const props = defineProps({
  show:      { type: Boolean, required: true },
  stage:     { type: Object, default: null },     // null = создание
  cross:     { type: Object, default: null },      // текущий сквозной график
  projectId: { type: [Number, String], default: null },
})

const emit = defineEmits(['saved', 'close'])

const saving = ref(false)
const form = ref({ name: '', parent_item_id: '', date_start: '', date_end: '' })

/** Пункты ГГ (is_item=true) для выбора родителя */
const ggItems = computed(() => {
  return (props.cross?.stages || []).filter(s => s.is_item)
})

// Заполнение формы при открытии
watch(() => props.show, (v) => {
  if (!v) return
  if (props.stage) {
    form.value = {
      name: props.stage.name || '',
      parent_item_id: props.stage.parent_item_id || '',
      date_start: props.stage.date_start || '',
      date_end: props.stage.date_end || '',
    }
  } else {
    form.value = { name: '', parent_item_id: '', date_start: '', date_end: '' }
  }
})

async function onSave() {
  if (!form.value.name.trim()) { alert('Название обязательно'); return }
  if (!form.value.parent_item_id) { alert('Выберите пункт'); return }

  saving.value = true
  try {
    const body = {
      name: form.value.name.trim(),
      parent_item_id: +form.value.parent_item_id,
    }
    if (form.value.date_start) body.date_start = form.value.date_start
    if (form.value.date_end) body.date_end = form.value.date_end

    if (props.stage) {
      await updateCrossStage(props.stage.id, body)
    } else {
      await createCrossStage(props.projectId, body)
    }
    emit('saved')
  } catch (e) {
    alert(e.error || 'Ошибка сохранения')
  } finally {
    saving.value = false
  }
}
</script>
