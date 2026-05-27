/**
 * Robo Spec Skills (feature 029) — /robo-sync round trip from source
 * code changes back into the Robo Architect graph.
 *
 * Scenario:
 *
 *   1. Project home already set up (Parts 1+2 left it at
 *      /tmp/robo-spec-real-flow, with `MemberAccount` scaffolded under
 *      `src/membership-management/entities/`).
 *   2. Open MemberAccount.ts in the file editor — capture BEFORE.
 *   3. Edit the file from disk (simulating a developer typing in
 *      their IDE) to add an `email: string` property to the
 *      constructor.
 *   4. Open the file again so the editor reflects the new content —
 *      capture AFTER.
 *   5. Type `/robo-sync` into the embedded Claude Code terminal.
 *      claude reads the SKILL.md, runs the AST extractor, calls
 *      MCP `propose_sync` → renders the diff → asks for confirmation
 *      (no destructive changes here, so just an add) → calls
 *      `apply_proposal` → reports the new property landed in the
 *      graph and the aggregate's version was bumped.
 *   6. Hit `GET /api/contexts/{bcId}/full-tree` directly to confirm
 *      the new property is in the graph from the HTTP surface. Save
 *      the JSON pretty-printed as a side artifact.
 *   7. Capture the Aggregate viewer in the SPA showing MemberAccount
 *      and its property list (which now includes `email`).
 *
 * Captures land under specs/029-robo-spec-skills/manual/screenshots/
 * with the `sync_` prefix.
 */
import { test, expect, type Page } from '@playwright/test'
import { execSync } from 'node:child_process'
import {
    existsSync, mkdirSync, readFileSync, writeFileSync,
} from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const SHOTS = resolve(__dirname, '../../specs/029-robo-spec-skills/manual/screenshots')
mkdirSync(SHOTS, { recursive: true })

const TEST_PROJECT = '/tmp/robo-spec-real-flow'
const MEMBER_FILE = `${TEST_PROJECT}/src/membership-management/entities/MemberAccount.ts`
const BC_ID = '24fa4636-6a5c-493a-8cfa-a08833e245eb'

// BEFORE source: matches the graph's 7 existing properties one-for-one
// so the AFTER edit (adding `email`) is a pure addition with no
// removals. This keeps the /robo-sync confirmation prompt out of the
// picture for this headless test — propose_sync produces an empty
// requiresConfirmation array and apply_proposal can run immediately.
const BEFORE_SOURCE = `export class MemberAccount {
  // TODO: invariants

  constructor(
    public readonly id: string,
    public status: string,
    public profile: object,
    public personalInformation: object,
    public identityVerification: object,
    public parentalConsent: object,
    public termsConsents: object[],
  ) {}
}
`

// AFTER source: same 7 + a new `email: string` field.
const AFTER_SOURCE = `export class MemberAccount {
  // TODO: invariants

  constructor(
    public readonly id: string,
    public readonly email: string,
    public status: string,
    public profile: object,
    public personalInformation: object,
    public identityVerification: object,
    public parentalConsent: object,
    public termsConsents: object[],
  ) {}
}
`

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

