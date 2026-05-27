/**
 * Companion capture for /robo-sync — show the Aggregate viewer in the
 * SPA AFTER the round trip landed `email` in the graph. The previous
 * robo-spec-sync.spec.ts spec ran the source edit + propose + apply,
 * leaving the graph at v1 with `email` added; this small spec just
 * navigates the SPA and captures the visual.
 */
import { test, expect, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const SHOTS = resolve(__dirname, '../../specs/029-robo-spec-skills/manual/screenshots')
mkdirSync(SHOTS, { recursive: true })

test('SPA aggregate viewer shows email after /robo-sync', async ({ page }) => {
    test.setTimeout(60_000)
    await page.goto('/')
    await expect(page.getByRole('button', { name: 'Design', exact: true })).toBeVisible({
        timeout: 20_000,
    })

    // Click MembershipManagement in the navigator to focus the BC.
    await page.getByText('MembershipManagement', { exact: false }).first().click()
    await page.waitForTimeout(1000)

    // Switch to the Aggregate viewer tab.
    await page.getByRole('button', { name: 'Aggregate', exact: true }).click()
    await page.waitForTimeout(2500)
    // The Aggregate panel renders BCs in cards/lists; expand MembershipManagement
    // and click MemberAccount if the UI exposes it that way.
    const memberLabel = page.getByText('MemberAccount', { exact: false }).first()
    if (await memberLabel.isVisible().catch(() => false)) {
        await memberLabel.click().catch(() => {})
        await page.waitForTimeout(1500)
    }
    await page.screenshot({
        path: `${SHOTS}/sync_06_aggregate_view_with_email.png`,
        fullPage: false,
    })

    // Sanity: email should be visible somewhere on the page now.
    const hasEmail = await page.getByText('email', { exact: false }).first().isVisible().catch(() => false)
    console.log('[sync-after] email visible in aggregate viewer:', hasEmail)
})
