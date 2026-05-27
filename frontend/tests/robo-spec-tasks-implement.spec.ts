/**
 * Robo Spec Skills (feature 029) — manual part 2: continue from a
 * project home that's already been set up, and drive /robo-tasks and a
 * SCOPED /robo-implement (just the MemberAccount aggregate, not the
 * whole BC) in the embedded Claude Code terminal.
 *
 * What this spec captures:
 *
 *   part2_01_plan_md_in_editor.png        plan.md from /robo-plan, opened in the file-editor pane via a click on the file tree
 *   part2_02_robo_tasks_running.png       /robo-tasks typed into the embedded terminal; claude is mid-generation
 *   part2_03_tasks_md_initial.png         tasks.md opened in the editor — all checkboxes still [ ], @robo markers visible
 *   part2_04_robo_implement_running.png   /robo-implement typed with scope = MemberAccount aggregate only; claude scaffolding
 *   part2_05_tasks_md_checked.png         tasks.md re-opened after /robo-implement — checkboxes now [x]
 *   part2_06_member_account_source.png    src/membership-management/entities/MemberAccount.ts opened in the editor pane
 *
 * This spec is self-contained: it re-runs setup-project (idempotent) so
 * it can run from a clean checkout. Earlier captures (steps 1–7 of the
 * companion manual) cover the PRD wizard and the /robo-plan terminal
 * round trip; this one focuses on what comes after.
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

const TEST_PROJECT = '/tmp/robo-spec-real-flow'

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

/** Click into the file tree to open a path like "specs/001-membership-management/plan.md".
 *  IMPORTANT: clicking a folder row in this tree TOGGLES expand state.
 *  Re-running openFileInTree on the same parents would collapse them
 *  and then time out waiting for the child. So we click a parent only
 *  if the *next* segment is not already visible — idempotent navigation.
 *  We use exact text match (`:text-is`) because substring matches
 *  silently confuse e.g. "membership-management" with the spec slug
 *  "001-membership-management".
 */
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
    const fileNameSpan = exact(file)
    await fileNameSpan.waitFor({ state: 'visible', timeout: 15_000 })
    await fileNameSpan.click()
    // Editor mount + content load.
    await page.waitForTimeout(1500)
}

async function refreshFileTree(page: Page) {
    // Click the small refresh icon in the tree header.
    const btn = page.locator('.file-tree-pane .tree-refresh').first()
    await btn.click().catch(() => {})
    await page.waitForTimeout(600)
}

