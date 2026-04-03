<template>
  <!-- Сворачиваемая карточка НТЦ-центра с таблицей отделов -->
  <div class="cap-card" :class="{ collapsed }">
    <div class="cap-card-header" @click="collapsed = !collapsed">
      <div class="cap-card-title">
        <i class="fas fa-chevron-down cap-card-chevron"></i>
        <strong>{{ center.center_name }}</strong>
        <span class="cap-dept-count">{{ center.departments.length }} отд.</span>
      </div>
      <div v-if="center.headcount != null" class="cap-card-summary">
        <span class="cap-summary-item"><span class="cap-summary-label">Числ.:</span> {{ center.headcount }}</span>
        <span class="cap-summary-item"><span class="cap-summary-label">Мощн.:</span> {{ fmtNum(center.capacity_hours) }} ч</span>
        <span class="cap-summary-item"><span class="cap-summary-label">Потр.:</span> {{ fmtNum(center.demand_hours) }} ч</span>
        <span class="cap-summary-item">
          <div class="capacity-cell">
            <div class="loading-bar">
              <div
                class="loading-bar-fill"
                :class="'loading-bar-fill--' + center.level"
                :style="{ width: Math.min(center.loading_pct, 150) + '%' }"
              ></div>
            </div>
            <span class="capacity-pct" :class="'capacity-pct--' + center.level">
              {{ center.loading_pct }}%
            </span>
          </div>
        </span>
        <span class="cap-summary-item" v-html="levelLabel(center.level)"></span>
      </div>
    </div>
    <div class="cap-card-body">
      <table class="cap-table">
        <thead>
          <tr>
            <th>Отдел</th>
            <th style="width:120px;">Числ.</th>
            <th style="width:180px;">Мощность, ч</th>
            <th style="width:180px;">Потребн., ч</th>
            <th style="width:220px;">Загрузка</th>
            <th style="width:140px;">Уровень</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="d in center.departments"
            :key="d.department_id"
            class="cap-dept-row"
            style="cursor:pointer;"
            title="Помесячная детализация"
            @click="$emit('drill', d.department_id)"
          >
            <td>{{ d.department_name }}</td>
            <td>{{ d.headcount }}</td>
            <td>{{ fmtNum(d.capacity_hours) }}</td>
            <td>{{ fmtNum(d.demand_hours) }}</td>
            <td>
              <div class="capacity-cell">
                <div class="loading-bar">
                  <div
                    class="loading-bar-fill"
                    :class="'loading-bar-fill--' + d.level"
                    :style="{ width: Math.min(d.loading_pct, 150) + '%' }"
                  ></div>
                </div>
                <span class="capacity-pct" :class="'capacity-pct--' + d.level">
                  {{ d.loading_pct }}%
                </span>
              </div>
            </td>
            <td v-html="levelLabel(d.level)"></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
/**
 * CapCenterCard.vue — сворачиваемая карточка НТЦ-центра.
 * Показывает summary-заголовок и таблицу отделов с loading bar.
 */
import { ref } from 'vue'

defineProps({
  center: { type: Object, required: true },
})

defineEmits(['drill'])

const collapsed = ref(false)

function fmtNum(n) {
  return (n || 0).toLocaleString('ru-RU')
}

/** Метка уровня загрузки (HTML) */
function levelLabel(level) {
  const m = {
    low:      '<span style="color:#9ca3af">Недозагрузка</span>',
    normal:   '<span style="color:#16a34a">Норма</span>',
    high:     '<span style="color:#ca8a04">Повышенная</span>',
    overload: '<span style="color:#dc2626;font-weight:600">Перегрузка</span>',
  }
  return m[level] || level
}
</script>
