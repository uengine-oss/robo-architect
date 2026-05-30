import { defineConfig } from '@playwright/test'

// Self-contained config for the 034 epic/feature manual e2e.
// Serial (workers:1, no parallel) because the steps share Neo4j state.
export default defineConfig({
  testDir: '.',
  testMatch: /playwright-.*\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  reporter: 'line',
  use: {
    baseURL: process.env.APP_URL || 'http://localhost:5199',
    // Normal laptop viewport so screenshots frame the actual content
    // (the old 5000px-tall fullPage shots were mostly black).
    viewport: { width: 1440, height: 900 },
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
  },
})
