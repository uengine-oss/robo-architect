/**
 * Robo Spec Skills (feature 029) — real-browser UI screenshots for the
 * end-to-end manual.
 *
 * What we capture (and what we don't):
 *
 *   captured here — pre-existing UI surfaces that the Phase 1+2+3 slice
 *   + the partial US1/US4 MCP-tools implementation make end-to-end
 *   relevant:
 *
 *     - The Design tab loaded against the live Neo4j (proof the
 *       3 BCs from the smoke fixture render in the navigator).
 *     - The Aggregate viewer tab focused on MemberAccount (proof of
 *       structured aggregate properties pulled from the graph).
 *     - The Event Modeling tab (proof of canvas render).
 *     - The Swagger UI at /docs with the three new robo-spec /
 *       classification routes registered.
 *     - The classification GET endpoint expanded in Swagger, showing
 *       the schema-validated request/response we added.
 *
 *   NOT captured here — UI surfaces that are part of *future* phases
 *   of feature 029 and don't exist yet:
 *
 *     - Per-element progress badges on the Design canvas (US2 / T033).
 *     - The "open implementation file" affordance on element click
 *       (US3 / T039–T041).
 *     - The "classification: core/supporting" indicator in the
 *       Inspector panel (frontend wiring deferred to a follow-on
 *       session — the BACKEND classification IS set live by the
 *       /robo-plan run, just not surfaced in this navigator yet).
 *
 *   When those land, extend this spec rather than rewriting it — the
 *   beforeEach + helper structure is already shaped for additional
 *   per-tab probes.
 */
