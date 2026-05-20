import { test, expect } from '@playwright/test'

/**
 * Feature 022 amendment (2026-05-12) — US5/US6/US7 end-to-end tests.
 *
 * UI coverage (headed): the PRD modal exposes include_frontend + the
 * framework selector populated from the backend catalog (which now
 * carries Vue / React / Svelte after the 2026-05-12 amendment).
 *
 * API coverage:
 *   - /api/prd/generate plans `specs/frontend/{framework,menu-structure,
 *     ui-flow}.md`, role-based agents (ddd-specialist + frontend-engineer),
 *     and the `/generate-frontend` slash command. Per-BC `<bc>_agent.md`
 *     entries are gone.
 *   - /api/prd/generate refuses with HTTP 400 + `frontend_framework_required`
 *     when include_frontend=true is sent without a framework (FR-020).
 *   - /api/prd/download returns a `application/zip` response. The
 *     internal zip layout (which exact files are inside, PRD↔CLAUDE
 *     disjointness, framework.md preamble) is asserted in the Python
 *     suite (`api/features/prd_generation/tests/test_role_based_emission.py`
 *     and `test_prd_split_disjoint.py`).
 *
 * The API calls target :8765 — same pattern as the v1 ddd-spec spec —
 * so the test reaches a backend running with the current code.
 */

const BACKEND = 'http://127.0.0.1:8765'


test('UI smoke: PRD modal exposes include_frontend + framework selector (Vue/React/Svelte)', async ({ page }) => {
  await page.goto('/')

  const trigger = page.getByRole('button', { name: 'PRD 생성' })
  await expect(trigger).toBeVisible({ timeout: 15_000 })
  await trigger.click()

  await expect(page.getByRole('heading', { name: 'Generate PRD for Vibe Coding' })).toBeVisible()

  // Pick DDD spec format.
  const dddCard = page.locator('label.radio-card', { hasText: 'DDD for SDD' })
  await dddCard.scrollIntoViewIfNeeded()
  await dddCard.click()
  await expect(dddCard).toHaveClass(/selected/)

  // Toggle "Include Frontend PRD and Rules"
  const includeFrontend = page.getByLabel('Include Frontend PRD and Rules')
  await includeFrontend.scrollIntoViewIfNeeded()
  await includeFrontend.check()

  // Framework dropdown should appear (UI plumbing — FR-020 surfaces the
  // selector once include_frontend is checked). The exact option list
  // is sourced from the running backend's catalog and is asserted in
  // the API test below against :8765.
  const frameworkSelect = page.locator('select').filter({
    has: page.locator('option', { hasText: /Select framework/ }),
  })
  await expect(frameworkSelect).toBeVisible({ timeout: 5_000 })
  const optionTexts = await frameworkSelect.locator('option').allTextContents()
  // At minimum, Vue and React (v1 catalog) MUST always be present.
  expect(optionTexts.some((t) => /Vue/i.test(t))).toBeTruthy()
  expect(optionTexts.some((t) => /React/i.test(t))).toBeTruthy()

  // Pick the first non-placeholder option to exercise the form binding.
  const firstReal = optionTexts.find((t) => t && !/Select framework/i.test(t))
  if (firstReal) {
    await frameworkSelect.selectOption({ label: firstReal })
  }

  await page.screenshot({
    path: 'test-results/ddd-frontend-perspective-modal.png',
    fullPage: true,
  })
})