/** Idempotent file-tree navigation — see Part 2 spec for rationale. */
async function openFileInTree(page: Page, segments: string[]) {
    const escapeForSelector = (s: string) => s.replace(/"/g, '\\"')
    const exact = (name: string) =>
        page.locator(`.tree-name:text-is("${escapeForSelector(name)}")`).first()
    for (let i = 0; i < segments.length - 1; i += 1) {
        const seg = segments[i]
        const childSeg = segments[i + 1]
        const childVisible = await exact(childSeg).isVisible().catch(() => false)
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

test.describe('/robo-sync round trip — source edit → propose → apply → graph', () => {
    test.setTimeout(420_000)

    test.beforeAll(() => {
        // Ensure the test project is in the "post-Part-2" state. We
        // restore MemberAccount.ts to a form that EXACTLY mirrors the
        // graph's existing 7 properties — so when the developer later
        // adds `email`, the propose_sync diff is purely additive
        // (no destructive removals → no confirmation prompt; claude
        // can apply immediately).
        if (existsSync(MEMBER_FILE)) {
            writeFileSync(
                MEMBER_FILE,
                BEFORE_SOURCE,
            )
        }
        // Remove any `email` property left over from prior smoke runs
        // and reset MemberAccount.version to 0 so the BEFORE state is
        // canonical.
        execSync(
            `cd /Users/uengine/main-robo-arch/robo-architect && .venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
import sys; sys.path.insert(0, '.')
from api.platform.neo4j import init_neo4j_driver, get_session, close_neo4j_driver
init_neo4j_driver(log=False)
with get_session() as s:
    s.run(\\"MATCH (a:Aggregate {name:'MemberAccount'})-[:HAS_PROPERTY]->(p:Property {name:'email'}) DETACH DELETE p\\").consume()
    s.run(\\"MATCH (a:Aggregate {name:'MemberAccount'}) SET a.version = 0\\").consume()
close_neo4j_driver(log=False)
"`,
            { encoding: 'utf-8' },
        )
    })

    test('source edit propagates to graph through /robo-sync', async ({ page }) => {
        page.on('console', m => { if (m.type() === 'error') console.log('[console]', m.text()) })

        // BEFORE — verify the property is NOT yet in the graph.
        const beforeProps = await (await page.request.get(
            `http://127.0.0.1:8000/api/contexts/${BC_ID}/full-tree`,
        )).json()
        const memberAccBefore = beforeProps.aggregates.find((a: any) => a.name === 'MemberAccount')
        expect(memberAccBefore).toBeTruthy()
        const beforeNames = (memberAccBefore.properties || []).map((p: any) => p.name).sort()
        expect(beforeNames).not.toContain('email')
        console.log('[before graph props]', beforeNames)

        // ============================================================
        // 1 — Open the SPA, navigate through PRD wizard quickly to
        //     reach the Claude Code tab at our existing project path
        //     (the wizard is idempotent in robo-spec mode).
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
        await page.waitForTimeout(5_000)

        // ============================================================
        // 2 — Open MemberAccount.ts in the editor — BEFORE
        // ============================================================
        await refreshFileTree(page)
        await openFileInTree(page, ['src', 'membership-management', 'entities', 'MemberAccount.ts'])
        await shot(page, 'sync_01_source_before_edit')

        // ============================================================
        // 3 — Edit the file on disk (simulates developer typing in IDE)
        //     to add `email: string` to the constructor params,
        //     while keeping the existing 7 fields intact so the
        //     /robo-sync diff is purely additive.
        // ============================================================
        writeFileSync(MEMBER_FILE, AFTER_SOURCE)

        // Sanity-check the extractor sees the new field plus the
        // existing ones.
        const extractOut = execSync(
            `node ${TEST_PROJECT}/.claude/skills/robo-sync/extractors/ts_extract.mjs ${MEMBER_FILE}`,
            { encoding: 'utf-8' },
        )
        const extracted = JSON.parse(extractOut)
        expect(extracted.fields.map((f: any) => f.name)).toContain('email')
        expect(extracted.fields.map((f: any) => f.name)).toContain('id')

        // ============================================================
        // 4 — Re-open the file in the editor — AFTER the edit
        // ============================================================
        await refreshFileTree(page)
        await openFileInTree(page, ['src', 'membership-management', 'entities', 'MemberAccount.ts'])
        await shot(page, 'sync_02_source_after_edit')

        // ============================================================
        // 5 — /robo-sync in the embedded terminal
        // ============================================================
        await typeIntoTerminal(
            page,
            '/robo-sync MembershipManagement — run the full propose+apply round trip against the MemberAccount aggregate. The source code keeps every existing field plus a new email property, so propose_sync should return an empty requiresConfirmation array (purely additive). Apply immediately. If asked to confirm anyway, pick the "Additions only" option (1).',
        )
        // Mid-execution capture.
        await page.waitForTimeout(20_000)
        await shot(page, 'sync_03_robo_sync_running')

        // Wait for `email` to land in the graph (max 4 min).
        const deadline = Date.now() + 240_000
        let afterNames: string[] = []
        while (Date.now() < deadline) {
            const r = await page.request.get(
                `http://127.0.0.1:8000/api/contexts/${BC_ID}/full-tree`,
            )
            const data = await r.json()
            const ma = data.aggregates.find((a: any) => a.name === 'MemberAccount')
            afterNames = (ma?.properties || []).map((p: any) => p.name).sort()
            if (afterNames.includes('email')) break
            await page.waitForTimeout(4000)
        }
        expect(afterNames).toContain('email')
        console.log('[after graph props]', afterNames)

        // Give claude a moment to finish printing its summary.
        await page.waitForTimeout(10_000)
        await shot(page, 'sync_04_robo_sync_done')

        // ============================================================
        // 6 — Dump the full-tree JSON for MemberAccount so the manual
        //     has a textual proof of the graph state. Then capture
        //     the Aggregate tab to show the property visually.
        // ============================================================
        const fullTreeR = await page.request.get(
            `http://127.0.0.1:8000/api/contexts/${BC_ID}/full-tree`,
        )
        const fullTree = await fullTreeR.json()
        const memberAccAfter = fullTree.aggregates.find((a: any) => a.name === 'MemberAccount')
        writeFileSync(
            `${SHOTS}/sync_05_member_account_after_graph.json`,
            JSON.stringify(memberAccAfter, null, 2),
        )

        // Show the Aggregate viewer with MemberAccount selected.
        await page.getByRole('button', { name: 'Aggregate', exact: true }).click()
        await page.waitForTimeout(2000)
        // Navigator may need a click to load the BC's aggregates.
        const memberLabel = page.getByText('MemberAccount', { exact: false }).first()
        if (await memberLabel.isVisible().catch(() => false)) {
            await memberLabel.click().catch(() => {})
            await page.waitForTimeout(1500)
        }
        await shot(page, 'sync_06_aggregate_view_with_email')

        // Summary
        const summary = {
            file: MEMBER_FILE,
            beforeGraphProperties: beforeNames,
            afterGraphProperties: afterNames,
            newProperty: 'email',
            elementVersionAfter: memberAccAfter?.version ?? null,
            propertyCountBefore: beforeNames.length,
            propertyCountAfter: afterNames.length,
        }
        writeFileSync(
            `${SHOTS}/sync_99_summary.json`,
            JSON.stringify(summary, null, 2),
        )
        console.log('[sync summary]', JSON.stringify(summary, null, 2))
    })
})
