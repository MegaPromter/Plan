<template>
  <!-- Сравнение двух снимков (или снимка с текущим) -->
  <BaseModal
    :show="show"
    :title="compareTitle"
    max-width="960px"
    @close="$emit('close')"
  >
    <template v-if="left && right">
      <!-- Мета -->
      <div class="baseline-view-meta">
        <span><strong>v{{ left.version }}:</strong> {{ formatDate(left.created_at) }}</span>
        <span v-if="!rightIsCurrent"><strong>v{{ right.version }}:</strong> {{ formatDate(right.created_at) }}</span>
      </div>

      <!-- Таблица сравнения -->
      <table class="baseline-table baseline-compare-table">
        <thead>
          <tr>
            <th rowspan="2">#</th>
            <th rowspan="2">Название</th>
            <th colspan="2" class="baseline-col-group">v{{ left.version }}</th>
            <th colspan="2" class="baseline-col-group">{{ rightLabel }}</th>
            <th rowspan="2">Изменение</th>
          </tr>
          <tr>
            <th>Начало</th><th>Окончание</th>
            <th>Начало</th><th>Окончание</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="comparisonRows.length">
            <tr v-for="row in comparisonRows" :key="row.order" :class="row.rowClass">
              <td>{{ row.order }}</td>
              <td>{{ row.name }}</td>
              <td>{{ row.leftStart }}</td>
              <td>{{ row.leftEnd }}</td>
              <td :class="row.startDiff ? 'baseline-diff' : ''">{{ row.rightStart }}</td>
              <td :class="row.endDiff ? 'baseline-diff' : ''">{{ row.rightEnd }}</td>
              <td v-html="row.badge"></td>
            </tr>
          </template>
          <tr v-else>
            <td colspan="7" class="text-center text-muted">Нет данных</td>
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
 * BaselineCompareModal.vue — сравнение двух снимков (или снимка с текущим состоянием).
 * Показывает добавленные, удалённые и изменённые этапы с diff-подсветкой.
 */
import { computed } from 'vue'
import BaseModal from '../../BaseModal.vue'

const props = defineProps({
  show:           { type: Boolean, required: true },
  left:           { type: Object, default: null },
  right:          { type: Object, default: null },
  rightIsCurrent: { type: Boolean, default: false },
})

defineEmits(['back', 'close'])

const rightLabel = computed(() => {
  if (!props.right) return ''
  return props.rightIsCurrent
    ? `Текущий (v${props.right.version})`
    : `v${props.right.version}`
})

const compareTitle = computed(() => {
  if (!props.left || !props.right) return 'Сравнение'
  return `Сравнение: v${props.left.version} \u2192 ${rightLabel.value}`
})

// ── Построение строк сравнения ─────────────────────────────────────────

const comparisonRows = computed(() => {
  if (!props.left || !props.right) return []

  const leftEntry = (props.left.entries || []).find(e => e.data?._type === 'schedule_state')
  const rightEntry = (props.right.entries || []).find(e => e.data?._type === 'schedule_state')
  const leftStages = leftEntry ? (leftEntry.data.stages || []) : []
  const rightStages = rightEntry ? (rightEntry.data.stages || []) : []

  // Map по order
  const leftMap = {}
  leftStages.forEach(s => { leftMap[s.order] = s })
  const rightMap = {}
  rightStages.forEach(s => { rightMap[s.order] = s })

  const allOrders = [...new Set([...Object.keys(leftMap), ...Object.keys(rightMap)])]
    .sort((a, b) => a - b)

  return allOrders.map(order => {
    const l = leftMap[order]
    const r = rightMap[order]

    // Добавлен (только справа)
    if (!l && r) {
      return {
        order: r.order,
        name: r.name,
        leftStart: '\u2014', leftEnd: '\u2014',
        rightStart: r.date_start || '\u2014', rightEnd: r.date_end || '\u2014',
        startDiff: false, endDiff: false,
        rowClass: 'baseline-added',
        badge: '<span class="baseline-badge baseline-badge--added">Добавлен</span>',
      }
    }

    // Удалён (только слева)
    if (l && !r) {
      return {
        order: l.order,
        name: l.name,
        leftStart: l.date_start || '\u2014', leftEnd: l.date_end || '\u2014',
        rightStart: '\u2014', rightEnd: '\u2014',
        startDiff: false, endDiff: false,
        rowClass: 'baseline-removed',
        badge: '<span class="baseline-badge baseline-badge--removed">Удал\u0451н</span>',
      }
    }

    // Оба есть — проверяем изменения
    const changes = []
    if (l.name !== r.name) changes.push('название')
    if (l.date_start !== r.date_start) changes.push('начало')
    if (l.date_end !== r.date_end) changes.push('окончание')

    const badge = changes.length
      ? `<span class="baseline-badge baseline-badge--changed">${changes.join(', ')}</span>`
      : '<span class="baseline-badge baseline-badge--same">Без изменений</span>'

    return {
      order: r.order,
      name: r.name,
      leftStart: l.date_start || '\u2014', leftEnd: l.date_end || '\u2014',
      rightStart: r.date_start || '\u2014', rightEnd: r.date_end || '\u2014',
      startDiff: l.date_start !== r.date_start,
      endDiff: l.date_end !== r.date_end,
      rowClass: changes.length ? 'baseline-changed' : '',
      badge,
    }
  })
})

function formatDate(iso) {
  if (!iso) return '\u2014'
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>
