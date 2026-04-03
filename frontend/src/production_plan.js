/**
 * Entry point для Vue-приложения «Производственный план».
 * Монтируется в div#vue-pp-app в Django-шаблоне.
 *
 * Конфигурация пользователя берётся из #pp-config JSON-блока,
 * который Django-шаблон вставляет на странице.
 */
import { createApp } from 'vue'
import PPApp from './components/pp/PPApp.vue'

const configEl = document.getElementById('pp-config')
const config = configEl ? JSON.parse(configEl.textContent) : {}

const el = document.getElementById('vue-pp-app')
if (el) {
  const app = createApp(PPApp, { config })
  app.mount(el)
}