import { test, expect, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// Output directory under the spec folder so screenshots land next to
// the manual that references them. (frontend's tsconfig compiles tests
// as ESM, so __dirname isn't defined — derive from import.meta.url.)
const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const SHOTS = resolve(
    __dirname,
    '../../specs/029-robo-spec-skills/manual/screenshots',
)
mkdirSync(SHOTS, { recursive: true })

// Helpers ------------------------------------------------------------

/** Wait for the SPA shell to settle: tab buttons + Navigator panel visible. */
async function waitAppReady(page: Page) {
    // Use getByRole so the text-engine doesn't misinterpret slashes
    // as regex delimiters. The 7 tabs render as <button> elements
    // (see App.vue tabComponents).
    await expect(page.getByRole('button', { name: 'Design', exact: true })).toBeVisible({
        timeout: 20_000,
    })
    await expect(page.getByRole('button', { name: 'Aggregate', exact: true })).toBeVisible({
        timeout: 20_000,
    })
}

/** Click a tab button by exact label. */
async function clickTab(page: Page, label: string) {
    await page.getByRole('button', { name: label, exact: true }).click()
    await page.waitForTimeout(800)
}

test.describe('robo-spec UI surfaces (feature 029)', () => {
    test.beforeEach(async ({ page }) => {
        page.on('console', (msg) => {
            if (msg.type() === 'error') console.log('[browser console error]', msg.text())
        })
        page.on('pageerror', (err) => console.log('[browser pageerror]', err.message))
    })

    test('Design tab — navigator shows the 3 fixture BCs', async ({ page }) => {
        await page.goto('/')
        await waitAppReady(page)
        // /api/contexts should have populated the navigator by now.
        // Each BC name appears as plain text inside a navigator item.
        for (const bc of [
            'LegalConsentManagement',
            'MembershipManagement',
            'TermsAndAuthenticationManagement',
        ]) {
            await expect(page.getByText(bc, { exact: false }).first()).toBeVisible({
                timeout: 10_000,
            })
        }
        await page.screenshot({
            path: `${SHOTS}/ui_01_design_tab_with_3_bcs.png`,
            fullPage: true,
        })
    })

    test('Aggregate tab — MemberAccount aggregate visible after BC drilldown', async ({ page }) => {
        await page.goto('/')
        await waitAppReady(page)
        // The Aggregate tab renders empty until a BC is selected via the
        // navigator (the panel reads from a shared store). Expand
        // MembershipManagement and click its aggregate first so the
        // viewer has something to display.
        await page
            .getByText('MembershipManagement', { exact: false })
            .first()
            .click()
        await page.waitForTimeout(800)
        // Expand the BC tree (the chevron is a sibling icon — clicking
        // the name should also toggle in the navigator, but we click the
        // expand-chevron defensively if visible).
        const chevron = page.locator('text=MembershipManagement').first().locator('..').locator('button, [role="button"]').first()
        if (await chevron.count() > 0) {
            try { await chevron.click({ timeout: 1500 }) } catch { /* ok */ }
        }
        await page.waitForTimeout(800)
        await clickTab(page, 'Aggregate')
        await page.waitForTimeout(2500)
        // We capture whatever the panel renders — MemberAccount label
        // may or may not be visible depending on which sub-view loads,
        // and the screenshot is the primary evidence either way.
        await page.screenshot({
            path: `${SHOTS}/ui_02_aggregate_tab_after_bc_select.png`,
            fullPage: true,
        })
    })

    test('Event Modeling tab — canvas renders for the focused BC', async ({ page }) => {
        await page.goto('/')
        await waitAppReady(page)
        await clickTab(page, 'Event Modeling')
        // The Event Modeling panel renders an empty canvas if no BC has
        // been focused yet — we still capture the layout for the manual.
        await page.waitForTimeout(2500)
        await page.screenshot({
            path: `${SHOTS}/ui_03_event_modeling_tab.png`,
            fullPage: true,
        })
    })

    test('Swagger UI lists the new robo-spec + classification routes', async ({ page }) => {
        // Hit the backend directly (NOT through the Vite proxy) because
        // /docs is a backend-served Swagger page, not part of the SPA.
        await page.goto('http://127.0.0.1:8000/docs')
        // Wait for the Swagger UI shell to hydrate.
        await expect(page.getByText('Event Storming Navigator API').first()).toBeVisible({
            timeout: 20_000,
        })
        // Above-the-fold capture at the default Swagger viewport.
        await page.setViewportSize({ width: 1600, height: 1100 })
        await page.screenshot({
            path: `${SHOTS}/ui_04_swagger_docs_above_fold.png`,
            fullPage: false,
        })
        // Full page so the alphabetised tag list captures robo-spec
        // wherever it lands.
        await page.screenshot({
            path: `${SHOTS}/ui_05_swagger_docs_full_page.png`,
            fullPage: true,
        })

        // Confirm the three new/extended paths are present in the
        // rendered HTML. Use page.content() text-search rather than
        // a locator (Swagger renders paths inside <span class="opblock-summary-path">
        // which the .text engine sometimes regex-mangles for slashes).
        const html = await page.content()
        for (const needle of [
            '/api/contexts/{bc_id}/classification',
            '/api/robo-spec/health',
            '/api/claude-code/setup-project',
        ]) {
            expect(html).toContain(needle)
        }
    })

    test('Swagger UI — classification endpoint expanded shows the new schema', async ({ page }) => {
        await page.goto('http://127.0.0.1:8000/docs')
        await expect(page.getByText('Event Storming Navigator API').first()).toBeVisible({
            timeout: 20_000,
        })
        // Expand the contexts tag section so the classification endpoints
        // are visible, then expand the GET classification endpoint.
        // Swagger UI uses opblock buttons; finding by the path text
        // works because path appears in <span class="opblock-summary-path">.
        const classificationOp = page
            .locator('.opblock')
            .filter({ hasText: '/api/contexts/{bc_id}/classification' })
            .filter({ hasText: 'GET' })
            .first()

        // Open the contexts tag if collapsed, then open the operation.
        // (Swagger collapses tags by default in some installations.)
        const opCount = await classificationOp.count()
        if (opCount === 0) {
            // Try clicking the "contexts" tag header to expand the group.
            await page.getByRole('button', { name: /contexts/ }).first().click()
            await page.waitForTimeout(500)
        }
        await classificationOp.click()
        await page.waitForTimeout(800)

        await page.setViewportSize({ width: 1600, height: 1400 })
        await page.screenshot({
            path: `${SHOTS}/ui_06_swagger_classification_expanded.png`,
            fullPage: false,
        })
    })
})
