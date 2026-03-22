import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/auth':         'http://127.0.0.1:8000',
      '/users':        'http://127.0.0.1:8000',
      '/upload':       'http://127.0.0.1:8000',
      '/my-reports':   'http://127.0.0.1:8000',
      '/my-transactions': 'http://127.0.0.1:8000',
      '/my-fraud-rings':  'http://127.0.0.1:8000',
      '/download':     'http://127.0.0.1:8000',
      '/chatbot':      'http://127.0.0.1:8000',
      '/health':       'http://127.0.0.1:8000',
    }
  },
  base: command === 'build' ? '/Money_muling/' : '/'
}))
