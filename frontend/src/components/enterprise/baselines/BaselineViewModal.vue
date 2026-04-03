<template>
  <!-- Просмотр одного снимка (baseline) -->
  <BaseModal
    :show="show"
    :title="'Снимок v' + (baseline?.version || '')"
    max-width="800px"
    @close="$emit('close')"
  >
    <template v-if="baseline">
      <!-- Мета-информация -->
      <div class="baseline-view-meta">
        <span><strong>Дата:</strong> {{ formatDate(baseline.created_at) }}</span>
        <span><strong>Автор:</strong> {{ baseline.created_by || '\u2014' }}</span>
        <span><strong>Комментарий:</strong> {{ baseline.comment || '\u2014' }}</span>
      </div>

      <!-- Этапы -->
      <h4 style="margin:16px 0 8px;">Этапы</h4>
      <table class="baseline-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Название</th>
            <th>Начало</th>
            <th>Окончание</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="stages.length">
            <tr v-for="s in stages" :key="s.order">
              <td>{{ s.order }}</td>
              <td>{{ s.name }}</td>
              <td>{{ s.date_start || '\u2014' }}</td>
              <td>{{ s.date_end || '\u2014' }}</td>
            </tr>
          </template>
          <tr v-else>
            <td colspan="4" class="text-center text-muted">Нет этапов</td>
          </tr>
        </tbody>
      </table>

      <!-- Вехи -->
      <h4 style="margin:16px 0 8px;">Вехи</h4>
      <table class="baseline-table">
        <thead>
          <tr>
            <th>Название</th>
            <th>Дата</th>
            <th>Этап</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="milestones.length">
            <tr v-for="m in milestones" :key="m.name + m.date">
              <td>{{ m.name }}</td>
              <td>{{ m.date || '\u2014' }}</td>
              <td>{{ milestoneStage(m) }}</td>
            </tr>
          </template>
          <tr v-else>
            <td colspan="3" class="text-center text-muted">Нет вех</td>
          </tr>
        </tbody>
      </table>
    </template>

    <template #footer>
      <button class="btn btn-outline btn-sm" @click="$emit('back')">
        <i class="fas fa-arrow-left"></i> Назад к списку
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * BaselineViewModal.vue — просмотр содержимого одного снимка (baseline).
 * Показывает этапы и вехи из entries с _type='schedule_state'.
 */
import { computed } from 'vue'
import BaseModal from '../../BaseModal.vue'

const props = defineProps({
  show:     { type: Boolean, required: true },
  baseline: { type: Object, default: null },
})

defineEmits(['back', 'close'])

// Извлекаем state из entries
const stateEntry = computed(() => {
  return (props.baseline?.entries || []).find(e => e.data && e.data._type === 'schedule_state')
})

const stages = computed(() => stateEntry.value ? (stateEntry.value.data.stages || []) : [])
const milestones = computed(() => stateEntry.value ? (stateEntry.value.data.milestones || []) : [])

/** Название этапа для вехи */
function milestoneStage(m) {
  const stage = stages.value.find(s => s.id === m.cross_stage_id)
  return stage ? stage.name : '\u2014'
}

function formatDate(iso) {
  if (!iso) return '\u2014'
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>
