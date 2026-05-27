/**
 * Navigator drill-down for ImplementationFile (feature 029).
 *
 * Verifies:
 *   1. Backend /full-tree returns implementationFiles[] on Aggregate/etc.
 *   2. TreeNode renders each file as a leaf with a language-aware icon (TS).
 *   3. Clicking the file leaf opens the InspectorPanel in source-viewer mode
 *      (reuses Claude Code's FileEditorPane), and the file's contents render
 *      in the CodeMirror editor.
 *
 * Captures (under specs/029-robo-spec-skills/manual/screenshots):
 *   navfile_01_navigator_drilled.png — Aggregate expanded showing TS file
 *   navfile_02_inspector_source.png  — Inspector showing source code
 */
import { test, expect, type Page } from '@playwright/test'
import {
    existsSync, mkdirSync, writeFileSync,
} from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const SHOTS = resolve(__dirname, '../../specs/029-robo-spec-skills/manual/screenshots')
mkdirSync(SHOTS, { recursive: true })

const TEST_PROJECT = '/tmp/robo-spec-navfile-test'
const LEGAL_BC_ID = 'c49c694f-6c5d-463c-9a4f-bd9a63d10ff8'
const LEGAL_BC_NAME = 'LegalConsentManagement'
// Display name in the navigator (terminology store applies the ubiquitous
// language label — Korean for this project). The backend reports the raw
// 'LegalGuardianConsent' but the navigator shows the translated form.
const AGG_NAME = 'LegalGuardianConsent'
const AGG_DISPLAY = '법정대리인 동의'
const ENTITY_FILE = 'LegalGuardianConsent.ts'

async function shot(page: Page, name: string) {
    await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false })
}

async function runWizard(page: Page) {
    await page.getByRole('button', { name: '프로젝트 홈 생성', exact: true }).click()
    await expect(page.locator('.modal-footer .btn.btn-primary').filter({ hasText: 'Next' }).first())
        .toBeVisible({ timeout: 10_000 })
    await page.locator('.modal-footer .btn.btn-primary').filter({ hasText: 'Next' }).first().click()
    await expect(page.locator('.complete-step').first()).toBeVisible({ timeout: 5_000 })
    await page.locator('input.form-input').first().fill(TEST_PROJECT)
    await page.locator('.complete-step .btn.btn-claude').first().click()
    await expect(page.locator('.complete-step').filter({ hasText: /설정 완료/ }).first())
        .toBeVisible({ timeout: 60_000 })
    await page.locator('.btn.btn-claude').filter({ hasText: /Claude Code 터미널 열기/ }).first().click()
    await expect(page.locator('.terminal-container').first()).toBeVisible({ timeout: 10_000 })
}

async function clickTreeName(page: Page, name: string) {
    const esc = name.replace(/"/g, '\\"')
    // The Design navigator (not the file-tree pane) labels nodes with
    // .tree-node__label. The label often includes a suffix like
    // " (core)" for classified BCs, so use a regex prefix match.
    const node = page
        .locator('.tree-node__label')
        .filter({ hasText: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:\\s|$|\\()`) })
        .first()
    await node.waitFor({ state: 'visible', timeout: 15_000 })
    await node.click()
    await page.waitForTimeout(500)
}

test.describe('Navigator → ImplementationFile drill-down', () => {
    test.setTimeout(180_000)

    test.beforeAll(() => {
        // Stub the source file so the inspector has something to render.
        const entityPath = `${TEST_PROJECT}/src/legal-consent-management/entities`
        mkdirSync(entityPath, { recursive: true })
        const filePath = `${entityPath}/${ENTITY_FILE}`
        if (!existsSync(filePath)) {
            writeFileSync(filePath, [
                '/**',
                ' * LegalGuardianConsent — aggregate root for legal-consent-management BC.',
                ' * Scaffolded by /robo-implement from the live design graph.',
                ' */',
                'export class LegalGuardianConsent {',
                '  // TODO: invariants',
                '  constructor(',
                '    public readonly id: string,',
                '    public consentDocument: object,',
                '    public consentStatus: string,',
                '    public consentType: string,',
                '    public legalGuardianContact: string,',
                '    public legalGuardianId: string,',
                '    public legalGuardianName: string,',
                '    public legalGuardianRelationship: string,',
                '    public memberId: string,',
                '  ) {}',
                '}',
                '',
            ].join('\n'))
        }
    })

    test('Aggregate drill-down shows TS file and inspector renders source', async ({ page }) => {
        page.on('console', m => {
            if (m.type() === 'error') console.log('[console]', m.text())
        })

        // Sanity — backend returns implementationFiles[].
        const tree = await (await page.request.get(
            `http://127.0.0.1:8000/api/contexts/${LEGAL_BC_ID}/full-tree`,
        )).json()
        const agg = tree.aggregates.find((a: any) => a.name === AGG_NAME)
        const files = (agg?.implementationFiles || []) as Array<{ path: string }>
        console.log('[graph files]', files.map(f => f.path))
        expect(files.some(f => f.path.endsWith(ENTITY_FILE))).toBe(true)

        // Open SPA, run the wizard so claudeCodeWorkdir is set, then return to Design tab.
        await page.goto('/')
        await runWizard(page)

        // Switch back to Design tab so the navigator becomes visible.
        await page.locator('.top-bar').getByText('Design', { exact: true }).first().click()
        await page.waitForTimeout(1500)

        // Drill: BC → Aggregate (clicking each tree name toggles expansion).
        // The BC label is suffixed with " (supporting)"/(core)/(generic), and
        // aggregates display the ubiquitous-language translation if enabled.
        await clickTreeName(page, LEGAL_BC_NAME)
        await clickTreeName(page, AGG_DISPLAY)
        await page.waitForTimeout(400)
        await shot(page, 'navfile_01_navigator_drilled')

        // The .ts file leaf should now be visible under the aggregate.
        const fileLeaf = page
            .locator('.tree-node__label')
            .filter({ hasText: ENTITY_FILE })
            .first()
        await fileLeaf.waitFor({ state: 'visible', timeout: 10_000 })

        // Click → inspector should switch to source-viewer mode.
        await fileLeaf.click()
        await page.waitForTimeout(1200)

        // The inspector's impl-file body should be present and the CodeMirror
        // editor inside it should have rendered some content.
        const implViewer = page.locator('.inspector-impl-file').first()
        await expect(implViewer).toBeVisible({ timeout: 10_000 })

        const cmContent = page.locator('.inspector-impl-file .cm-content').first()
        await expect(cmContent).toBeVisible({ timeout: 10_000 })
        const source = (await cmContent.textContent()) || ''
        console.log('[editor first 80]', source.slice(0, 80))
        expect(source).toContain('LegalGuardianConsent')

        await shot(page, 'navfile_02_inspector_source')
    })
})
