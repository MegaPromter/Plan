<template>
  <!-- Модалка создания снимка (baseline) -->
  <BaseModal
    :show="show"
    title="Создать снимок"
    max-width="460px"
    @close="$emit('close')"
  >
    <div>
      <label style="display:block; font-size:13px; font-weight:500; margin-bottom:6px;">
        Комментарий (необязательно)
      </label>
      <textarea
        ref="commentEl"
        v-model="comment"
        rows="3"
        style="width:100%; resize:vertical; padding:8px 10px; border:1px solid var(--border); border-radius:8px; font-size:13px; font-family:inherit;"
        placeholder="Опишите причину или содержание снимка..."
      ></textarea>
    </div>

    <template #footer>
      <button class="btn btn-outline btn-sm" @click="$emit('close')">Отмена</button>
      <button class="btn btn-primary btn-sm" :disabled="saving" @click="onCreate">
        <i :class="saving ? 'fas fa-spinner fa-spin' : 'fas fa-camera'"></i>
        {{ saving ? 'Создание...' : 'Создать' }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * BaselineCreateModal.vue — модалка создания снимка сквозного графика.
 * Отправляет POST на /api/enterprise/cross/<projectId>/baselines/.
 */
import { ref, watch, nextTick } from 'vue'
import { createBaseline } from '../../../api/enterprise.js'
import BaseModal from '../../BaseModal.vue'

const props = defineProps({
  show:      { type: Boolean, required: true },
  projectId: { type: [Number, String], default: null },
})

const emit = defineEmits(['created', 'close'])

const comment = ref('')
const saving = ref(false)
const commentEl = ref(null)

// Фокус при открытии, сброс
watch(() => props.show, async (v) => {
  if (v) {
    comment.value = ''
    await nextTick()
    commentEl.value?.focus()
  }
})

async function onCreate() {
  if (!props.projectId) return
  saving.value = true
  try {
    const data = await createBaseline(props.projectId, comment.value.trim())
    emit('created', data)
  } catch (e) {
    alert(e.error || 'Ошибка')
  } finally {
    saving.value = false
  }
}
</script>
