<template>
  <!--
    Выпадающий список с поиском (searchable dropdown).
    Используется в PPDepsModal для выбора задачи-предшественника/последователя.
    Поддерживает навигацию клавиатурой (ArrowUp/Down/Enter/Escape).
  -->
  <div class="search-dropdown" ref="wrapperRef">
    <input
      ref="inputRef"
      type="text"
      class="search-dropdown-input"
      :placeholder="placeholder"
      :value="searchText"
      autocomplete="off"
      @input="onInput"
      @focus="open = true"
      @keydown="onKeydown"
    >
    <span class="search-dropdown-arrow">&#x25BC;</span>
    <div v-show="open" class="search-dropdown-list open">
      <div
        v-if="filtered.length === 0"
        class="search-dropdown-empty"
      >
        Ничего не найдено
      </div>
      <div
        v-for="(item, idx) in filtered"
        :key="item.id"
        class="search-dropdown-item"
        :class="{
          selected: item.id === modelValue,
          highlighted: idx === highlightIdx,
        }"
        @click="select(item)"
      >
        {{ item.label }}
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * PPSearchDropdown — выпадающий список с текстовым поиском.
 *
 * Props:
 *   modelValue — id выбранного элемента (v-model)
 *   items      — массив { id, label }
 *   placeholder — подсказка в поле ввода
 *
 * Emits:
 *   update:modelValue — при выборе элемента
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  modelValue:  { type: [Number, String, null], default: null },
  items:       { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Поиск...' },
})

const emit = defineEmits(['update:modelValue'])

const wrapperRef = ref(null)
const inputRef = ref(null)
const open = ref(false)
const searchText = ref('')
const highlightIdx = ref(-1)

// Фильтрация элементов по введённому тексту
const filtered = computed(() => {
  const q = searchText.value.toLowerCase()
  if (!q) return props.items
  return props.items.filter(it => it.label.toLowerCase().includes(q))
})

// Сброс текста при смене modelValue извне (например, при очистке)
watch(() => props.modelValue, (val) => {
  if (!val) {
    searchText.value = ''
  } else {
    // Находим метку выбранного элемента
    const item = props.items.find(it => it.id === val)
    if (item) searchText.value = item.label
  }
}, { immediate: true })

// При изменении списка items — обновляем текст если был выбран элемент
watch(() => props.items, () => {
  if (props.modelValue) {
    const item = props.items.find(it => it.id === props.modelValue)
    if (item) searchText.value = item.label
  }
})

function onInput(e) {
  searchText.value = e.target.value
  open.value = true
  highlightIdx.value = -1
  // Сбрасываем выбор при ручном вводе
  if (props.modelValue) {
    emit('update:modelValue', null)
  }
}

function select(item) {
  searchText.value = item.label
  emit('update:modelValue', item.id)
  open.value = false
  highlightIdx.value = -1
}

function onKeydown(e) {
  const len = filtered.value.length
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlightIdx.value = Math.min(highlightIdx.value + 1, len - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlightIdx.value = Math.max(highlightIdx.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    if (highlightIdx.value >= 0 && filtered.value[highlightIdx.value]) {
      select(filtered.value[highlightIdx.value])
    }
  } else if (e.key === 'Escape') {
    open.value = false
  }
}

// Закрытие при клике вне компонента
function onDocClick(e) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))
</script>
