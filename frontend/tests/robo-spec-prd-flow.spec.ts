/**
 * Robo Spec Skills (feature 029) — the REAL user flow.
 *
 * What we drive here:
 *
 *   1. Open the Robo Architect SPA.
 *   2. Click "PRD 생성" (the purple top-bar button).
 *   3. Walk through the PRD wizard:
 *        step 1 (config)   → step 2 (preview) → step 3 (project path)
 *        → step 4 (success) → "Open in Claude Code".
 *   4. Tab auto-switches to "Claude Code" and the embedded terminal
 *      mounts a real PTY at the generated project path.
 *   5. Verify the project on disk has the robo-* + speckit-* skills
 *      and an .mcp.json pointing at this backend.
 *   6. Drive `/robo-plan MembershipManagement` end-to-end against that
 *      project via `claude -p`, then `/robo-tasks`, `/robo-implement`.
 *   7. Capture before/after of the BC classification via the HTTP
 *      endpoint to prove T3 wrote through.
 *
 * What we do NOT do here:
 *
 *   - Driving the embedded xterm.js terminal to type the slash commands
 *     interactively. xterm.js routes keypresses through onData → WS →
 *     PTY → claude CLI; that round-trip is fine in a real session but
 *     hard to drive reliably in a 60s headless test (each keystroke
 *     ratchets the WS, and prompts inside `claude` need ANSI-aware
 *     waits). Instead we run `claude -p` directly against the project
 *     path written by setup-project — that's the same `claude` binary
 *     that the embedded terminal would have launched, with the same
 *     working directory and the same .mcp.json, so the proof is
 *     equivalent.
 */
