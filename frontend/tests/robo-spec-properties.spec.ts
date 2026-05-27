/**
 * Properties round-trip test (feature 029 — bug-fix verification).
 *
 * Validates the two bugs the user reported in the LegalConsentManagement
 * /robo-implement run:
 *
 *   1. get_bc_design used to NOT return `properties[]`; now it does.
 *   2. robo-implement/SKILL.md used to scaffold an empty
 *      `constructor(public readonly id: string) {}` stub; now it
 *      reads `properties[]` from the live graph and scaffolds one
 *      constructor parameter per real property (with the right
 *      `readonly` modifier on isKey-marked fields).
 *
 * The test drives a fresh workspace through the full chain
 * (/robo-plan + /robo-tasks + /robo-implement) for the
 * LegalConsentManagement BC, then asserts the scaffolded
 * `LegalGuardianConsent.ts` contains EVERY property the graph has
 * (9 of them, not just `id`).
 *
 * Captures:
 *   props_01_initial_empty.png         — fresh workspace shell before any /robo-* run
 *   props_02_scaffold_with_all_fields.png — final state with the populated source file open in the editor pane
 *   props_99_summary.json              — machine-readable summary including the property-count diff
 */
import { test, expect, type Page } from '@playwright/test'
import { execSync } from 'node:child_process'
import {
    existsSync, mkdirSync, readFileSync, rmSync, writeFileSync,
} from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const SHOTS = resolve(__dirname, '../../specs/029-robo-spec-skills/manual/screenshots')
mkdirSync(SHOTS, { recursive: true })

const TEST_PROJECT = '/tmp/robo-spec-properties-test'

// Graph state the test asserts against — these MUST stay in sync with
// what /api/contexts/{bc_id}/full-tree currently reports for
// LegalConsentManagement. If the graph schema for the fixture changes,
// update this expectation.
const LEGAL_BC_ID = 'c49c694f-6c5d-463c-9a4f-bd9a63d10ff8'
const EXPECTED_LGC_PROPERTIES = [
    'consentDocument',
    'consentStatus',
    'consentType',
    'id',
    'legalGuardianContact',
    'legalGuardianId',
    'legalGuardianName',
    'legalGuardianRelationship',
    'memberId',
]

async function shot(page: Page, name: string) {
    await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false })
}

async function typeIntoTerminal(page: Page, text: string, opts: { delay?: number } = {}) {
    const viewport = page.locator('.terminal-container .xterm-screen').first()
    await viewport.click()
    await page.waitForTimeout(300)
    await page.locator('.terminal-container .xterm-helper-textarea').first().focus().catch(() => {})
    await page.keyboard.type(text, { delay: opts.delay ?? 40 })
    await page.waitForTimeout(200)
    await page.keyboard.press('Enter')
}

