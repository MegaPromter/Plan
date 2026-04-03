/**
 * Entry point для Vue-приложения «Управление предприятием».
 * Монтируется в div#vue-enterprise-app в Django-шаблоне.
 */
import { createApp } from 'vue'
import EnterpriseApp from './components/enterprise/EnterpriseApp.vue'

const el = document.getElementById('vue-enterprise-app')
if (el) {
  const app = createApp(EnterpriseApp)
  app.mount(el)
}
