<template>
  <!-- Строка портфеля проектов -->
  <tr>
    <td>{{ index + 1 }}</td>
    <td>{{ project.name_full || project.name_short }}</td>
    <td>{{ project.code }}</td>
    <td><StatusBadge :status="project.status || ''" /></td>
    <td>
      <span v-if="project.priority_number != null">{{ project.priority_number }}. </span>
      <PriorityBadge v-if="project.priority_category" :category="project.priority_category" />
      <span v-else>—</span>
    </td>
    <td>{{ chiefName }}</td>
    <td>{{ project.pp_count }}</td>
    <td>{{ project.sp_count }}</td>
    <td>{{ laborFormatted }}</td>
    <td>
      <button
        v-if="isWriter"
        class="btn btn-ghost btn-sm"
        title="Редактировать"
        @click="$emit('editProject', project.id)"
      >
        <i class="fas fa-pen"></i>
      </button>
    </td>
  </tr>
</template>

<script setup>
import { computed } from 'vue'
import StatusBadge from '../../StatusBadge.vue'
import PriorityBadge from '../../PriorityBadge.vue'

const props = defineProps({
  project:  { type: Object, required: true },
  index:    { type: Number, required: true },
  isWriter: { type: Boolean, default: false },
})

defineEmits(['editProject'])

// Имя главного конструктора
const chiefName = computed(() =>
  props.project.chief_designer ? props.project.chief_designer.name : '—'
)

// Форматирование трудоёмкости с разделителем тысяч
const laborFormatted = computed(() =>
  props.project.labor_total
    ? props.project.labor_total.toLocaleString('ru-RU')
    : '—'
)
</script>
