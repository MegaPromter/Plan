<template>
  <!-- Табличный вид генерального графика: пункты + вехи -->
  <div>
    <!-- Пункты (stages) -->
    <div class="ent-section">
      <h3 class="ent-section-title">Пункты</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>№</th>
            <th>Название пункта</th>
            <th>Начало</th>
            <th>Окончание</th>
            <th>Трудоёмкость</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!stages.length">
            <td colspan="6" class="text-center text-muted">Нет пунктов</td>
          </tr>
          <tr v-for="s in stages" :key="s.id">
            <td>{{ s.order }}</td>
            <td>{{ s.name }}</td>
            <td>{{ s.date_start || '\u2014' }}</td>
            <td>{{ s.date_end || '\u2014' }}</td>
            <td>{{ s.labor != null ? s.labor : '\u2014' }}</td>
            <td>
              <template v-if="isWriter">
                <button
                  class="btn btn-ghost btn-sm"
                  title="Редактировать"
                  @click="$emit('edit-stage', s.id)"
                >
                  <i class="fas fa-pen"></i>
                </button>
                <button
                  class="btn btn-ghost btn-sm"
                  title="Удалить"
                  @click="$emit('delete-stage', s.id)"
                >
                  <i class="fas fa-trash"></i>
                </button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Вехи (milestones) -->
    <div class="ent-section">
      <h3 class="ent-section-title">Вехи</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>Название</th>
            <th>Дата</th>
            <th>Пункт</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!milestones.length">
            <td colspan="4" class="text-center text-muted">Нет вех</td>
          </tr>
          <tr v-for="m in milestones" :key="m.id">
            <td>{{ m.name }}</td>
            <td>{{ m.date || '\u2014' }}</td>
            <td>{{ stageName(m.stage_id) }}</td>
            <td>
              <button
                v-if="isWriter"
                class="btn btn-ghost btn-sm"
                title="Удалить"
                @click="$emit('delete-milestone', m.id)"
              >
                <i class="fas fa-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  schedule: { type: Object, required: true },
  isWriter: { type: Boolean, default: false },
})

defineEmits(['edit-stage', 'delete-stage', 'delete-milestone'])

const stages = computed(() => props.schedule?.stages || [])
const milestones = computed(() => props.schedule?.milestones || [])

/** Название пункта по id (для столбца «Пункт» в таблице вех) */
function stageName(stageId) {
  if (!stageId) return '\u2014'
  const s = stages.value.find(x => x.id === stageId)
  return s ? s.name : '\u2014'
}
</script>
