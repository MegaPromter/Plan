<template>
  <!-- Иерархическая таблица сквозного графика: пункты ГГ → этапы → работы -->
  <div>
    <!-- Раздел «Пункты и этапы» -->
    <div class="ent-section">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <h3 class="ent-section-title" style="margin-bottom:0; border-bottom:none; padding-bottom:0;">
          Пункты и этапы
        </h3>
        <div class="cross-expand-btns">
          <button class="btn btn-ghost btn-sm" @click="expandAll" title="Развернуть все">
            <i class="fas fa-expand-alt"></i> Развернуть
          </button>
          <button class="btn btn-ghost btn-sm" @click="collapseAll" title="Свернуть все">
            <i class="fas fa-compress-alt"></i> Свернуть
          </button>
        </div>
      </div>

      <div class="cross-table-wrap">
        <table class="cross-table">
          <thead>
            <tr>
              <th>Название</th>
              <th style="width:110px;">Начало</th>
              <th style="width:110px;">Окончание</th>
              <th style="width:80px;">Труд.</th>
              <th style="width:100px;">Отдел</th>
              <th style="width:60px;"></th>
            </tr>
          </thead>
          <tbody>
            <template v-if="ggItems.length">
              <template v-for="item in ggItems" :key="'item-' + item.id">
                <!-- Пункт ГГ — lv0 -->
                <tr class="cross-lv0">
                  <td>
                    {{ item.order }}. {{ item.name }}
                    <span v-if="totalWorksForItem(item) > 0" class="cross-works-badge">
                      {{ totalWorksForItem(item) }}
                    </span>
                  </td>
                  <td>{{ item.date_start || '\u2014' }}</td>
                  <td>{{ item.date_end || '\u2014' }}</td>
                  <td></td>
                  <td></td>
                  <td>
                    <button
                      v-if="canAssign"
                      class="btn btn-ghost btn-sm"
                      @click.stop="$emit('assign-works', item.id)"
                      title="Привязать работы"
                    >
                      <i class="fas fa-link"></i>
                    </button>
                  </td>
                </tr>

                <!-- Работы пункта напрямую -->
                <template v-if="(item.works_count || 0) > 0">
                  <tr
                    v-for="w in item.works"
                    :key="'iw-' + w.id"
                    class="cross-lv2"
                    :data-stage="item.id"
                    v-show="expandedStages.has(item.id)"
                  >
                    <td>{{ w.name }}</td>
                    <td>{{ w.date_start || '\u2014' }}</td>
                    <td>{{ w.date_end || '\u2014' }}</td>
                    <td>{{ w.labor != null ? w.labor : '\u2014' }}</td>
                    <td>{{ w.department }}</td>
                    <td>
                      <button
                        v-if="canAssign"
                        class="btn btn-ghost btn-sm btn-danger-text"
                        @click="$emit('unlink-work', { stageId: item.id, workId: w.id })"
                        title="Отвязать"
                      >
                        <i class="fas fa-unlink"></i>
                      </button>
                    </td>
                  </tr>
                </template>

                <!-- Вложенные этапы -->
                <template v-for="(sub, idx) in subByParent[item.id] || []" :key="'sub-' + sub.id">
                  <tr
                    class="cross-lv1"
                    :style="(sub.works_count || 0) > 0 ? 'cursor:pointer' : ''"
                    @click="(sub.works_count || 0) > 0 && toggleStageWorks(sub.id)"
                  >
                    <td>
                      <i
                        v-if="(sub.works_count || 0) > 0"
                        class="fas cross-chevron"
                        :class="expandedStages.has(sub.id) ? 'fa-chevron-down' : 'fa-chevron-right'"
                      ></i>
                      {{ item.order }}.{{ idx + 1 }}. {{ sub.name }}
                      <span v-if="(sub.works_count || 0) > 0" class="cross-works-badge">
                        {{ sub.works_count }}
                      </span>
                    </td>
                    <td>{{ sub.date_start || '\u2014' }}</td>
                    <td>{{ sub.date_end || '\u2014' }}</td>
                    <td></td>
                    <td></td>
                    <td>
                      <button
                        v-if="isWriter && editOwner !== 'locked'"
                        class="btn btn-ghost btn-sm"
                        @click.stop="$emit('edit-stage', sub.id)"
                        title="Редактировать"
                      >
                        <i class="fas fa-pen"></i>
                      </button>
                      <button
                        v-if="canAssign"
                        class="btn btn-ghost btn-sm"
                        @click.stop="$emit('assign-works', sub.id)"
                        title="Привязать работы"
                      >
                        <i class="fas fa-link"></i>
                      </button>
                    </td>
                  </tr>

                  <!-- Работы этапа -->
                  <template v-if="(sub.works_count || 0) > 0">
                    <tr
                      v-for="w in sub.works"
                      :key="'sw-' + w.id"
                      class="cross-lv2"
                      :data-stage="sub.id"
                      v-show="expandedStages.has(sub.id)"
                    >
                      <td>{{ w.name }}</td>
                      <td>{{ w.date_start || '\u2014' }}</td>
                      <td>{{ w.date_end || '\u2014' }}</td>
                      <td>{{ w.labor != null ? w.labor : '\u2014' }}</td>
                      <td>{{ w.department }}</td>
                      <td>
                        <button
                          v-if="canAssign"
                          class="btn btn-ghost btn-sm btn-danger-text"
                          @click="$emit('unlink-work', { stageId: sub.id, workId: w.id })"
                          title="Отвязать"
                        >
                          <i class="fas fa-unlink"></i>
                        </button>
                      </td>
                    </tr>
                  </template>
                </template>
              </template>
            </template>
            <tr v-else>
              <td colspan="6" class="text-center text-muted">Нет пунктов</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Неназначенные работы ПП -->
    <div v-if="unassignedWorks.length" class="ent-section">
      <div class="ent-section-title">
        Неназначенные работы ПП
        <span class="cross-works-badge">{{ unassignedWorks.length }}</span>
      </div>
      <table class="cross-table">
        <thead>
          <tr>
            <th>Название</th>
            <th style="width:110px;">Начало</th>
            <th style="width:110px;">Окончание</th>
            <th style="width:80px;">Труд.</th>
            <th style="width:100px;">Отдел</th>
            <th style="width:60px;"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in unassignedWorks" :key="'ua-' + w.id" class="cross-lv2">
            <td>{{ w.name }}</td>
            <td>{{ w.date_start || '\u2014' }}</td>
            <td>{{ w.date_end || '\u2014' }}</td>
            <td>{{ w.labor != null ? w.labor : '\u2014' }}</td>
            <td>{{ w.department }}</td>
            <td></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Вехи -->
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
          <template v-if="milestones.length">
            <tr v-for="m in milestones" :key="'ms-' + m.id">
              <td>{{ m.name }}</td>
              <td>{{ m.date || '\u2014' }}</td>
              <td>{{ milestoneItemName(m) }}</td>
              <td>
                <button
                  v-if="isWriter && editOwner !== 'locked'"
                  class="btn btn-ghost btn-sm"
                  @click="$emit('delete-milestone', m.id)"
                  title="Удалить"
                >
                  <i class="fas fa-trash"></i>
                </button>
              </td>
            </tr>
          </template>
          <tr v-else>
            <td colspan="4" class="text-center text-muted">Нет вех</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
