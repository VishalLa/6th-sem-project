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
      '/input': 'http://127.0.0.1:8000/',
      '/show':  'http://127.0.0.1:8000/',
      '/download': 'http://127.0.0.1:8000/'
    }
  },
  base: command === 'build' ? "/Money_muling/" : "/"
}))
