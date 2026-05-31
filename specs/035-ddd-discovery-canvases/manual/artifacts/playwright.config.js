// @ts-check
const { defineConfig } = require('@playwright/test')

module.exports = defineConfig({
  testDir: '.',
  testMatch: ['playwright-ddd-canvases.spec.js'],
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  reporter: 'line',
  use: {
    headless: true,
    actionTimeout: 15_000,
  },
})