async function openFileInTree(page: Page, segments: string[]) {
    const esc = (s: string) => s.replace(/"/g, '\\"')
    const exact = (n: string) => page.locator(`.tree-name:text-is("${esc(n)}")`).first()
    for (let i = 0; i < segments.length - 1; i += 1) {
        const seg = segments[i]
        const child = segments[i + 1]
        const childVisible = await exact(child).isVisible().catch(() => false)
        if (childVisible) continue
        const nameSpan = exact(seg)
        await nameSpan.waitFor({ state: 'visible', timeout: 15_000 })
        await nameSpan.click()
        await page.waitForTimeout(700)
    }
    const file = segments[segments.length - 1]
    await exact(file).waitFor({ state: 'visible', timeout: 15_000 })
    await exact(file).click()
    await page.waitForTimeout(1500)
}

async function refreshFileTree(page: Page) {
    await page.locator('.file-tree-pane .tree-refresh').first().click().catch(() => {})
    await page.waitForTimeout(600)
}

test.describe('Properties round-trip — /robo-implement uses graph properties', () => {
    test.setTimeout(900_000) // 15 min: full /robo-plan + /robo-tasks + /robo-implement chain

    test.beforeAll(() => {
        // Fresh workspace — no leftover plan/tasks/src from prior runs.
        try { rmSync(TEST_PROJECT, { recursive: true, force: true }) } catch {}
        mkdirSync(TEST_PROJECT, { recursive: true })
    })

    test('LegalGuardianConsent scaffolds with all 9 graph properties', async ({ page }) => {
        page.on('console', m => { if (m.type() === 'error') console.log('[console]', m.text()) })

        // Sanity: graph really has 9 properties for LegalGuardianConsent.
        const graphResp = await (await page.request.get(
            `http://127.0.0.1:8000/api/contexts/${LEGAL_BC_ID}/full-tree`,
        )).json()
        const graphAgg = graphResp.aggregates.find((a: any) => a.name === 'LegalGuardianConsent')
        const graphPropNames = (graphAgg?.properties || []).map((p: any) => p.name).sort()
        console.log('[graph props]', graphPropNames)
        expect(graphPropNames).toEqual(EXPECTED_LGC_PROPERTIES)

        // ============================================================
        // 1 — Open SPA → 프로젝트 홈 생성 → robo-spec mode →
        //     /tmp/robo-spec-properties-test → Claude Code 터미널 열기
        // ============================================================
        await page.goto('/?permission_mode=bypassPermissions')
        await page.getByRole('button', { name: '프로젝트 홈 생성', exact: true }).click()
        await expect(page.getByText('프로젝트 홈 생성').first()).toBeVisible({ timeout: 10_000 })
        await page.locator('.modal-footer .btn.btn-primary').filter({ hasText: 'Next' }).first().click()
        await expect(page.locator('.complete-step').first()).toBeVisible({ timeout: 5_000 })
        await page.locator('input.form-input').first().fill(TEST_PROJECT)
        await page.locator('.complete-step .btn.btn-claude').first().click()
        await expect(page.locator('.complete-step').filter({ hasText: /설정 완료/ }).first())
            .toBeVisible({ timeout: 60_000 })
        await page.locator('.btn.btn-claude').filter({ hasText: /Claude Code 터미널 열기/ }).first().click()
        await expect(page.locator('.terminal-container').first()).toBeVisible({ timeout: 10_000 })
        await page.waitForTimeout(8_000)
        await shot(page, 'props_01_initial_empty')

        // Brand new workspaces show claude's "Quick safety check / trust
        // this folder" gate before any slash command works. The
        // permission_mode=bypassPermissions query param only affects
        // per-TOOL prompts, not the workspace-TRUST gate. Press Enter
        // once to accept the default ("Yes, I trust this folder").
        // If no trust prompt is showing this Enter goes into claude's
        // empty input prompt and claude ignores it.
        const viewport = page.locator('.terminal-container .xterm-screen').first()
        await viewport.click()
        await page.waitForTimeout(300)
        await page.locator('.terminal-container .xterm-helper-textarea').first().focus().catch(() => {})
        await page.keyboard.press('Enter')
        await page.waitForTimeout(5_000)

        // ============================================================
        // 2 — /robo-plan LegalConsentManagement
        // ============================================================
        await typeIntoTerminal(
            page,
            '/robo-plan LegalConsentManagement — if no classification, treat as core and persist via set_bc_classification',
        )
        const planDeadline = Date.now() + 240_000
        let planPath = ''
        while (Date.now() < planDeadline) {
            planPath = execSync(
                `find ${TEST_PROJECT}/specs -name plan.md -type f 2>/dev/null | head -1`,
                { encoding: 'utf-8' },
            ).trim()
            if (planPath) break
            await page.waitForTimeout(4_000)
        }
        expect(planPath).toBeTruthy()
        console.log('[plan.md]', planPath)
        await page.waitForTimeout(8_000)

        // ============================================================
        // 3 — /robo-tasks
        // ============================================================
        await typeIntoTerminal(page, '/robo-tasks')
        const tasksDeadline = Date.now() + 180_000
        let tasksPath = ''
        while (Date.now() < tasksDeadline) {
            tasksPath = execSync(
                `find ${TEST_PROJECT}/specs -name tasks.md -type f 2>/dev/null | head -1`,
                { encoding: 'utf-8' },
            ).trim()
            if (tasksPath) {
                const len = parseInt(execSync(`wc -c < "${tasksPath}"`, { encoding: 'utf-8' }).trim(), 10)
                if (len > 800) break
            }
            await page.waitForTimeout(4_000)
        }
        expect(tasksPath).toBeTruthy()
        console.log('[tasks.md]', tasksPath)
        await page.waitForTimeout(8_000)

        // ============================================================
        // 4 — /robo-implement scoped to LegalGuardianConsent entity only
        // ============================================================
        await typeIntoTerminal(
            page,
            '/robo-implement — ONLY scaffold the LegalGuardianConsent aggregate entity file (one file under entities/). Per the SKILL.md, you MUST call get_bc_design once first to fetch the live property list, and the scaffolded class MUST include every property the graph reports as a constructor parameter — do NOT emit an empty `constructor(public readonly id: string)` stub. Skip every other task except the LegalGuardianConsent entity scaffold.',
        )

        // Wait for the LegalGuardianConsent.ts file to appear.
        const lgcDeadline = Date.now() + 360_000
        let lgcPath = ''
        while (Date.now() < lgcDeadline) {
            lgcPath = execSync(
                `find ${TEST_PROJECT}/src -name 'LegalGuardianConsent.ts' -type f 2>/dev/null | head -1`,
                { encoding: 'utf-8' },
            ).trim()
            if (lgcPath) {
                // Wait until it's "settled" — at least 400 bytes
                const size = parseInt(execSync(`wc -c < "${lgcPath}"`, { encoding: 'utf-8' }).trim(), 10)
                if (size > 400) break
            }
            await page.waitForTimeout(5_000)
        }
        expect(lgcPath).toBeTruthy()
        console.log('[lgcPath]', lgcPath)
        await page.waitForTimeout(15_000)  // give claude time to register & tick checkbox

        // ============================================================
        // 5 — The critical assertion: does the file contain ALL 9 graph
        //     properties? Not just `id`?
        // ============================================================
        const lgcSource = readFileSync(lgcPath, 'utf-8')
        console.log('[LegalGuardianConsent.ts]\n' + lgcSource)
        const missing = EXPECTED_LGC_PROPERTIES.filter((p) => !lgcSource.includes(p))
        console.log('[missing properties]', missing)

        // Soft assertion first — capture the file in the editor regardless.
        await refreshFileTree(page)
        const relSegs = lgcPath.replace(`${TEST_PROJECT}/`, '').split('/')
        await openFileInTree(page, relSegs)
        await shot(page, 'props_02_scaffold_with_all_fields')

        // Summary
        const presentProps = EXPECTED_LGC_PROPERTIES.filter((p) => lgcSource.includes(p))
        const summary = {
            workspace: TEST_PROJECT,
            bc: 'LegalConsentManagement',
            aggregate: 'LegalGuardianConsent',
            graphPropertyCount: EXPECTED_LGC_PROPERTIES.length,
            graphProperties: EXPECTED_LGC_PROPERTIES,
            scaffoldedFilePath: lgcPath,
            scaffoldedFileBytes: lgcSource.length,
            propertiesPresentInScaffold: presentProps,
            propertiesMissingFromScaffold: missing,
            allPropertiesScaffolded: missing.length === 0,
        }
        writeFileSync(
            `${SHOTS}/props_99_summary.json`,
            JSON.stringify(summary, null, 2),
        )
        console.log('[summary]', JSON.stringify(summary, null, 2))

        // Hard assertion last so a failure still leaves the captures
        // and the summary file behind for the manual.
        expect(missing).toEqual([])
    })
})
