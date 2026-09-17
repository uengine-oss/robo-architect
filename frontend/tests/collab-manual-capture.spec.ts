import { test, expect, type Page } from '@playwright/test'
import { login, sharedGraph, openApp, waitConnected, gotoDesignTree, type Who } from './helpers/collab'

/**
 * **동시편집 매뉴얼의 화면을 실제로 찍는다**
 * → `specs/057-presence-bound-element-lock/manual/images/`.
 *
 * 매뉴얼에 손으로 그린 그림을 넣지 않는다. 화면이 바뀌면 그림이 조용히
 * 거짓말을 하기 시작하고, 그 거짓말은 고객이 먼저 본다. 여기서 찍은 것만 쓴다.
 *
 * 두 사람을 실제로 띄운다 — 동시편집은 **혼자서는 찍을 수 없는 화면**이다.
 *
 * 실 데이터를 고치지 않는다. 잠그고 보고 푸는 것만 한다.
 *
 *     npx playwright test tests/collab-manual-capture.spec.ts --workers=1
 */

const IMG = '../specs/057-presence-bound-element-lock/manual/images'

test.use({ storageState: { cookies: [], origins: [] } })

async function openCanvas(page: Page): Promise<string> {
  await gotoDesignTree(page)
  const rows = page.locator('.tree-node__label')
  for (let i = 0; i < Math.min(await rows.count(), 15); i += 1) {
    const label = (await rows.nth(i).textContent().catch(() => ''))?.trim() || ''
    if (!label || /\(\d+\)\s*$/.test(label)) continue
    await rows.nth(i).dblclick().catch(() => {})
    await page.waitForTimeout(1500)
    if (await page.locator('.vue-flow__node').count() > 0) return label
  }
  throw new Error('캔버스가 안 그려진다 — 설계가 들어 있는 프로젝트여야 한다')
}

/** 캔버스 노드는 서로 겹쳐 있어 `force` 가 필요하다. 앱이 느린 게 아니다. */
async function pickNode(page: Page): Promise<{ id: string; index: number }> {
  const nodes = page.locator('.vue-flow__node')
  for (let i = 0; i < Math.min(await nodes.count(), 12); i += 1) {
    const cls = (await nodes.nth(i).getAttribute('class')) || ''
    if (/vue-flow__node-(boundedcontext|aggregate)\b/.test(cls)) continue
    const id = await nodes.nth(i).getAttribute('data-id')
    if (id) return { id, index: i }
  }
  throw new Error('챗이 다룰 수 있는 캔버스 노드가 없다')
}

test('동시편집 매뉴얼 — 두 사람 화면 캡처', async ({ browser }) => {
  test.setTimeout(420_000)
  const [alice, tester]: Who[] = await Promise.all([login('alice'), login('test')])
  const graph = await sharedGraph(alice, tester)
  console.log(`[manual] ${alice.uid} · ${tester.uid} · graph=${graph}`)

  const ca = await browser.newContext({ viewport: { width: 1600, height: 950 } })
  const cb = await browser.newContext({ viewport: { width: 1600, height: 950 } })
  const pa = await openApp(ca, alice, graph)
  const pb = await openApp(cb, tester, graph)
  await waitConnected(pa, 'alice')
  await waitConnected(pb, 'test')

  let target: string | null = null
  try {
    // ── 01 접속자 ──────────────────────────────────────────────────────
    await gotoDesignTree(pa)
    await pa.waitForTimeout(1200)
    await pa.screenshot({ path: `${IMG}/01-viewers.png`, fullPage: false })

    // ── 02 요소를 열면 잡는다 (잡은 사람 화면) ─────────────────────────
    await openCanvas(pa)
    const picked = await pickNode(pa)
    target = picked.id
    const node = pa.locator('.vue-flow__node').nth(picked.index)
    await node.scrollIntoViewIfNeeded().catch(() => {})
    await node.dblclick({ force: true, timeout: 20_000 })
    await expect(pa.locator('.inspector-panel')).toBeVisible({ timeout: 20_000 })
    await pa.waitForTimeout(2000)
    await pa.screenshot({ path: `${IMG}/02-holder-can-edit.png`, fullPage: false })

    // ── 03 같은 요소를 연 다른 사람 화면 — 배너와 잠긴 입력칸 ──────────
    await openCanvas(pb)
    const same = pb.locator(`.vue-flow__node[data-id="${target}"]`)
    await same.scrollIntoViewIfNeeded().catch(() => {})
    await same.dblclick({ force: true, timeout: 20_000 })
    await expect(pb.locator('.inspector-panel .lockbar'), '남이 잡았는데 배너가 없다')
      .toBeVisible({ timeout: 20_000 })
    await pb.waitForTimeout(1200)
    await pb.screenshot({ path: `${IMG}/03-locked-for-others.png`, fullPage: false })
    await pb.locator('.inspector-panel .lockbar').screenshot({ path: `${IMG}/04-lock-banner.png` })

    // ── 05 AI 챗도 같은 선점을 본다 ────────────────────────────────────
    await same.click({ force: true, timeout: 20_000 })
    const chat = pb.locator('.chat-panel')
    if (!(await chat.isVisible({ timeout: 3_000 }).catch(() => false))) {
      await pb.locator('.right-sidebar [title="Chat"]').first().click()
    }
    await expect(chat).toBeVisible({ timeout: 20_000 })
    await expect(pb.locator('.chat-panel .lockbar')).toBeVisible({ timeout: 20_000 })
    await pb.waitForTimeout(800)
    await pb.screenshot({ path: `${IMG}/05-chat-blocked.png`, fullPage: false })

    // ── 06 연결이 끊기면 — 잡은 사람에게 뜨는 경고 ─────────────────────
    await pa.route('**/api/collab/stream*', (r) => r.abort())
    await pa.evaluate(() => (window as any).__collab?.close?.(false))
    await expect(pa.locator('.inspector-panel .lockbar--risk'), '끊김 경고가 안 뜬다')
      .toBeVisible({ timeout: 40_000 })
    await pa.waitForTimeout(600)
    await pa.screenshot({ path: `${IMG}/06-disconnected-warning.png`, fullPage: false })
    await pa.locator('.inspector-panel .lockbar--risk').screenshot({ path: `${IMG}/07-risk-banner.png` })

    await pa.unroute('**/api/collab/stream*')
    await pa.evaluate((g) => (window as any).__collab?.watch?.(g), graph)
    await expect(pa.locator('.inspector-panel .lockbar--risk')).toHaveCount(0, { timeout: 40_000 })

    console.log('[manual] 캡처 완료')
  } finally {
    if (target) {
      await pa.evaluate((id) => fetch('/api/collab/unlock', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ elementId: id }),
      }), target).catch(() => {})
    }
    await ca.close(); await cb.close()
  }
})
