import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  timeout: 60_000,
  use: {
    baseURL: process.env.APP_URL || 'http://localhost:5173',
    headless: true,
  },
})
