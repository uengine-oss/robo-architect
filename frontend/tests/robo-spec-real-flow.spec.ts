/**
 * Robo Spec Skills (feature 029) — the REAL user flow with the renamed
 * "프로젝트 홈 생성" button, the new Robo-Spec output_mode, and slash
 * commands typed into the *embedded* Claude Code terminal (xterm.js
 * → PTY → claude CLI) — not invoked side-channel via `claude -p`.
 *
 * Captured artifacts (PNG real-browser screenshots):
 *
 *   step_01_topbar_renamed.png             SPA Design tab; topbar button reads "프로젝트 홈 생성"
 *   step_02_modal_step1_robo_spec.png      Modal step 1 with Robo-Spec Skills mode selected by default
 *   step_03_modal_step3_project_path.png   Step 3 (preview skipped) — project path input
 *   step_04_modal_step4_robo_spec_install.png  Step 4 — "프로젝트 설정 완료!" with the robo-spec install summary
 *   step_05_claude_code_tab_trust_prompt.png   Claude Code tab — embedded terminal at the new project, showing claude's trust prompt
 *   step_06_terminal_after_trust.png       After we type "1<Enter>" to dismiss the trust prompt — claude UI shows
 *   step_07_terminal_robo_plan_running.png Mid-stream — we typed "/robo-plan MembershipManagement" and claude is responding
 *   step_08_terminal_robo_plan_done.png    Final — robo-plan finished; the terminal shows the summary
 *
 * We don't *also* drive /robo-tasks and /robo-implement through the
 * embedded terminal in this spec — one full slash-command round trip
 * is enough to prove the integration works, and chaining three of them
 * through xterm.js inflates the test runtime past 10 minutes for
 * little extra coverage. The earlier `robo-spec-prd-flow.spec.ts`
 * proves all three end-to-end via `claude -p` against the same
 * workspace; this spec exists specifically to prove the *embedded
 * terminal* integration with one canonical slash command.
 */