import { test, expect, type Page } from '@playwright/test'
import { execSync } from 'node:child_process'
import { existsSync, readFileSync, mkdirSync, rmSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const SHOTS = resolve(__dirname, '../../specs/029-robo-spec-skills/manual/screenshots')
mkdirSync(SHOTS, { recursive: true })

const TEST_PROJECT = '/tmp/robo-spec-prd-flow'

async function shot(page: Page, name: string, opts: { fullPage?: boolean } = {}) {
    await page.screenshot({
        path: `${SHOTS}/${name}.png`,
        fullPage: opts.fullPage ?? false,
    })
}

test.describe('PRD 생성 → Claude Code → /robo-* (real flow)', () => {
    // Three claude -p invocations each take 30–60s with model thinking;
    // budget 8 minutes for the whole flow.
    test.setTimeout(480_000)

    test.beforeAll(() => {
        try { rmSync(TEST_PROJECT, { recursive: true, force: true }) } catch {}
        mkdirSync(TEST_PROJECT, { recursive: true })
    })

    test('full flow: PRD wizard → workspace install → robo-plan/tasks/implement', async ({ page }) => {
        page.on('console', m => { if (m.type() === 'error') console.log('[console]', m.text()) })
        page.on('pageerror', e => console.log('[pageerror]', e.message))

        // ============================================================
        // 0 — Capture BEFORE state via HTTP
        // ============================================================
        const memberBcId = '24fa4636-6a5c-493a-8cfa-a08833e245eb'
        const beforeResp = await page.request.get(
            `http://127.0.0.1:8000/api/contexts/${memberBcId}/classification`,
        )
        const beforeJson = await beforeResp.json()
        expect(beforeJson.classification).toBeNull()
        console.log('[before]', beforeJson)

        // ============================================================
        // 1 — SPA loads with the Design tab and the navigator populated
        // ============================================================
        await page.goto('/')
        await expect(page.getByRole('button', { name: 'Design', exact: true })).toBeVisible({
            timeout: 20_000,
        })
        await expect(page.getByText('MembershipManagement').first()).toBeVisible({
            timeout: 10_000,
        })
        await shot(page, 'flow_01_spa_design_tab_before')

        // ============================================================
        // 2 — Click PRD 생성 → modal opens at step 1
        // ============================================================
        await page.getByRole('button', { name: 'PRD 생성', exact: true }).click()
        // Wait for the modal heading to render.
        await expect(page.getByText('Generate PRD for Vibe Coding').first()).toBeVisible({
            timeout: 10_000,
        })
        // Turn off "Include Frontend PRD" so we don't have to pick a
        // frontend framework (otherwise the backend rejects with
        // FR-020 'frontend_framework MUST be set').
        const includeFrontendCheckbox = page
            .getByLabel('Include Frontend PRD and Rules', { exact: false })
            .first()
        if (await includeFrontendCheckbox.isChecked()) {
            await includeFrontendCheckbox.uncheck()
        }
        // Use the simplest spec format (PRD flat). It's the default.
        await shot(page, 'flow_02_prd_modal_step1_config')

        // ============================================================
        // 3 — Step 1 → 2: click "Preview →" (generatePreview)
        // ============================================================
        await page.locator('.modal-footer .btn.btn-primary').filter({ hasText: /Preview/i }).first().click()
        // Wait for step 2 to render: ".preview-step" container.
        await expect(page.locator('.preview-step').first()).toBeVisible({
            timeout: 30_000,
        })
        await shot(page, 'flow_03_prd_modal_step2_preview')

        // ============================================================
        // 4 — Step 2 → 3: footer's primary button "Claude Code에서 열기"
        //     (proceedToClaudeSetup). At step 2 this lives in the modal
        //     footer, distinguishing it from the step-3 inline button
        //     which has the same label.
        // ============================================================
        await page.locator('.modal-footer .btn.btn-primary').first().click()
        await expect(page.locator('.complete-step').first()).toBeVisible({
            timeout: 10_000,
        })
        // Fill in the project path
        await page.locator('input.form-input').first().fill(TEST_PROJECT)
        await shot(page, 'flow_04_prd_modal_step3_project_path')

        // ============================================================
        // 5 — Step 3 inline `.btn-claude` button → setupAndOpenClaudeCode → step 4
        // ============================================================
        // The setup button lives INSIDE .complete-step (not the footer),
        // is class `btn-claude`, and shows "Claude Code에서 열기" or
        // "프로젝트 설정 중..." while in flight.
        await page.locator('.complete-step .btn.btn-claude').first().click()
        // setup-project takes a few seconds (PRD generation + verbatim
        // copy + checksum) — allow up to 90s before timing out.
        await expect(page.locator('.complete-step').filter({ hasText: /설정 완료/ }).first())
            .toBeVisible({ timeout: 90_000 })
        await shot(page, 'flow_05_prd_modal_step4_success')

        // ============================================================
        // 6 — Verify what setup-project actually wrote to disk
        // ============================================================
        expect(existsSync(`${TEST_PROJECT}/.mcp.json`)).toBe(true)
        expect(existsSync(`${TEST_PROJECT}/.claude/robo-project.json`)).toBe(true)
        const mcpJson = JSON.parse(readFileSync(`${TEST_PROJECT}/.mcp.json`, 'utf-8'))
        expect(mcpJson.mcpServers?.['robo-spec']?.url).toBeTruthy()
        // All four robo-* skills installed
        for (const s of ['robo-plan', 'robo-tasks', 'robo-implement', 'robo-sync']) {
            expect(existsSync(`${TEST_PROJECT}/.claude/skills/${s}/SKILL.md`)).toBe(true)
        }
        // Speckit upstreams (required for the inheritance chain)
        for (const s of ['speckit-plan', 'speckit-tasks', 'speckit-implement']) {
            expect(existsSync(`${TEST_PROJECT}/.claude/skills/${s}/SKILL.md`)).toBe(true)
        }

        // ============================================================
        // 7 — Click "Open in Claude Code" → tab switches
        // ============================================================
        await page.locator('.btn.btn-claude').first().click()
        // Tab switch — wait for the Claude Code workspace shell.
        await page.waitForTimeout(2500)
        await shot(page, 'flow_06_claude_code_tab_opened')

        // ============================================================
        // 8 — Rewrite the .mcp.json URL to this backend (the install
        //     writes :8000 by default, which matches in this run; we
        //     leave it alone but verify it's pointing at the live
        //     backend so the rest of the run actually exercises MCP).
        // ============================================================
        // Sanity: the mcp.json should already point at :8000.
        expect(mcpJson.mcpServers['robo-spec'].url).toMatch(/127\.0\.0\.1:8000|localhost:8000/)

        // ============================================================
        // 9 — Drive /robo-plan via `claude -p` against the same project
        //     path that the embedded terminal would have opened.
        // ============================================================
        const planOut = execSync(
            `cd ${TEST_PROJECT} && echo "/robo-plan MembershipManagement — if no classification is recorded, treat it as core and persist via set_bc_classification" | claude -p --output-format text --permission-mode bypassPermissions --max-budget-usd 2.50 --model claude-sonnet-4-5`,
            { encoding: 'utf-8', maxBuffer: 1024 * 1024 * 4 },
        )
        console.log('[robo-plan stdout]', planOut.slice(-1200))
        // plan.md should now exist somewhere under specs/
        const planExists = execSync(
            `find ${TEST_PROJECT}/specs -name plan.md -type f 2>/dev/null | head -1`,
            { encoding: 'utf-8' },
        ).trim()
        expect(planExists).toBeTruthy()

        // ============================================================
        // 10 — Drive /robo-tasks
        // ============================================================
        const tasksOut = execSync(
            `cd ${TEST_PROJECT} && echo "/robo-tasks" | claude -p --output-format text --permission-mode bypassPermissions --max-budget-usd 2.50 --model claude-sonnet-4-5`,
            { encoding: 'utf-8', maxBuffer: 1024 * 1024 * 4 },
        )
        console.log('[robo-tasks stdout]', tasksOut.slice(-800))
        const tasksExists = execSync(
            `find ${TEST_PROJECT}/specs -name tasks.md -type f 2>/dev/null | head -1`,
            { encoding: 'utf-8' },
        ).trim()
        expect(tasksExists).toBeTruthy()
        // Verify at least one @robo marker
        const tasksContent = readFileSync(tasksExists, 'utf-8')
        expect(tasksContent).toMatch(/<!-- @robo elementId=/)

        // ============================================================
        // 11 — Drive /robo-implement
        // ============================================================
        const implOut = execSync(
            `cd ${TEST_PROJECT} && echo "/robo-implement" | claude -p --output-format text --permission-mode bypassPermissions --max-budget-usd 3.00 --model claude-sonnet-4-5`,
            { encoding: 'utf-8', maxBuffer: 1024 * 1024 * 4 },
        )
        console.log('[robo-implement stdout]', implOut.slice(-800))
        // The MemberAccount aggregate should now be scaffolded
        const srcFiles = execSync(
            `find ${TEST_PROJECT}/src -type f 2>/dev/null | sort`,
            { encoding: 'utf-8' },
        ).trim()
        console.log('[scaffolded src files]', srcFiles)
        expect(srcFiles).toContain('MemberAccount')
        // R7 enforcement: NO @robo markers in source
        const robotInSrc = execSync(
            `grep -rIn '@robo' ${TEST_PROJECT}/src 2>/dev/null || true`,
            { encoding: 'utf-8' },
        )
        expect(robotInSrc.trim()).toBe('')

        // ============================================================
        // 12 — Capture AFTER state via HTTP — classification persisted
        // ============================================================
        const afterResp = await page.request.get(
            `http://127.0.0.1:8000/api/contexts/${memberBcId}/classification`,
        )
        const afterJson = await afterResp.json()
        expect(afterJson.classification).toBe('core')
        console.log('[after]', afterJson)

        // Final summary written to a sidecar so the manual can ingest it
        const summary = {
            beforeClassification: beforeJson.classification,
            afterClassification: afterJson.classification,
            mcpUrl: mcpJson.mcpServers['robo-spec'].url,
            planMd: planExists,
            tasksMd: tasksExists,
            scaffoldedFiles: srcFiles.split('\n').filter(Boolean),
            roboMarkersInSrc: robotInSrc.trim() || '(none — R7 enforced)',
        }
        execSync(
            `cat > ${SHOTS}/flow_99_summary.json <<'EOF'\n${JSON.stringify(summary, null, 2)}\nEOF`,
        )
        console.log('[summary]', JSON.stringify(summary, null, 2))
    })
})
