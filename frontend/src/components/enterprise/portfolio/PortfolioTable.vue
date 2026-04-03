<template>
  <!-- Таблица портфеля проектов -->
  <div class="table-responsive">
    <table class="data-table">
      <thead>
        <!-- Заголовки с сортировкой -->
        <tr>
          <th>&#8470;</th>
          <th style="cursor:pointer; user-select:none;" @click="$emit('sort', 'name')">
            Проект <SortIcon :state="sortState" col="name" />
          </th>
          <th style="cursor:pointer; user-select:none;" @click="$emit('sort', 'code')">
            Шифр <SortIcon :state="sortState" col="code" />
          </th>
          <th style="cursor:pointer; user-select:none;" @click="$emit('sort', 'status')">
            Статус <SortIcon :state="sortState" col="status" />
          </th>
          <th style="cursor:pointer; user-select:none;" @click="$emit('sort', 'priority')">
            Приоритет <SortIcon :state="sortState" col="priority" />
          </th>
          <th style="cursor:pointer; user-select:none;" @click="$emit('sort', 'chief')">
            Главный конструктор <SortIcon :state="sortState" col="chief" />
          </th>
          <th style="cursor:pointer; user-select:none;" @click="$emit('sort', 'pp_count')">
            Работы ПП <SortIcon :state="sortState" col="pp_count" />
          </th>
          <th style="cursor:pointer; user-select:none;" @click="$emit('sort', 'sp_count')">
            Работы СП <SortIcon :state="sortState" col="sp_count" />
          </th>
          <th style="cursor:pointer; user-select:none;" @click="$emit('sort', 'labor_total')">
            Трудоёмкость, ч <SortIcon :state="sortState" col="labor_total" />
          </th>
          <th></th>
        </tr>
        <!-- Строка мультифильтров -->
        <tr class="filter-row">
          <th></th>
          <th>
            <FilterDropdown
              col="name"
              :values="getFilterValues('name')"
              :active="!!filters.value?.name"
              @apply="sel => $emit('filter', 'name', sel)"
            />
          </th>
          <th>
            <FilterDropdown
              col="code"
              :values="getFilterValues('code')"
              :active="!!filters.value?.code"
              @apply="sel => $emit('filter', 'code', sel)"
            />
          </th>
          <th>
            <FilterDropdown
              col="status"
              :values="getFilterValues('status')"
              :active="!!filters.value?.status"
              @apply="sel => $emit('filter', 'status', sel)"
            />
          </th>
          <th>
            <FilterDropdown
              col="priority_category"
              :values="getFilterValues('priority_category')"
              :active="!!filters.value?.priority_category"
              @apply="sel => $emit('filter', 'priority_category', sel)"
            />
          </th>
          <th>
            <FilterDropdown
              col="chief"
              :values="getFilterValues('chief')"
              :active="!!filters.value?.chief"
              @apply="sel => $emit('filter', 'chief', sel)"
            />
          </th>
          <th></th>
          <th></th>
          <th></th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <PortfolioRow
          v-for="(project, index) in projects"
          :key="project.id"
          :project="project"
          :index="index"
          :is-writer="isWriter"
          @edit-project="id => $emit('editProject', id)"
        />
      </tbody>
    </table>
  </div>
</template>

<script setup>
import SortIcon from '../../SortIcon.vue'
import FilterDropdown from '../../FilterDropdown.vue'
import PortfolioRow from './PortfolioRow.vue'

defineProps({
  projects:        { type: Array, required: true },
  isWriter:        { type: Boolean, default: false },
  sortState:       { type: Object, required: true },
  filters:         { type: Object, required: true },
  getFilterValues: { type: Function, required: true },
})

defineEmits(['sort', 'filter', 'clearFilter', 'editProject'])
</script>
