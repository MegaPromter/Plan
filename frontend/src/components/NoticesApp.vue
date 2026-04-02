<template>
  <NoticesTable
    :data="notices"
    :loading="loading"
    :error="error"
    :cfg="cfg"
    @add="openAdd"
    @edit="openEdit"
    @desc="openDesc"
    @close="openClose"
    @delete="onDelete"
  />

  <NoticeModal
    :visible="modal.show"
    :edit-id="modal.editId"
    :edit-data="modal.editData"
    @close="modal.show = false"
    @saved="reload"
  />

  <DescModal
    :visible="descModal.show"
    :notice-id="descModal.noticeId"
    :initial-text="descModal.text"
    @close="descModal.show = false"
    @saved="reload"
  />

  <CloseModal
    :visible="closeModal.show"
    :notice-id="closeModal.noticeId"
    :dept-code="closeModal.deptCode"
    @close="closeModal.show = false"
    @saved="reload"
  />
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import NoticesTable from './NoticesTable.vue'
import NoticeModal from './NoticeModal.vue'
import DescModal from './DescModal.vue'
import CloseModal from './CloseModal.vue'
import { fetchNotices, deleteNotice } from '../api/journal.js'

// Конфигурация из Django-шаблона
const cfgEl = document.getElementById('page-config')
const cfg = cfgEl ? JSON.parse(cfgEl.textContent) : {}

const notices = ref([])
const loading = ref(true)
const error = ref(false)

// Состояние модалов
const modal = reactive({ show: false, editId: null, editData: null })
const descModal = reactive({ show: false, noticeId: null, text: '' })
const closeModal = reactive({ show: false, noticeId: null, deptCode: '' })

async function load() {
  loading.value = true
  error.value = false
  try {
    notices.value = await fetchNotices()
  } catch {
    error.value = true
  }
  loading.value = false
}

async function reload() {
  await load()
}

// Открытие модалов
function openAdd() {
  modal.editId = null
  modal.editData = null
  modal.show = true
}

function openEdit(id) {
  const n = notices.value.find(x => x.id === id)
  if (!n || n.is_auto) return
  modal.editId = id
  modal.editData = n
  modal.show = true
}

function openDesc(id) {
  const n = notices.value.find(x => x.id === id)
  if (!n) return
  descModal.noticeId = id
  descModal.text = n.description || ''
  descModal.show = true
}

function openClose(id) {
  const n = notices.value.find(x => x.id === id)
  if (!n) return
  closeModal.noticeId = id
  closeModal.deptCode = n.dept || ''
  closeModal.show = true
}

async function onDelete(id) {
  const n = notices.value.find(x => x.id === id)
  if (n?.is_auto) {
    window.showToast?.('Автоматические записи нельзя удалить', 'warning')
    return
  }
  // Используем confirmDialog из utils.js (глобальный)
  const confirmed = window.confirmDialog
    ? await window.confirmDialog('Удалить запись?', 'Подтверждение')
    : confirm('Удалить запись?')
  if (!confirmed) return
  try {
    await deleteNotice(id)
    notices.value = notices.value.filter(x => x.id !== id)
    window.showToast?.('Запись удалена', 'success')
  } catch (e) {
    window.showToast?.(e.message, 'error')
  }
}

onMounted(() => {
  load()
  // Слушаем CustomEvent от кнопки «Добавить» из topbar (вне Vue)
  const el = document.getElementById('vue-notices-app')
  if (el) el.addEventListener('notice-add', openAdd)
})
</script>
