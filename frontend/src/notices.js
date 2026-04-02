/**
 * Entry point для Vue-приложения «Журнал извещений».
 * Монтируется в div#vue-notices-app в Django-шаблоне.
 */
import { createApp } from 'vue'
import NoticesApp from './components/NoticesApp.vue'

const el = document.getElementById('vue-notices-app')
if (el) {
  const app = createApp(NoticesApp)
  app.mount(el)
}
