import { test, expect } from '@playwright/test'
import { execSync } from 'node:child_process'
import { existsSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

/**
 * 039 재설계 검증 — Proposal 샌드박스 구현 = "Claude Code 탭 대상 프로젝트" 기준 worktree + Code 탭 셀 재사용
 *
 * 검증 포인트:
 *  1. Worktree 원천이 robo-architect가 아니라 Claude Code 탭의 대상 프로젝트(projectRoot)이다.
 *     → <projectRoot>/.sandbox/proposal/<PRO> 가 실제로 생성된다.
 *  2. "구현 시작" → 상태 IMPLEMENTING 전환 + 화면이 Code 탭으로 이동(셀 재사용).
 *  3. Proposal 상세에 "Claude Code 셀로 이동" / "구현 완료 → 테스트" 버튼이 나타난다.
 *
 * LLM(intent 분해)에 의존하지 않도록 Proposal을 API로 직접 SUBMITTED 상태까지 시드한다.
 */

const BACKEND = 'http://localhost:8000'
const APP = 'http://localhost:5173'

test.use({ headless: false, viewport: { width: 1440, height: 900 } })

test('샌드박스 구현: 대상 프로젝트에 worktree 생성 + Code 탭 셀 재사용', async ({ page, request }) => {
  // ── 0. 대상 프로젝트(가짜 사용자 프로젝트) git repo 생성 ──────────────────────
  const target = mkdtempSync(join(tmpdir(), 'robo-proposal-target-'))
  execSync('git init -q && git config user.email t@t.io && git config user.name t', { cwd: target })
  execSync('echo "# target project" > README.md && git add -A && git commit -q -m init', { cwd: target })
  console.log(`✅ 대상 프로젝트 repo: ${target}`)

  let proposalId = ''
  try {
    // ── 1. Proposal을 API로 SUBMITTED까지 시드 ───────────────────────────────
    const created = await request.post(`${BACKEND}/api/proposals/`, {
      data: { originalPrompt: '상품 리뷰 작성/평점 기능 추가', title: '리뷰 기능(샌드박스 셀 테스트)' },
    })
    expect(created.ok(), `create 실패: ${created.status()}`).toBeTruthy()
    proposalId = (await created.json()).id
    console.log(`✅ Proposal 생성: ${proposalId}`)

    const diff = await request.put(`${BACKEND}/api/proposals/${proposalId}/diff`, {
      data: {
        tacticalDiff: [
          { nodeId: 'AGG-review', nodeLabel: 'Aggregate', changeType: 'MODIFY', semanticDiff: { ops: [] } },
        ],
      },
    })
    expect(diff.ok(), `diff 실패: ${diff.status()}`).toBeTruthy()

    const submitted = await request.post(`${BACKEND}/api/proposals/${proposalId}/submit`, { data: {} })
    expect(submitted.ok(), `submit 실패: ${submitted.status()}`).toBeTruthy()
    expect((await submitted.json()).status).toBe('SUBMITTED')
    console.log('✅ SUBMITTED 상태로 시드 완료')

    // ── 2. Claude Code 탭 경로(projectRoot)를 localStorage에 주입 후 앱 로드 ────
    await page.addInitScript((root) => {
      localStorage.setItem('claude_code_workspace_root', root as string)
    }, target)

    await page.goto(APP)
    await page.waitForLoadState('networkidle')

    // ── 3. Proposals 탭 → 시드한 Proposal 열기 ───────────────────────────────
    await page.getByText('Proposals', { exact: true }).click()
    const item = page.locator('.proposal-item', { hasText: proposalId })
    await expect(item).toBeVisible({ timeout: 10_000 })
    await item.click()
    await page.screenshot({ path: 'test-results/sh01-detail.png' })

    // ── 4. "샌드박스 구현" 탭 → 대상 프로젝트 경로 노출 확인 ──────────────────
    await page.getByRole('button', { name: '샌드박스 구현' }).click()
    await expect(page.locator('.project-root-line code', { hasText: target })).toBeVisible({ timeout: 5000 })
    console.log('✅ 대상 프로젝트 경로가 UI에 표시됨 (robo-architect 아님)')
    await page.screenshot({ path: 'test-results/sh02-sandbox-tab.png' })

    // ── 5. 구현 시작 ─────────────────────────────────────────────────────────
    await page.getByRole('button', { name: '구현 시작' }).first().click()

    // 5a. 백엔드가 대상 프로젝트에 worktree를 동기 생성했는지 (디스크 확인)
    const worktree = join(target, '.sandbox', 'proposal', proposalId)
    await expect.poll(() => existsSync(worktree), { timeout: 20_000, message: 'worktree 생성 대기' }).toBe(true)
    expect(existsSync(join(worktree, `PROPOSAL_${proposalId}.md`))).toBe(true)
    console.log(`✅ Worktree 생성 확인: ${worktree}`)

    // 5b. 브랜치가 대상 repo에 만들어졌는지
    const branches = execSync('git branch --list', { cwd: target }).toString()
    expect(branches).toContain(`proposal/${proposalId}`)
    console.log('✅ proposal/<PRO> 브랜치가 대상 repo에 생성됨')

    // ── 6. 화면이 Code 탭(셀 재사용)으로 전환되었는지 ────────────────────────
    await expect(page.locator('.claude-code-terminal')).toBeVisible({ timeout: 15_000 })
    await expect(page.locator('.terminal-header__workdir')).toContainText(target, { timeout: 10_000 })
    console.log('✅ Code 탭 셀이 worktree 경로로 전환됨')
    await page.screenshot({ path: 'test-results/sh03-code-tab-shell.png' })

    // ── 7. Proposal 상세로 복귀 → 셀로 이동 / 구현 완료 버튼 확인 ─────────────
    await page.getByText('Proposals', { exact: true }).click()
    const item2 = page.locator('.proposal-item', { hasText: proposalId })
    await item2.click()
    await page.getByRole('button', { name: '샌드박스 구현' }).click()
    await expect(page.getByRole('button', { name: 'Claude Code 셀로 이동' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: /구현 완료/ })).toBeVisible()
    console.log('✅ "셀로 이동" / "구현 완료 → 테스트" 버튼 노출 확인')
    await page.screenshot({ path: 'test-results/sh04-implementing-actions.png' })

    console.log('🎉 모든 검증 통과')
  } finally {
    // ── 정리: worktree/브랜치 제거 + 임시 repo 삭제 ──────────────────────────
    try {
      if (proposalId) {
        execSync(`git worktree remove --force .sandbox/proposal/${proposalId}`, { cwd: target, stdio: 'ignore' })
        execSync(`git branch -D proposal/${proposalId}`, { cwd: target, stdio: 'ignore' })
      }
    } catch {}
    try { rmSync(target, { recursive: true, force: true }) } catch {}
  }
})
