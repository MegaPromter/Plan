<template>
  <!-- Модалка привязки работ ПП к этапу сквозного графика -->
  <BaseModal
    :show="show"
    :title="'Привязать работы к этапу \u00AB' + stageName + '\u00BB'"
    max-width="800px"
    @close="$emit('close')"
  >
    <div style="overflow-x:auto;">
      <table class="cross-works-table">
        <thead>
          <tr>
            <th style="width:32px;">
              <input type="checkbox" v-model="selectAll" @change="onSelectAll" />
            </th>
            <th>Код</th>
            <th>Работа</th>
            <th>Начало</th>
            <th>Окончание</th>
            <th>Труд.</th>
            <th>Исполнитель</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in unassigned" :key="w.id">
            <td>
              <input type="checkbox" v-model="selected" :value="w.id" />
            </td>
            <td class="text-muted">{{ w.row_code }}</td>
            <td>{{ w.name }}</td>
            <td>{{ w.date_start || '\u2014' }}</td>
            <td>{{ w.date_end || '\u2014' }}</td>
            <td>{{ w.labor != null ? w.labor : '\u2014' }}</td>
            <td>{{ w.executor }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <template #footer>
      <button class="btn btn-outline btn-sm" @click="$emit('close')">Отмена</button>
      <button class="btn btn-primary btn-sm" :disabled="!selected.length || saving" @click="onAssign">
        <i v-if="saving" class="fas fa-spinner fa-spin"></i>
        <i v-else class="fas fa-link"></i>
        Привязать выбранные ({{ selected.length }})
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * AssignWorksModal.vue — модалка привязки неназначенных работ ПП
 * к конкретному этапу сквозного графика.
 */
import { ref, watch } from 'vue'
import { assignWorks } from '../../../api/enterprise.js'
import BaseModal from '../../BaseModal.vue'

const props = defineProps({
  show:       { type: Boolean, required: true },
  stageId:    { type: [Number, String], default: null },
  stageName:  { type: String, default: '' },
  unassigned: { type: Array, default: () => [] },
})

const emit = defineEmits(['assigned', 'close'])

const selected = ref([])
const selectAll = ref(false)
const saving = ref(false)

// Сброс при открытии
watch(() => props.show, (v) => {
  if (v) {
    selected.value = []
    selectAll.value = false
  }
})

function onSelectAll() {
  if (selectAll.value) {
    selected.value = props.unassigned.map(w => w.id)
  } else {
    selected.value = []
  }
}

async function onAssign() {
  if (!selected.value.length) return
  saving.value = true
  try {
    await assignWorks(props.stageId, selected.value)
    emit('assigned')
  } catch (e) {
    alert(e.error || 'Ошибка')
  } finally {
    saving.value = false
  }
}
</script>
