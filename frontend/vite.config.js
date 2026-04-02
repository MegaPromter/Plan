import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  root: resolve(__dirname),
  base: '/static/vue/',
  build: {
    // Собранные файлы кладём в Django staticfiles
    outDir: resolve(__dirname, '../static/vue'),
    emptyOutDir: true,
    manifest: 'manifest.json',
    rollupOptions: {
      input: {
        notices: resolve(__dirname, 'src/notices.js'),
        // Сюда будут добавляться новые entry points по мере миграции:
        // enterprise: resolve(__dirname, 'src/enterprise.js'),
        // production_plan: resolve(__dirname, 'src/production_plan.js'),
        // plan: resolve(__dirname, 'src/plan.js'),
      },
    },
  },
  server: {
    // Dev-сервер для HMR при разработке
    port: 5173,
    origin: 'http://localhost:5173',
  },
})
