import { test, expect } from '@playwright/test'

/**
 * Feature 022 — DDD spec format toggle in the PRD modal.
 *
 * - UI smoke (headed): the modal renders the new "Spec Format" radio
 *   cards (PRD-style + DDD for SDD).
 * - API integration (headless): /api/prd/generate and /api/prd/download
 *   honour `spec_format='ddd'` and produce the feature-022 artifact set
 *   under specs/bounded-contexts/... + specs/context-map.md.
 *
 * The API calls go to :8765 (a fresh backend with the new code) so we
 * don't depend on whatever build the developer has on :8000.
 */

const BACKEND = 'http://127.0.0.1:8765'

test('UI smoke: PRD modal exposes the Spec Format toggle (PRD vs DDD for SDD)', async ({ page }) => {
  await page.goto('/')

  const trigger = page.getByRole('button', { name: 'PRD 생성' })
  await expect(trigger).toBeVisible({ timeout: 15_000 })
  await trigger.click()

  await expect(page.getByRole('heading', { name: 'Generate PRD for Vibe Coding' })).toBeVisible()

  const prdCard = page.locator('label.radio-card', { hasText: 'PRD-style' })
  const dddCard = page.locator('label.radio-card', { hasText: 'DDD for SDD' })
  await expect(prdCard).toBeVisible()
  await expect(dddCard).toBeVisible()

  // The PRD option is the default selection.
  await expect(prdCard).toHaveClass(/selected/)
  await dddCard.scrollIntoViewIfNeeded()
  await dddCard.click()
  await expect(dddCard).toHaveClass(/selected/)
  await expect(prdCard).not.toHaveClass(/selected/)

  await page.screenshot({
    path: 'test-results/ddd-spec-modal-spec-format.png',
    fullPage: true,
  })
})

test('API: /api/prd/generate with spec_format=ddd plans the DDD-for-SDD layout', async ({ request }) => {
  const resp = await request.post(`${BACKEND}/api/prd/generate`, {
    data: {
      tech_stack: { spec_format: 'ddd', ai_assistant: 'cursor' },
    },
  })
  expect(resp.ok()).toBeTruthy()
  const body = await resp.json()

  expect(body.tech_stack.spec_format).toBe('ddd')
  const files: string[] = body.files_to_generate

  // DDD layout is present.
  expect(files.some((p) => /^specs\/bounded-contexts\/.+\/domain-terms\.md$/.test(p))).toBe(true)
  expect(files.some((p) => /^specs\/bounded-contexts\/.+\/bc-.+\.md$/.test(p))).toBe(true)
  expect(files.some((p) => /^specs\/bounded-contexts\/.+\/aggregates\/aggregate-.+\.md$/.test(p))).toBe(true)
  expect(files.some((p) => /^specs\/bounded-contexts\/.+\/requirements\.md$/.test(p))).toBe(true)
  expect(files).toContain('specs/context-map.md')

  // Legacy flat layout is NOT present.
  expect(files.every((p) => !/^specs\/[^/]+_spec\.md$/.test(p))).toBe(true)
})

test('API: /api/prd/generate with spec_format=prd keeps the legacy flat layout', async ({ request }) => {
  const resp = await request.post(`${BACKEND}/api/prd/generate`, {
    data: {
      tech_stack: { spec_format: 'prd', ai_assistant: 'cursor' },
    },
  })
  expect(resp.ok()).toBeTruthy()
  const body = await resp.json()
  const files: string[] = body.files_to_generate

  expect(files.some((p) => /^specs\/[a-z0-9_-]+_spec\.md$/.test(p))).toBe(true)
  expect(files.every((p) => !p.startsWith('specs/bounded-contexts/'))).toBe(true)
  expect(files).not.toContain('specs/context-map.md')
})

test('API: /api/prd/download with spec_format=ddd returns a ZIP carrying the DDD artifacts', async ({ request }) => {
  const resp = await request.post(`${BACKEND}/api/prd/download`, {
    data: {
      tech_stack: { project_name: 'demo-ddd', spec_format: 'ddd', ai_assistant: 'cursor' },
    },
  })
  expect(resp.ok()).toBeTruthy()
  expect(resp.headers()['content-type']).toContain('application/zip')

  const buf = await resp.body()
  expect(buf.length).toBeGreaterThan(10 * 1024)

  // Central directory holds file names in plaintext for stored/deflated
  // entries — scan for the canonical feature-022 paths.
  const text = buf.toString('latin1')
  expect(text).toContain('specs/bounded-contexts/')
  expect(text).toContain('domain-terms.md')
  expect(text).toContain('/bc-')
  expect(text).toContain('/aggregates/aggregate-')
  expect(text).toContain('/requirements.md')
  expect(text).toContain('specs/context-map.md')
})
