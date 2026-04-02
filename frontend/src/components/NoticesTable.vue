<template>
  <div class="ji-wrap">
    <table class="ji-table" id="jiTable">
      <colgroup>
        <col style="width:30px">
        <col style="width:62px">
        <col style="width:78px">
        <col style="width:110px">
        <col style="width:110px">
        <col style="width:82px">
        <col style="width:82px">
        <col style="width:40px">
        <col style="width:56px">
        <col style="width:100px">
        <col style="width:90px">
        <col style="width:80px">
        <col style="width:110px">
      </colgroup>
      <thead>
        <tr>
          <th rowspan="2">&#8470;</th>
          <th rowspan="2" class="sortable" @click="onSort('ii_pi')">
            ИИ/ПИ <SortIcon :state="sort.state" col="ii_pi" />
          </th>
          <th rowspan="2" class="sortable" @click="onSort('notice_number')">
            Номер изв. <SortIcon :state="sort.state" col="notice_number" />
          </th>
          <th colspan="2" style="text-align:center">Группа</th>
          <th rowspan="2" class="sortable" @click="onSort('date_issued')">
            Дата выпуска <SortIcon :state="sort.state" col="date_issued" />
          </th>
          <th rowspan="2" class="sortable" @click="onSort('date_expires')">
            Срок действия <SortIcon :state="sort.state" col="date_expires" />
          </th>
          <th rowspan="2" class="sortable" @click="onSort('dept')">
            Отдел <SortIcon :state="sort.state" col="dept" />
          </th>
          <th rowspan="2" class="sortable" @click="onSort('sector')">
            Сектор <SortIcon :state="sort.state" col="sector" />
          </th>
          <th rowspan="2" class="sortable" @click="onSort('executor')">
            Разработчик <SortIcon :state="sort.state" col="executor" />
          </th>
          <th rowspan="2" class="sortable" @click="onSort('description')">
            Описание <SortIcon :state="sort.state" col="description" />
          </th>
          <th rowspan="2" class="sortable" @click="onSort('status')">
            Статус <SortIcon :state="sort.state" col="status" />
          </th>
          <th rowspan="2" class="col-actions"></th>
        </tr>
        <tr>
          <th class="sortable" @click="onSort('subject')">
            Наименование <SortIcon :state="sort.state" col="subject" />
          </th>
          <th class="sortable" @click="onSort('doc_designation')">
            Обозначение <SortIcon :state="sort.state" col="doc_designation" />
          </th>
        </tr>
        <!-- Строка фильтров -->
        <tr class="filter-row">
          <th></th>
          <th v-for="col in filterCols" :key="col">
            <FilterDropdown
              :col="col"
              :values="mf.getValues(col)"
              :active="!!mf.filters[col]"
              @apply="(sel) => mf.setFilter(col, sel)"
            />
          </th>
          <th class="col-actions"></th>
        </tr>
      </thead>
      <tbody>
        <!-- Skeleton-загрузка -->
        <template v-if="loading">
          <tr v-for="i in 5" :key="'sk'+i">
            <td colspan="13">
              <div class="skeleton skeleton-row" style="height:36px;margin:6px 0"></div>
            </td>
          </tr>
        </template>
        <!-- Ошибка -->
        <tr v-else-if="error">
          <td colspan="13" style="color:var(--danger);text-align:center">
            Ошибка загрузки данных
          </td>
        </tr>
        <!-- Пустое состояние -->
        <tr v-else-if="displayed.length === 0">
          <td colspan="13">
            <div class="empty-state">
              <i class="fas fa-envelope-open empty-state-icon"></i>
              <div class="empty-state-title">Нет извещений</div>
              <div class="empty-state-desc">Попробуйте изменить фильтры или добавьте новое извещение</div>
              <div v-if="cfg.isAdmin" class="empty-state-action">
                <button class="btn btn-primary btn-sm" @click="$emit('add')">
                  <i class="fas fa-plus"></i> Новое извещение
                </button>
              </div>
            </div>
          </td>
        </tr>
        <!-- Данные -->
        <NoticeRow
          v-for="(notice, idx) in displayed"
          :key="notice.id"
          :notice="notice"
          :index="idx"
          :can-modify="canModify(notice)"
          :can-close="canCloseRow(notice)"
          :can-edit="canEditRow(notice)"
          :can-delete="canDeleteRow(notice)"
          @edit="$emit('edit', $event)"
          @desc="$emit('desc', $event)"
          @close="$emit('close', $event)"
          @delete="$emit('delete', $event)"
        />
      </tbody>
    </table>
  </div>
  <div class="ji-footer">
    Записей: {{ filtered.length }}
    <template v-if="filtered.length < data.length">
      (из {{ data.length }})
    </template>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import NoticeRow from './NoticeRow.vue'
import FilterDropdown from './FilterDropdown.vue'
import SortIcon from './SortIcon.vue'
import { useMultiFilter } from '../composables/useMultiFilter.js'
import { useSort } from '../composables/useSort.js'

const props = defineProps({
  data: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  error: { type: Boolean, default: false },
  cfg: { type: Object, required: true },
})

const emit = defineEmits(['add', 'edit', 'desc', 'close', 'delete'])

const filterCols = [
  'ii_pi', 'notice_number', 'subject', 'doc_designation',
  'date_issued', 'date_expires', 'dept', 'sector',
  'executor', 'description', 'status',
]

const dataRef = computed(() => props.data)
const mf = useMultiFilter(dataRef, filterCols)
const sort = useSort()

function onSort(col) { sort.toggle(col) }

const filtered = computed(() => {
  return mf.applyFilters(props.data)
})

const sorted = computed(() => {
  return sort.applySortToArray(filtered.value, (row, col) => row[col] || '')
})

// Ленивая отрисовка (infinite scroll)
const CHUNK = 50
const renderedCount = ref(CHUNK)

const displayed = computed(() => {
  return sorted.value.slice(0, renderedCount.value)
})

function onScroll() {
  const wrap = document.querySelector('.ji-wrap')
  if (!wrap) return
  if (wrap.scrollTop + wrap.clientHeight >= wrap.scrollHeight - 100) {
    if (renderedCount.value < sorted.value.length) {
      renderedCount.value = Math.min(renderedCount.value + CHUNK, sorted.value.length)
    }
  }
}

onMounted(() => {
  const wrap = document.querySelector('.ji-wrap')
  if (wrap) wrap.addEventListener('scroll', onScroll)
})
onUnmounted(() => {
  const wrap = document.querySelector('.ji-wrap')
  if (wrap) wrap.removeEventListener('scroll', onScroll)
})

// Сбрасываем счётчик при изменении фильтров/сортировки
import { watch } from 'vue'
watch([filtered], () => { renderedCount.value = CHUNK })

// Права доступа
function canModify(n) {
  const cfg = props.cfg
  if (cfg.userRole === 'admin' || cfg.userRole === 'ntc_head' || cfg.userRole === 'ntc_deputy') return true
  if (cfg.userRole === 'dept_head' || cfg.userRole === 'dept_deputy') return n.dept === cfg.userDept
  if (cfg.userRole === 'sector_head') return n.sector === cfg.userSector
  return false
}
function canCloseRow(n) { return canModify(n) && (n.status === 'active' || n.status === 'expired') }
function canEditRow(n) { return canModify(n) && !n.is_auto }
function canDeleteRow(n) {
  const cfg = props.cfg
  const full = cfg.userRole === 'admin' || cfg.userRole === 'ntc_head' || cfg.userRole === 'ntc_deputy'
  return full && !n.is_auto
}
</script>

<style scoped>
.sortable { cursor: pointer; user-select: none; }
</style>