test.describe('Manual part 2 — /robo-tasks → scoped /robo-implement in embedded terminal', () => {
    test.setTimeout(720_000) // 12 min budget — three terminal round-trips

    test.beforeAll(() => {
        // Do NOT wipe specs/ — the user's intent is "continue from the
        // existing project home". If plan.md already exists from a
        // previous run, we re-use it (the test detects and skips
        // /robo-plan). We DO wipe src/ and tasks.md so the
        // /robo-tasks and /robo-implement captures show artifacts
        // being created, not just present.
        try { rmSync(`${TEST_PROJECT}/src`, { recursive: true, force: true }) } catch {}
        try {
            const tasksPath = execSync(
                `find ${TEST_PROJECT}/specs -name tasks.md -type f 2>/dev/null | head -1`,
                { encoding: 'utf-8' },
            ).trim()
            if (tasksPath) rmSync(tasksPath)
        } catch {}
        mkdirSync(TEST_PROJECT, { recursive: true })
    })

    test('continue: tasks + scoped implement', async ({ page }) => {
        page.on('console', m => { if (m.type() === 'error') console.log('[console]', m.text()) })
        page.on('pageerror', e => console.log('[pageerror]', e.message))

        const memberBcId = '24fa4636-6a5c-493a-8cfa-a08833e245eb'

        // ============================================================
        // Pre-flight — make sure setup is in place (idempotent install).
        // We re-run setup-project via the wizard so the test is
        // independently runnable. Skill files and .mcp.json are
        // re-copied (byte-identical) and robo-project.json is preserved.
        // ============================================================
        await page.goto('/?permission_mode=bypassPermissions')
        await expect(page.getByRole('button', { name: '프로젝트 홈 생성', exact: true })).toBeVisible({
            timeout: 20_000,
        })
        await page.getByRole('button', { name: '프로젝트 홈 생성', exact: true }).click()
        await expect(page.getByText('프로젝트 홈 생성').first()).toBeVisible({ timeout: 10_000 })
        // Robo-spec is the default; click Next → step 3 directly.
        await page.locator('.modal-footer .btn.btn-primary').filter({ hasText: 'Next' }).first().click()
        await expect(page.locator('.complete-step').first()).toBeVisible({ timeout: 5_000 })
        await page.locator('input.form-input').first().fill(TEST_PROJECT)
        await page.locator('.complete-step .btn.btn-claude').first().click()
        await expect(page.locator('.complete-step').filter({ hasText: /설정 완료/ }).first())
            .toBeVisible({ timeout: 60_000 })
        // Sanity — install is present.
        for (const s of ['robo-plan', 'robo-tasks', 'robo-implement', 'robo-sync',
                          'speckit-plan', 'speckit-tasks', 'speckit-implement']) {
            expect(existsSync(`${TEST_PROJECT}/.claude/skills/${s}/SKILL.md`)).toBe(true)
        }
        // Click into the Claude Code tab.
        await page.locator('.btn.btn-claude').filter({ hasText: /Claude Code 터미널 열기/ }).first().click()
        await expect(page.locator('.terminal-container').first()).toBeVisible({ timeout: 10_000 })
        await page.waitForTimeout(8_000)

        // ============================================================
        // 1 — Ensure plan.md exists. If a previous run left it in
        //     place (the workspace persists across spec runs), reuse
        //     it; otherwise drive /robo-plan to produce one.
        // ============================================================
        let planPath = execSync(
            `find ${TEST_PROJECT}/specs -name plan.md -type f 2>/dev/null | head -1`,
            { encoding: 'utf-8' },
        ).trim()
        if (!planPath) {
            await typeIntoTerminal(
                page,
                '/robo-plan MembershipManagement — if no classification, treat as core and persist via set_bc_classification',
            )
            const planDeadline = Date.now() + 240_000
            while (Date.now() < planDeadline) {
                planPath = execSync(
                    `find ${TEST_PROJECT}/specs -name plan.md -type f 2>/dev/null | head -1`,
                    { encoding: 'utf-8' },
                ).trim()
                if (planPath) break
                await page.waitForTimeout(4_000)
            }
            await page.waitForTimeout(8_000)
        } else {
            console.log('[part2] reusing existing plan.md at', planPath)
        }
        expect(planPath).toBeTruthy()

        // ============================================================
        // 2 — Click into the file tree to open plan.md in the editor
        // ============================================================
        await refreshFileTree(page)
        await openFileInTree(page, ['specs', '001-membership-management', 'plan.md'])
        await shot(page, 'part2_01_plan_md_in_editor')

        // ============================================================
        // 3 — Drive /robo-tasks (or reuse existing tasks.md from a
        //     previous run if it's already there)
        // ============================================================
        let tasksPath = execSync(
            `find ${TEST_PROJECT}/specs -name tasks.md -type f 2>/dev/null | head -1`,
            { encoding: 'utf-8' },
        ).trim()
        if (!tasksPath) {
            await typeIntoTerminal(page, '/robo-tasks')
            // Capture mid-generation
            await page.waitForTimeout(15_000)
            await shot(page, 'part2_02_robo_tasks_running')
            const tasksDeadline = Date.now() + 180_000
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
            await page.waitForTimeout(8_000)
        } else {
            console.log('[part2] reusing existing tasks.md at', tasksPath)
        }
        expect(tasksPath).toBeTruthy()

        // ============================================================
        // 4 — Open tasks.md in the editor — captures the INITIAL state
        //     with all checkboxes [ ] unchecked and @robo markers visible
        // ============================================================
        await refreshFileTree(page)
        await openFileInTree(page, ['specs', '001-membership-management', 'tasks.md'])
        // Verify @robo marker actually present in the file on disk.
        const tasksInitial = readFileSync(tasksPath, 'utf-8')
        expect(tasksInitial).toMatch(/<!-- @robo elementId=/)
        // Most tasks should be unchecked at this point.
        const uncheckedCount = (tasksInitial.match(/^- \[ \] /gm) || []).length
        expect(uncheckedCount).toBeGreaterThan(0)
        await shot(page, 'part2_03_tasks_md_initial')

        // ============================================================
        // 5 — Drive /robo-implement with a SCOPE CONSTRAINT — only the
        //     MemberAccount aggregate entity, not the whole BC. We type
        //     the scope hint as part of the prompt so claude limits its
        //     work to a single aggregate's primary entity file. This
        //     keeps the test fast and produces a visible partial
        //     scaffold (some checkboxes flipped, others still [ ]).
        // ============================================================
        await typeIntoTerminal(
            page,
            '/robo-implement — ONLY scaffold the MemberAccount aggregate entity file (one file under entities/). Do not scaffold any usecases, interface_adapters, frameworks_and_drivers, or repository files. Skip Phase 1 setup tasks except the entities/ directory. Stop after the aggregate entity is created and its @robo marker is ticked.',
        )
        // Capture mid-execution (claude reading the spec + thinking).
        await page.waitForTimeout(20_000)
        await shot(page, 'part2_04_robo_implement_running')

        // Wait for the MemberAccount.ts file to appear.
        const memberDeadline = Date.now() + 240_000
        let memberPath = ''
        while (Date.now() < memberDeadline) {
            memberPath = execSync(
                `find ${TEST_PROJECT}/src -name 'MemberAccount.ts' -type f 2>/dev/null | head -1`,
                { encoding: 'utf-8' },
            ).trim()
            if (memberPath) break
            await page.waitForTimeout(4_000)
        }
        expect(memberPath).toBeTruthy()
        // Give claude a chance to also flip the matching tasks.md checkbox.
        await page.waitForTimeout(20_000)

        // ============================================================
        // 6 — Re-open tasks.md to capture the CHECKED state
        // ============================================================
        await refreshFileTree(page)
        await openFileInTree(page, ['specs', '001-membership-management', 'tasks.md'])
        const tasksAfter = readFileSync(tasksPath, 'utf-8')
        const checkedCount = (tasksAfter.match(/^- \[x\] /gm) || []).length
        // We expect at least the MemberAccount task to be ticked.
        expect(checkedCount).toBeGreaterThan(0)
        await shot(page, 'part2_05_tasks_md_checked')

        // ============================================================
        // 7 — Open MemberAccount.ts in the editor to show the scaffolded source
        // ============================================================
        await refreshFileTree(page)
        // The path depends on the BC slug — we navigate from src/ down.
        // Derive segments from the absolute memberPath relative to TEST_PROJECT.
        const rel = memberPath.replace(`${TEST_PROJECT}/`, '')
        const segments = rel.split('/')
        await openFileInTree(page, segments)
        await shot(page, 'part2_06_member_account_source')

        // ============================================================
        // 8 — Summary
        // ============================================================
        const summary = {
            workspace: TEST_PROJECT,
            planMd: planPath,
            tasksMd: tasksPath,
            memberAccountTs: memberPath,
            tasksUncheckedInitial: uncheckedCount,
            tasksCheckedAfterImplement: checkedCount,
            constraint: 'MemberAccount aggregate entity only — Phase 2 partial scaffold',
            roboMarkersInSrc: execSync(
                `grep -rIn '@robo' ${TEST_PROJECT}/src 2>/dev/null || true`,
                { encoding: 'utf-8' },
            ).trim() || '(none — R7 enforced)',
        }
        writeFileSync(
            `${SHOTS}/part2_99_summary.json`,
            JSON.stringify(summary, null, 2),
        )
        console.log('[part2 summary]', JSON.stringify(summary, null, 2))
    })
})
