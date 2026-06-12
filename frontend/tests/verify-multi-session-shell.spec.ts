import { test, expect } from '@playwright/test'
import { execSync } from 'node:child_process'
import { existsSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

/**
 * 039 멀티 세션 검증 — 여러 Proposal이 동시에 각자의 worktree에서 독립 claude 셀로 진행,
 * Code 탭 상단 세션 탭으로 전환 가능 (프로세스/UI 중복 없음).
 */

const BACKEND = 'http://localhost:8000'
const APP = 'http://localhost:5173'

test.use({ headless: false, viewport: { width: 1480, height: 920 } })

async function seedSubmitted(request: any, title: string): Promise<string> {
  const c = await request.post(`${BACKEND}/api/proposals/`, {
    data: { originalPrompt: title, title },
  })
  expect(c.ok()).toBeTruthy()
  const id = (await c.json()).id
  const d = await request.put(`${BACKEND}/api/proposals/${id}/diff`, {
    data: { tacticalDiff: [{ nodeId: `AGG-${id}`, nodeLabel: 'Aggregate', changeType: 'MODIFY', semanticDiff: { ops: [] } }] },
  })
  expect(d.ok()).toBeTruthy()
  const s = await request.post(`${BACKEND}/api/proposals/${id}/submit`, { data: {} })
  expect(s.ok()).toBeTruthy()
  return id
}

async function openAndImplement(page: any, id: string) {
  await page.getByText('Proposals', { exact: true }).click()
  const item = page.locator('.proposal-item', { hasText: id })
  await expect(item).toBeVisible({ timeout: 10_000 })
  await item.click()
  await page.getByRole('button', { name: '샌드박스 구현' }).click()
  await page.getByRole('button', { name: '구현 시작' }).first().click()
}

test('멀티 세션: 두 Proposal worktree가 각각 셀 탭으로 뜨고 전환된다', async ({ page, request }) => {
  const target = mkdtempSync(join(tmpdir(), 'robo-multi-target-'))
  execSync('git init -q && git config user.email t@t.io && git config user.name t', { cwd: target })
  execSync('echo "# t" > README.md && git add -A && git commit -q -m init', { cwd: target })

  let idA = ''
  let idB = ''
  try {
    idA = await seedSubmitted(request, '멀티세션 A')
    idB = await seedSubmitted(request, '멀티세션 B')
    console.log(`seeded A=${idA} B=${idB}`)

    await page.addInitScript((root) => {
      localStorage.setItem('claude_code_workspace_root', root as string)
      // 깨끗한 세션 상태에서 시작
      localStorage.removeItem('claude_code_workspace_sessions')
      localStorage.removeItem('claude_code_workspace_active_session')
    }, target)
    await page.goto(APP)
    await page.waitForLoadState('networkidle')

    // ── Proposal A 구현 시작 → 세션 A 생성 + Code 탭 ──
    await openAndImplement(page, idA)
    await expect(page.locator('.ccw-session-tabs')).toBeVisible({ timeout: 15_000 })
    const tabA = page.locator('.ccw-session-tab', { hasText: idA })
    await expect(tabA).toBeVisible({ timeout: 10_000 })
    await expect(tabA).toHaveClass(/is-active/)
    console.log('✅ 세션 A 탭 생성 + 활성')
    await page.screenshot({ path: 'test-results/ms01-session-A.png' })

    // ── Proposal B 구현 시작 → 세션 B 추가 ──
    await openAndImplement(page, idB)
    const tabB = page.locator('.ccw-session-tab', { hasText: idB })
    await expect(tabB).toBeVisible({ timeout: 10_000 })
    await expect(tabB).toHaveClass(/is-active/)
    // A 탭도 여전히 존재해야 함 (세션 유지, 중복 없음)
    await expect(page.locator('.ccw-session-tab', { hasText: idA })).toHaveCount(1)
    await expect(page.locator('.ccw-session-tab', { hasText: idB })).toHaveCount(1)
    console.log('✅ 세션 B 추가 — A/B 두 세션 공존')
    await page.screenshot({ path: 'test-results/ms02-session-B.png' })

    // ── 두 worktree가 디스크에 동시 존재 ──
    const wtA = join(target, '.sandbox', 'proposal', idA)
    const wtB = join(target, '.sandbox', 'proposal', idB)
    await expect.poll(() => existsSync(wtA) && existsSync(wtB), { timeout: 15_000 }).toBe(true)
    console.log('✅ 두 worktree 동시 존재')

    // ── 세션 A로 전환 → 파일 트리가 A worktree를 따라간다 ──
    await page.locator('.ccw-session-tab', { hasText: idA }).click()
    await expect(page.locator('.ccw-session-tab', { hasText: idA })).toHaveClass(/is-active/)
    await expect(page.getByText(`PROPOSAL_${idA}.md`)).toBeVisible({ timeout: 10_000 })
    console.log('✅ A 전환 시 파일 트리가 A worktree(PROPOSAL_A.md) 표시')
    await page.screenshot({ path: 'test-results/ms03-switch-to-A.png' })

    // ── 다시 B로 전환 → 트리가 B worktree ──
    await page.locator('.ccw-session-tab', { hasText: idB }).click()
    await expect(page.getByText(`PROPOSAL_${idB}.md`)).toBeVisible({ timeout: 10_000 })
    console.log('✅ B 전환 시 파일 트리가 B worktree 표시')

    console.log('🎉 멀티 세션 검증 통과')
  } finally {
    for (const id of [idA, idB]) {
      if (!id) continue
      try { execSync(`git worktree remove --force .sandbox/proposal/${id}`, { cwd: target, stdio: 'ignore' }) } catch {}
      try { execSync(`git branch -D proposal/${id}`, { cwd: target, stdio: 'ignore' }) } catch {}
      // Neo4j 테스트 노드 정리는 별도(자격증명 필요) — 여기선 생략
    }
    try { rmSync(target, { recursive: true, force: true }) } catch {}
  }
})
