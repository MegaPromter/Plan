/**
 * Composable для управления состоянием модального окна.
 *
 * Пример использования:
 *   const editModal = useModal()
 *   editModal.open()   // показать
 *   editModal.close()  // скрыть
 *   // в шаблоне: v-if="editModal.isOpen.value"
 */
import { ref } from 'vue'

export function useModal() {
  const isOpen = ref(false)

  function open() {
    isOpen.value = true
  }

  function close() {
    isOpen.value = false
  }

  /** Переключить состояние */
  function toggle() {
    isOpen.value = !isOpen.value
  }

  return { isOpen, open, close, toggle }
}
