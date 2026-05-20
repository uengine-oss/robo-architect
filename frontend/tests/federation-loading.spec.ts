import { test, expect } from '@playwright/test'

/**
 * Test that the direct integration of open-pencil components works correctly.
 * (Federation has been replaced with direct source imports via Vite aliases.)
 */

test.describe('Open-Pencil Direct Integration', () => {
  test('canvaskit.wasm is served from /canvaskit.wasm', async ({ request }) => {
    const resp = await request.get('http://localhost:5173/canvaskit.wasm')
    expect(resp.status()).toBe(200)
    expect(resp.headers()['content-type']).toContain('wasm')
  })

  test('frontend page loads without critical errors', async ({ page }) => {
    const pageErrors: string[] = []
    page.on('pageerror', err => pageErrors.push(err.message))

    const failedRequests: string[] = []
    page.on('requestfailed', req => {
      failedRequests.push(`${req.url()} - ${req.failure()?.errorText}`)
    })

    await page.goto('/', { waitUntil: 'networkidle' })

    // No errors about module resolution or canvaskit
    const criticalErrors = pageErrors.filter(e =>
      e.includes('Failed to fetch dynamically imported module') ||
      e.includes('canvaskit') ||
      e.includes('Cannot find module')
    )
    expect(criticalErrors).toHaveLength(0)
  })

  test('UI node InspectorPanel renders without import errors', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', err => errors.push(err.message))

    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('#app')).toBeVisible()

    const criticalErrors = errors.filter(e =>
      e.includes('Failed to fetch dynamically imported module') ||
      e.includes('remoteEntry') ||
      e.includes('forEach is not a function')
    )
    expect(criticalErrors).toHaveLength(0)
  })
})
