import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// 代理目标：默认 localhost:8000（本地开发），Docker 下通过 VITE_API_PROXY 覆盖
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': { target, changeOrigin: true },
        '/uploads': { target, changeOrigin: true },
      },
    },
  }
})