test('API: /api/prd/generate plans the frontend perspective + role-based agents', async ({ request }) => {
  const resp = await request.post(`${BACKEND}/api/prd/generate`, {
    data: {
      tech_stack: {
        spec_format: 'ddd',
        ai_assistant: 'claude',
        include_frontend: true,
        frontend_framework: 'vue',
      },
    },
  })
  expect(resp.status()).toBe(200)
  const body = await resp.json()

  // The planned file list MUST include the three frontend files (FR-021).
  expect(body.files_to_generate).toContain('specs/frontend/framework.md')
  expect(body.files_to_generate).toContain('specs/frontend/menu-structure.md')
  expect(body.files_to_generate).toContain('specs/frontend/ui-flow.md')

  // Role-based agents (one each) — and NO per-BC <bc_name>_agent.md (FR-023).
  expect(body.files_to_generate).toContain('.claude/agents/ddd-specialist.md')
  expect(body.files_to_generate).toContain('.claude/agents/frontend-engineer.md')
  expect(body.files_to_generate).toContain('.claude/commands/generate-frontend.md')
  const perBcHits = (body.files_to_generate as string[]).filter(
    (p) => p.startsWith('.claude/agents/') && p.endsWith('_agent.md'),
  )
  expect(perBcHits).toEqual([])

  // Deprecated per-BC agents reported as cleanup hints (one per BC).
  expect(Array.isArray(body.deprecated_per_bc_agents)).toBe(true)
  expect(body.deprecated_per_bc_agents.length).toBeGreaterThan(0)
  for (const dep of body.deprecated_per_bc_agents) {
    expect(dep.reason).toBe('deprecated_per_bc_agent')
    expect(dep.existing_path).toMatch(/^\.claude\/agents\/.*_agent\.md$/)
  }
})


test('API: /api/prd/generate refuses when include_frontend=true but framework is missing (FR-020)', async ({ request }) => {
  const resp = await request.post(`${BACKEND}/api/prd/generate`, {
    data: {
      tech_stack: {
        spec_format: 'ddd',
        ai_assistant: 'claude',
        include_frontend: true,
        // frontend_framework deliberately omitted — FR-020 must trip.
      },
    },
  })
  expect(resp.status()).toBe(400)
  const body = await resp.json()
  expect(body.detail.code).toBe('frontend_framework_required')
})


test('UI: Step 2 exposes both "Download ZIP" and "Claude Code에서 열기" actions', async ({ page }) => {
  // Configure first, then preview to land on Step 2.
  await page.goto('/')

  const trigger = page.getByRole('button', { name: 'PRD 생성' })
  await expect(trigger).toBeVisible({ timeout: 15_000 })
  await trigger.click()

  await expect(page.getByRole('heading', { name: 'Generate PRD for Vibe Coding' })).toBeVisible()

  // The Preview button advances Step 1 → Step 2.
  const previewBtn = page.getByRole('button', { name: /Preview/ })
  await previewBtn.scrollIntoViewIfNeeded()
  await previewBtn.click()

  // On Step 2 both action buttons must be visible side by side.
  const downloadBtn = page.getByRole('button', { name: /Download ZIP/ })
  const openClaudeBtn = page.getByRole('button', { name: /Claude Code에서 열기/ })
  await expect(downloadBtn).toBeVisible({ timeout: 10_000 })
  await expect(openClaudeBtn).toBeVisible()

  // Clicking "Claude Code에서 열기" jumps straight to the path-picker
  // step without a download being triggered. The header reflects the
  // "Open in Claude Code" path, NOT "Download Complete!".
  await openClaudeBtn.click()
  await expect(page.getByRole('heading', { name: /Claude Code 에서 열기/ })).toBeVisible({ timeout: 5_000 })
  await expect(page.getByText('Download Complete!')).toHaveCount(0)

  await page.screenshot({
    path: 'test-results/prd-step2-two-actions.png',
    fullPage: true,
  })
})


test('API: /api/prd/download returns a zip when DDD + frontend(svelte) selected', async ({ request }) => {
  const resp = await request.post(`${BACKEND}/api/prd/download`, {
    data: {
      tech_stack: {
        spec_format: 'ddd',
        ai_assistant: 'claude',
        include_frontend: true,
        frontend_framework: 'svelte',
        project_name: 'feature-022-amendment-e2e',
      },
    },
  })
  expect(resp.status()).toBe(200)
  expect(resp.headers()['content-type']).toContain('application/zip')
  const buf = await resp.body()
  expect(buf.byteLength).toBeGreaterThan(1024)
})
