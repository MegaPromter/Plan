<template>
  <!-- Детальный вид сценария с записями -->
  <div>
    <!-- Шапка: кнопка назад, заголовок, статус -->
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:12px;">
      <button class="btn btn-ghost btn-sm" @click="$emit('back')">
        <i class="fas fa-arrow-left"></i> Назад
      </button>
      <h3 class="ent-section-title" style="margin:0; border:none; padding:0;">
        {{ scenario.name }}
      </h3>
      <span class="scenario-status" :class="statusClass(scenario.status)">
        {{ SCENARIO_STATUS_LABELS[scenario.status] || scenario.status }}
      </span>
    </div>

    <!-- Мета-информация -->
    <div class="ent-meta-bar">
      <div class="ent-meta-item">
        <span class="ent-meta-label">Проект:</span> {{ projectName }}
      </div>
      <div class="ent-meta-item">
        <span class="ent-meta-label">Автор:</span> {{ scenario.created_by || '\u2014' }}
      </div>
      <div class="ent-meta-item">
        <span class="ent-meta-label">Создан:</span> {{ scenario.created_at?.substring(0, 10) || '\u2014' }}
      </div>
      <button
        v-if="isWriter"
        class="btn btn-outline btn-sm"
        @click="$emit('edit', scenario.id)"
      >
        <i class="fas fa-pen"></i> Редактировать
      </button>
    </div>

    <!-- Записи сценария -->
    <div class="ent-section">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <h4 class="ent-section-title" style="margin:0; border:none; padding:0;">Записи сценария</h4>
        <button
          v-if="isWriter"
          class="btn btn-primary btn-sm"
          @click="showEntryModal = true"
        >
          <i class="fas fa-plus"></i> Добавить запись
        </button>
      </div>

      <table class="cross-table">
        <thead>
          <tr>
            <th>Работа / Описание</th>
            <th style="width:100px;">Отдел</th>
            <th style="width:100px;">Труд., ч</th>
            <th style="width:110px;">Начало</th>
            <th style="width:110px;">Окончание</th>
            <th style="width:60px;"></th>
          </tr>
        </thead>
        <tbody>
          <template v-if="entries.length">
            <tr v-for="e in entries" :key="e.id">
              <td style="text-align:left;">{{ entryName(e) }}</td>
              <td>{{ e.data?.department || '\u2014' }}</td>
              <td>{{ e.data?.labor != null ? e.data.labor : '\u2014' }}</td>
              <td>{{ e.data?.date_start || '\u2014' }}</td>
              <td>{{ e.data?.date_end || '\u2014' }}</td>
              <td>
                <button
                  v-if="isWriter"
                  class="btn btn-ghost btn-sm btn-danger-text"
                  @click="onDeleteEntry(e.id)"
                  title="Удалить"
                >
                  <i class="fas fa-trash"></i>
                </button>
              </td>
            </tr>
          </template>
          <tr v-else>
            <td colspan="6" class="text-center text-muted">
              Нет записей. Добавьте работы для моделирования.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Модалка добавления записи -->
    <ScenarioEntryModal
      :show="showEntryModal"
      :scenario-id="scenario.id"
      @saved="$emit('entry-added'); showEntryModal = false"
      @close="showEntryModal = false"
    />
  </div>
</template>

<script setup>
/**
 * ScenarioDetailView.vue — детальный вид сценария с таблицей записей.
 * Поддерживает добавление и удаление записей.
 */
import { ref, computed, inject } from 'vue'
import { ENTERPRISE_STORE_KEY } from '../../../stores/useEnterpriseStore.js'
import { SCENARIO_STATUS_LABELS } from '../../../constants/enterprise.js'
import { deleteScenarioEntry } from '../../../api/enterprise.js'
import ScenarioEntryModal from './ScenarioEntryModal.vue'

const store = inject(ENTERPRISE_STORE_KEY)

const props = defineProps({
  scenario: { type: Object, required: true },
  isWriter: { type: Boolean, default: false },
})

const emit = defineEmits(['back', 'edit', 'entry-added', 'entry-deleted'])

const showEntryModal = ref(false)

const entries = computed(() => props.scenario.entries || [])

const projectName = computed(() => {
  if (!props.scenario.project_id) return '\u2014'
  const p = store.projectsList.value.find(x => x.id === props.scenario.project_id)
  return p ? (p.name_short || p.name_full) : '\u2014'
})

function entryName(e) {
  const d = e.data || {}
  return d.name || (e.work_id ? `Работа #${e.work_id}` : '(без названия)')
}

function statusClass(status) {
  if (status === 'active') return 'status--active'
  if (status === 'archived') return 'status--closed'
  return 'status--draft'
}

async function onDeleteEntry(entryId) {
  if (!confirm('Удалить запись?')) return
  try {
    await deleteScenarioEntry(props.scenario.id, entryId)
    emit('entry-deleted')
  } catch (e) {
    alert(e.error || 'Ошибка')
  }
}
</script>
