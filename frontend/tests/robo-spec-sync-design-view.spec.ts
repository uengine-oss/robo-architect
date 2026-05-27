/**
 * One-off capture: drive the SPA to a state that shows MemberAccount
 * and its properties (with the new `email` field from /robo-sync) in
 * the Aggregate Design view.
 *
 * Strategy: expand MembershipManagement in the navigator, then click
 * MemberAccount to focus it. Try multiple interaction patterns until
 * the property list renders.
 */
import { test, expect, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const SHOTS = resolve(__dirname, '../../specs/029-robo-spec-skills/manual/screenshots')
mkdirSync(SHOTS, { recursive: true })

test('show MemberAccount + email in SPA Design view', async ({ page }) => {
    test.setTimeout(90_000)
    await page.goto('/')
    await expect(page.getByRole('button', { name: 'Design', exact: true })).toBeVisible({
        timeout: 20_000,
    })
    // Click MembershipManagement to expand
    await page.getByText('MembershipManagement', { exact: false }).first().click()
    await page.waitForTimeout(1500)
    // Click the MemberAccount label inside the expanded navigator —
    // hopefully this either selects it on the canvas or opens the
    // Inspector panel.
    const memberAcct = page.getByText('MemberAccount', { exact: false }).first()
    if (await memberAcct.isVisible().catch(() => false)) {
        await memberAcct.click().catch(() => {})
    }
    await page.waitForTimeout(2000)

    // Try double-click — many navigator items in this SPA require
    // double-click to focus.
    await memberAcct.dblclick().catch(() => {})
    await page.waitForTimeout(2000)

    // Capture whatever state we're in.
    await page.screenshot({
        path: `${SHOTS}/sync_06_design_view_after_sync.png`,
        fullPage: false,
    })

    // Now switch to Aggregate tab and try drag → drop the aggregate.
    await page.getByRole('button', { name: 'Aggregate', exact: true }).click()
    await page.waitForTimeout(2000)
    // Click on MemberAccount in the navigator (which already auto-expanded).
    const memberInAgg = page.getByText('MemberAccount', { exact: false }).first()
    if (await memberInAgg.isVisible().catch(() => false)) {
        // Try double-click to load.
        await memberInAgg.dblclick().catch(() => {})
        await page.waitForTimeout(2500)
    }
    await page.screenshot({
        path: `${SHOTS}/sync_07_aggregate_panel_after_sync.png`,
        fullPage: false,
    })

    // Last try: check if `email` shows up anywhere on the page now.
    const emailCount = await page.getByText('email', { exact: false }).count()
    console.log('[sync-after] elements containing "email":', emailCount)
})
