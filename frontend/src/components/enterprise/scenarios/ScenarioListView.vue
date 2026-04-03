<template>
  <!-- Таблица списка сценариев -->
  <table class="cross-table">
    <thead>
      <tr>
        <th style="width:35%;">Название</th>
        <th style="width:20%;">Проект</th>
        <th style="width:100px;">Статус</th>
        <th style="width:15%;">Автор</th>
        <th style="width:120px;">Обновлён</th>
        <th style="width:60px;"></th>
      </tr>
    </thead>
    <tbody>
      <template v-if="scenarios.length">
        <tr
          v-for="s in scenarios"
          :key="s.id"
          style="cursor:pointer;"
          @click="$emit('open', s.id)"
        >
          <td style="text-align:left; font-weight:600;">{{ s.name }}</td>
          <td>{{ projectName(s.project_id) }}</td>
          <td>
            <span class="scenario-status" :class="statusClass(s.status)">
              {{ SCENARIO_STATUS_LABELS[s.status] || s.status }}
            </span>
          </td>
          <td>{{ s.created_by || '' }}</td>
          <td>{{ s.updated_at ? s.updated_at.substring(0, 10) : '' }}</td>
          <td>
            <template v-if="isWriter">
              <button class="btn btn-ghost btn-sm" @click.stop="$emit('edit', s.id)" title="Редактировать">
                <i class="fas fa-pen"></i>
              </button>
              <button class="btn btn-ghost btn-sm btn-danger-text" @click.stop="$emit('delete', s.id)" title="Удалить">
                <i class="fas fa-trash"></i>
              </button>
            </template>
          </td>
        </tr>
      </template>
      <tr v-else>
        <td colspan="6" class="text-center text-muted">Нет сценариев</td>
      </tr>
    </tbody>
  </table>
</template>

<script setup>
/**
 * ScenarioListView.vue — табличный список сценариев.
 * Клик по строке открывает детальный вид.
 */
import { inject } from 'vue'
import { ENTERPRISE_STORE_KEY } from '../../../stores/useEnterpriseStore.js'
import { SCENARIO_STATUS_LABELS } from '../../../constants/enterprise.js'

const store = inject(ENTERPRISE_STORE_KEY)

defineProps({
  scenarios: { type: Array, default: () => [] },
  isWriter:  { type: Boolean, default: false },
})

defineEmits(['open', 'edit', 'delete'])

/** Название проекта по id */
function projectName(projectId) {
  if (!projectId) return '\u2014'
  const p = store.projectsList.value.find(x => x.id === projectId)
  return p ? (p.name_short || p.name_full) : '\u2014'
}

/** CSS-класс статуса */
function statusClass(status) {
  if (status === 'active') return 'status--active'
  if (status === 'archived') return 'status--closed'
  return 'status--draft'
}
</script>
