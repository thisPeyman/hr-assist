/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    // Point the dev proxy at wherever the backend runs (BACKEND_ORIGIN=http://localhost:8001 npm run dev)
    proxy: {
      '/api': process.env.BACKEND_ORIGIN ?? 'http://localhost:8000',
      '/auth': process.env.BACKEND_ORIGIN ?? 'http://localhost:8000',
    },
  },
  test: {
    include: ['src/**/*.test.ts'],
  },
})