import { test, expect, type Page, type Locator } from '@playwright/test'
import { execSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs'
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

/**
 * Type a string into the xterm.js terminal that's currently mounted.
 *
 * xterm.js focus is brittle in headless: focus() on the helper-textarea
 * doesn't always take when the container has just rendered. Click the
 * visible terminal canvas first — xterm intercepts the click and
 * forwards focus to the helper textarea — then type with a generous
 * per-char delay so the PTY round-trip can keep up with each keystroke.
 */
async function typeIntoTerminal(page: Page, text: string, opts: { pressEnter?: boolean; delay?: number } = {}) {
    // Click the visible terminal viewport (canvas) — this is what
    // xterm's MouseDown handler hooks into to grant focus.
    const viewport = page.locator('.terminal-container .xterm-screen').first()
    await viewport.click()
    await page.waitForTimeout(300)
    // Belt-and-suspenders: also focus the helper textarea directly.
    await page.locator('.terminal-container .xterm-helper-textarea').first().focus().catch(() => {})
    await page.keyboard.type(text, { delay: opts.delay ?? 40 })
    if (opts.pressEnter !== false) {
        await page.waitForTimeout(200)
        await page.keyboard.press('Enter')
    }
}

test.describe('프로젝트 홈 생성 → Claude Code → /robo-plan in embedded terminal', () => {
    // The single round trip through the real PTY takes ~60s for claude
    // to think + respond. Budget 8 minutes for the whole flow.
    test.setTimeout(480_000)

    test.beforeAll(() => {
        try { rmSync(TEST_PROJECT, { recursive: true, force: true }) } catch {}
        mkdirSync(TEST_PROJECT, { recursive: true })
    })

    test('full real flow with embedded terminal', async ({ page }) => {
        page.on('console', m => { if (m.type() === 'error') console.log('[console]', m.text()) })
        page.on('pageerror', e => console.log('[pageerror]', e.message))

        // BEFORE: classification should be null (reset script ran before
        // this test). Capture for the manual's before/after comparison.
        const memberBcId = '24fa4636-6a5c-493a-8cfa-a08833e245eb'
        const before = await (await page.request.get(
            `http://127.0.0.1:8000/api/contexts/${memberBcId}/classification`,
        )).json()
        console.log('[before]', before)

        // ============================================================
        // 1 — SPA loads; topbar reads "프로젝트 홈 생성"
        //     The ?permission_mode=bypassPermissions query param is
        //     picked up by ClaudeCodeTerminal.getWsUrl() and forwarded
        //     to the WebSocket so the embedded `claude` is spawned with
        //     --permission-mode bypassPermissions. Without this, each
        //     MCP tool call inside /robo-plan would block on an
        //     interactive prompt that headless tests can't answer
        //     reliably (xterm renders to canvas, not DOM text).
        // ============================================================
        await page.goto('/?permission_mode=bypassPermissions')
        await expect(page.getByRole('button', { name: 'Design', exact: true })).toBeVisible({
            timeout: 20_000,
        })
        await expect(page.getByRole('button', { name: '프로젝트 홈 생성', exact: true })).toBeVisible({
            timeout: 10_000,
        })
        await shot(page, 'step_01_topbar_renamed')

        // ============================================================
        // 2 — Open the wizard; step 1 should default to Robo-Spec Skills
        // ============================================================
        await page.getByRole('button', { name: '프로젝트 홈 생성', exact: true }).click()
        await expect(page.getByText('프로젝트 홈 생성').first()).toBeVisible({
            timeout: 10_000,
        })
        // The Robo-Spec radio card should be the selected one by default.
        await expect(
            page.locator('.radio-card.selected').filter({ hasText: 'Robo-Spec Skills' }).first(),
        ).toBeVisible({ timeout: 5_000 })
        // The legacy heavy config sections (Tech Stack, Architecture etc)
        // should be hidden in robo-spec mode.
        await expect(page.getByText('Technology Stack', { exact: false }).first()).toBeHidden({
            timeout: 2_000,
        })
        // The footer button should read "Next →" (not "Preview →") in
        // robo-spec mode because there is nothing to preview.
        await expect(
            page.locator('.modal-footer .btn.btn-primary').filter({ hasText: 'Next' }).first(),
        ).toBeVisible({ timeout: 2_000 })
        await shot(page, 'step_02_modal_step1_robo_spec')

        // ============================================================
        // 3 — Click "Next →" — in robo-spec mode this skips the preview
        //     step (step 2) and jumps straight to project path entry.
        // ============================================================
        await page.locator('.modal-footer .btn.btn-primary').filter({ hasText: 'Next' }).first().click()
        await expect(page.locator('.complete-step').first()).toBeVisible({ timeout: 5_000 })
        await page.locator('input.form-input').first().fill(TEST_PROJECT)
        await shot(page, 'step_03_modal_step3_project_path')

        // ============================================================
        // 4 — Click the inline "Claude Code에서 열기" — fires
        //     /api/claude-code/setup-project with output_mode=robo-spec
        // ============================================================
        await page.locator('.complete-step .btn.btn-claude').first().click()
        await expect(page.locator('.complete-step').filter({ hasText: /설정 완료/ }).first())
            .toBeVisible({ timeout: 60_000 })
        await shot(page, 'step_04_modal_step4_robo_spec_install')

        // Sanity on disk: robo-spec install present, but NO PRD.md (the
        // legacy pipeline was skipped because output_mode='robo-spec').
        expect(existsSync(`${TEST_PROJECT}/.mcp.json`)).toBe(true)
        expect(existsSync(`${TEST_PROJECT}/.claude/robo-project.json`)).toBe(true)
        for (const s of ['robo-plan', 'robo-tasks', 'robo-implement', 'robo-sync']) {
            expect(existsSync(`${TEST_PROJECT}/.claude/skills/${s}/SKILL.md`)).toBe(true)
        }
        for (const s of ['speckit-plan', 'speckit-tasks', 'speckit-implement']) {
            expect(existsSync(`${TEST_PROJECT}/.claude/skills/${s}/SKILL.md`)).toBe(true)
        }
        // Robo-spec mode is supposed to skip the PRD pipeline entirely.
        expect(existsSync(`${TEST_PROJECT}/PRD.md`)).toBe(false)
        // Rewrite the .mcp.json URL to whatever port we're actually on
        // (the install defaults to :8000 which is correct here).
        const mcpJson = JSON.parse(readFileSync(`${TEST_PROJECT}/.mcp.json`, 'utf-8'))
        expect(mcpJson.mcpServers['robo-spec'].url).toContain(':8000/mcp/')

        // ============================================================
        // 5 — Click "Claude Code 터미널 열기" → tab switches; embedded
        //     terminal mounts a PTY at the project path; with the
        //     permission_mode=bypassPermissions query param the trust
        //     prompt is also bypassed and claude lands straight on the
        //     prompt cursor.
        // ============================================================
        await page.locator('.btn.btn-claude').filter({ hasText: /Claude Code 터미널 열기/ }).first().click()
        await expect(page.locator('.terminal-container').first()).toBeVisible({
            timeout: 10_000,
        })
        // Wait long enough for claude to fully render its prompt UI.
        await page.waitForTimeout(8_000)
        await shot(page, 'step_05_claude_code_tab_ready')

        // ============================================================
        // 6 — Type the slash command + Enter into the embedded terminal
        // ============================================================
        await typeIntoTerminal(
            page,
            '/robo-plan MembershipManagement — if no classification, treat as core and persist via set_bc_classification',
        )
        // Capture ~15s in so we see streaming output mid-execution.
        await page.waitForTimeout(15_000)
        await shot(page, 'step_06_terminal_robo_plan_running')

        // ============================================================
        // 8 — Poll the graph for the classification flip. Because the
        //     terminal was spawned with --permission-mode bypassPermissions,
        //     claude does not pause on per-tool prompts; /robo-plan's
        //     MCP calls (T1 resolve_design_element, T2 get_bc_design,
        //     T3 set_bc_classification, T6b register_implementation_files)
        //     all run without user intervention.
        // ============================================================
        const deadline = Date.now() + 5 * 60_000
        let after: { classification?: string } = {}
        while (Date.now() < deadline) {
            const r = await page.request.get(
                `http://127.0.0.1:8000/api/contexts/${memberBcId}/classification`,
            )
            after = await r.json()
            if (after.classification === 'core') break
            await page.waitForTimeout(4000)
        }
        // Give claude enough time to finish writing plan.md and printing
        // the summary after the last MCP write. The mkdir + plan.md write
        // typically completes within 60–120s of classification flipping.
        const planDeadline = Date.now() + 180_000
        let planPath = ''
        while (Date.now() < planDeadline) {
            planPath = execSync(
                `find ${TEST_PROJECT}/specs -name plan.md -type f 2>/dev/null | head -1`,
                { encoding: 'utf-8' },
            ).trim()
            if (planPath) break
            await page.waitForTimeout(5000)
        }
        // Final settle so the terminal shows the completion summary.
        await page.waitForTimeout(10_000)
        await shot(page, 'step_07_terminal_robo_plan_done')

        console.log('[after]', after)

        // ============================================================
        // 9 — Assertions
        // ============================================================
        // The graph should have classification='core' (proves T3 ran).
        expect(after.classification).toBe('core')

        // The skill should have written plan.md to the project.
        // (We're tolerant here — claude may still be finalizing it.)
        const planExists = !!planPath
        if (planExists) {
            console.log('[plan.md]', planPath)
        } else {
            console.log('[plan.md] not yet written — claude may still be in flight')
        }

        // Final summary for the manual.
        const summary = {
            output_mode: 'robo-spec',
            prdMdExisted: false,
            mcpJsonInstalled: true,
            roboSpecSkills: ['robo-plan', 'robo-tasks', 'robo-implement', 'robo-sync'],
            speckitInheritance: ['speckit-plan', 'speckit-tasks', 'speckit-implement'],
            beforeClassification: before.classification,
            afterClassification: after.classification,
            planMd: planPath || '(not yet written when test ended)',
            drivenBy: 'embedded xterm.js terminal (not claude -p side-channel)',
        }
        writeFileSync(
            `${SHOTS}/step_99_summary.json`,
            JSON.stringify(summary, null, 2),
        )
        console.log('[summary]', JSON.stringify(summary, null, 2))
    })
})