/**
 * CrossTable.vue — иерархическая таблица сквозного графика.
 * Три уровня: пункт ГГ (lv0) -> этап (lv1) -> работы (lv2).
 * Поддержка expand/collapse, привязки/отвязки работ.
 */
import { ref, computed } from 'vue'

const props = defineProps({
  cross:    { type: Object, default: null },
  isWriter: { type: Boolean, default: false },
})

defineEmits(['edit-stage', 'delete-stage', 'delete-milestone', 'assign-works', 'unlink-work'])

// ── Expand/collapse ────────────────────────────────────────────────────
const expandedStages = ref(new Set())

function toggleStageWorks(stageId) {
  if (expandedStages.value.has(stageId)) {
    expandedStages.value.delete(stageId)
  } else {
    expandedStages.value.add(stageId)
  }
}

function expandAll() {
  const stages = props.cross?.stages || []
  stages.forEach(s => {
    if ((s.works_count || 0) > 0) expandedStages.value.add(s.id)
  })
}

function collapseAll() {
  expandedStages.value.clear()
}

// ── Вычисляемые ────────────────────────────────────────────────────────

const editOwner = computed(() => props.cross?.edit_owner || 'cross')
const canAssign = computed(() => props.isWriter && editOwner.value === 'cross')

const stages = computed(() => props.cross?.stages || [])
const milestones = computed(() => props.cross?.milestones || [])
const unassignedWorks = computed(() => props.cross?.unassigned_works || [])

/** Пункты ГГ (is_item=true) */
const ggItems = computed(() => stages.value.filter(s => s.is_item))

/** Вложенные этапы сгруппированные по parent_item_id */
const subByParent = computed(() => {
  const map = {}
  stages.value.filter(s => !s.is_item).forEach(s => {
    const pid = s.parent_item_id
    if (!map[pid]) map[pid] = []
    map[pid].push(s)
  })
  return map
})

/** Общее кол-во работ для пункта ГГ (включая вложенные этапы) */
function totalWorksForItem(item) {
  const own = item.works_count || 0
  const subs = (subByParent.value[item.id] || []).reduce((s, sub) => s + (sub.works_count || 0), 0)
  return own + subs
}

/** Название пункта для вехи */
function milestoneItemName(m) {
  const linked = stages.value.find(s => s.id === m.cross_stage_id)
  if (!linked) return '\u2014'
  const parent = linked.gg_stage_id
    ? ggItems.value.find(g => g.id === linked.gg_stage_id)
    : linked
  return parent ? parent.name : linked.name
}
</script>
