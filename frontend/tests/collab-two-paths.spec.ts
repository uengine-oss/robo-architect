import { test, expect, type Page } from '@playwright/test'
import {
  login, sharedGraph, openApp, waitConnected, gotoDesignTree, serverLocks, type Who,
} from './helpers/collab'

/**
 * **고치는 길이 둘이다 — 인스펙터 직접 편집과 AI 챗.** 둘이 같은 선점을 봐야 한다.
 *
 * 지금까지 이 둘은 따로 재였다. 직접 편집은 여덟 종류를 그래프까지 확인했고,
 * 챗은 `/api/chat/confirm` 까지만 쟀다 — **프롬프트를 치고 초안을 받아 승인을
 * 누르는 왕복**은 한 번도 안 지났다.
 *
 * 그리고 한 자리가 "모른다"로 남아 있었다(STATUS §4.27): 챗의 **칩 id** 와
 * 인스펙터의 **잠금 id** 가 같은 값인지. 기존 검사는 **양쪽에 같은 id 를 심어서**
 * 넣으므로 그 질문에 답하지 못한다. 다르면 배너도 입력 잠금도 안 걸리고 서버
 * 409 만 남는다 — 고치기 전 상태와 똑같아진다.
 *
 * spec: `specs/057-presence-bound-element-lock/` (US4 · US5)
 */

test.use({ storageState: { cookies: [], origins: [] } })

/**
 * **두 길이 만나는 자리는 캔버스다.**
 *
 * 트리로는 못 만난다 — 실측이다.
 *
 *     UserStory      더블클릭하면 인스펙터가 열린다. 그런데 **챗이 거른다**
 *                    (`addToChatSelection` 이 UserStory·Invariant 를 건너뛴다)
 *     그 밖의 종류    Cmd+클릭으로 칩은 생기는데 **트리 더블클릭으로는 인스펙터가
 *                    안 열린다**. BoundedContext 를 더블클릭하면 캔버스가 그려진다
 *
 * 그래서 BC 를 열어 캔버스를 그린 뒤, **같은 캔버스 노드**를 클릭(칩)하고
 * 더블클릭(인스펙터)한다.
 *
 * `force: true` 가 필요하다. 캔버스 노드는 서로 겹쳐 있어서 Playwright 의
 * 조작 가능성 검사가 통과하지 못하고 기다리기만 한다 — **"캔버스 노드
 * 더블클릭이 180초를 넘긴다"고 적혀 있던 것이 이것이었다.** 앱이 느린 것이
 * 아니었다.
 */
async function openBoundedContextCanvas(page: Page): Promise<string> {
  await gotoDesignTree(page)
  const rows = page.locator('.tree-node__label')
  const total = Math.min(await rows.count(), 15)
  for (let i = 0; i < total; i += 1) {
    const label = (await rows.nth(i).textContent().catch(() => ''))?.trim() || ''
    if (!label || /\(\d+\)\s*$/.test(label)) continue
    await rows.nth(i).dblclick().catch(() => {})
    await page.waitForTimeout(1500)
    if (await page.locator('.vue-flow__node').count() > 0) return label
  }
  throw new Error('트리에서 BoundedContext 를 열어도 캔버스가 안 그려진다')
}

/** 캔버스에서 **챗이 다룰 수 있는** 노드 하나. BC 컨테이너는 거른다. */
async function pickCanvasNode(page: Page): Promise<{ id: string; index: number }> {
  const nodes = page.locator('.vue-flow__node')
  const n = await nodes.count()
  for (let i = 0; i < Math.min(n, 12); i += 1) {
    const cls = await nodes.nth(i).getAttribute('class') || ''
    if (/vue-flow__node-(boundedcontext|aggregate)\b/.test(cls)) continue
    const id = await nodes.nth(i).getAttribute('data-id')
    if (id) return { id, index: i }
  }
  throw new Error(`캔버스 노드 ${n}개 중 챗이 다룰 수 있는 것이 없다`)
}

/**
 * 같은 캔버스 노드를 **두 길로** 건드린다 — 클릭(칩)과 더블클릭(인스펙터).
 * 어느 쪽에도 id 를 심지 않는다. 그래야 "같은 값인가"를 물을 수 있다.
 */
async function pickBothWays(page: Page): Promise<{ chipIds: string[]; lockId: string; label: string }> {
  const bc = await openBoundedContextCanvas(page)
  const { index } = await pickCanvasNode(page)
  const node = page.locator('.vue-flow__node').nth(index)

  await node.scrollIntoViewIfNeeded().catch(() => {})
  await node.click({ force: true, timeout: 20_000 })
  await page.waitForTimeout(1200)
  const chipIds = await chipIdsOf(page)

  await node.dblclick({ force: true, timeout: 20_000 })
  await expect(page.locator('.inspector-panel'), '캔버스 노드를 열었는데 인스펙터가 안 뜬다')
    .toBeVisible({ timeout: 20_000 })
  await page.waitForTimeout(2000)
  const locked = await page.evaluate(() =>
    ((window as any).__collab?.locks || []).map((l: any) => l.elementId))
  // **0건의 이유를 가른다.** "안 잡혔다"와 "안 봤다"는 다른 사건이다.
  expect(locked, `인스펙터는 열렸는데 잠금이 하나도 없다 (BC=${bc})`).not.toHaveLength(0)

  return { chipIds, lockId: locked[locked.length - 1], label: bc }
}

function chipIdsOf(page: Page): Promise<string[]> {
  return page.evaluate(async () => {
    const { useModelModifierStore } = await import('/src/features/modelModifier/modelModifier.store.js')
    return (useModelModifierStore().currentSelectedNodes || [])
      .map((n: any) => n.id || n.data?.id).filter(Boolean)
  })
}

test.describe('고치는 길이 둘 — 인스펙터와 AI 챗', () => {
  let alice: Who, tester: Who, graph: string

  test.beforeAll(async () => {
    ;[alice, tester] = await Promise.all([login('alice'), login('test')])
    graph = await sharedGraph(alice, tester)
    console.log(`[two-paths] ${alice.uid} · ${tester.uid} · graph=${graph}`)
  })

  /**
   * FR-010 — **칩 id 와 잠금 id 가 같은 값인가.**
   *
   * 코드를 읽으면 맞는다(`props.node.id` 하나에서 갈린다). 하지만 **읽어서 맞는
   * 것과 재서 맞는 것은 다르다.** 여기서는 앱이 만든 두 값을 그대로 맞댄다.
   */
  test('챗 칩과 인스펙터 잠금이 같은 요소를 가리킨다', async ({ browser }) => {
    test.setTimeout(180_000)
    const ca = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    await waitConnected(pa, 'alice')

    try {
      const { chipIds, lockId, label } = await pickBothWays(pa)
      console.log(`[two-paths] ${label} · 칩=${JSON.stringify(chipIds)} · 잠금=${lockId}`)

      expect(chipIds, `칩이 하나도 없다 — 비교할 것이 없다 (${label})`).not.toHaveLength(0)
      expect(chipIds,
        `같은 요소인데 챗 칩(${chipIds.join(', ')})과 잠금(${lockId})의 id 가 다르다 — ` +
        '배너도 입력 잠금도 안 걸리고 서버 409 만 남는다')
        .toContain(lockId)

      // 서버가 아는 값과도 같아야 한다. 화면끼리만 맞으면 서버는 다른 것을 막는다.
      const onServer = (await serverLocks(pa)).map((l: any) => l.elementId)
      expect(onServer, `화면은 ${lockId} 를 잡았다는데 서버 목록에 없다`).toContain(lockId)
    } finally {
      await ca.close()
    }
  })

  /**
   * US4-1 — 남이 잡은 요소를 챗에 올리면 **LLM 을 부르기 전에** 막힌다.
   *
   * 기존 검사는 칩을 스토어에 심어서 넣었다 — 그러면 칩 id 와 잠금 id 가
   * 실제로 같은지를 묻지 못한다. 여기서는 **화면 조작으로** 올린다.
   */
  test('남이 잡은 요소는 챗이 프롬프트 단계에서 막는다', async ({ browser }) => {
    test.setTimeout(240_000)
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    let target: string | null = null
    try {
      // alice 가 캔버스에서 하나를 열어 잡는다 (인스펙터)
      const picked = await pickBothWays(pa)
      target = picked.lockId

      // test 는 **같은 요소를** 같은 길로 올린다 — 캔버스에서 고른다
      await openBoundedContextCanvas(pb)
      const same = pb.locator(`.vue-flow__node[data-id="${target}"]`)
      await expect(same, `test 창 캔버스에 같은 노드(${target})가 없다`)
        .toHaveCount(1, { timeout: 20_000 })
      await same.scrollIntoViewIfNeeded().catch(() => {})
      await same.click({ force: true, timeout: 20_000 })

      const chatPanel = pb.locator('.chat-panel')
      if (!(await chatPanel.isVisible({ timeout: 3_000 }).catch(() => false))) {
        await pb.locator('.right-sidebar [title="Chat"]').first().click()
      }
      await expect(chatPanel, '챗 패널이 안 열린다').toBeVisible({ timeout: 20_000 })
      expect(await chipIdsOf(pb), '캔버스에서 골랐는데 칩에 그 요소가 없다').toContain(target)

      const banner = pb.locator('.chat-panel .lockbar')
      const input = pb.locator('.chat-input__textarea')
      await expect(banner, '남이 잡았는데 챗이 아무 말도 안 한다').toBeVisible({ timeout: 20_000 })
      await expect(banner).toContainText('편집 중')
      await expect(input, '남이 잡았는데 프롬프트를 칠 수 있다').toBeDisabled({ timeout: 15_000 })

      // **반대쪽도 잰다** — 잡은 사람이 떠나면 다시 칠 수 있어야 한다.
      // 이게 없으면 전부 막아 놓고도 통과한다.
      await pa.goto('about:blank', { waitUntil: 'domcontentloaded' })
      await expect(input, '잡은 사람이 떠났는데 챗이 계속 막혀 있다')
        .toBeEnabled({ timeout: 40_000 })
      await expect(banner).toHaveCount(0)
    } finally {
      if (target) {
        await pb.evaluate((id) => fetch('/api/collab/unlock', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ elementId: id }),
        }), target).catch(() => {})
      }
      await ca.close().catch(() => {}); await cb.close()
    }
  })

  /**
   * US4-3 · US5-2 — **AI 챗 왕복.** 프롬프트를 치고, LLM 초안을 받고, 승인을 누른다.
   *
   * 여기가 인수조건 중 마지막으로 안 지나간 자리다. 지금까지는
   * `/api/chat/confirm` 까지만 쟀다 — 그건 "승인하면 적용된다"를 잰 것이지
   * **사람이 챗으로 고칠 수 있다**를 잰 것이 아니다.
   *
   * ## 실 데이터를 고친다 — 되돌리기를 먼저 만든다
   *
   * 이 검사는 진짜 요소의 값을 바꾼다. 앞서 한 번, 되돌리지 않은 UI 검사가
   * UserStory 넉 장의 본문을 깨뜨렸다. 그래서 **되돌리기가 실패하면 이 검사도
   * 실패한다.**
   */
  test('AI 챗 왕복 — 프롬프트 · 초안 · 승인이 상대 창까지 간다', async ({ browser }) => {
    test.setTimeout(420_000)
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    const stamp = `동시편집 검사 ${Date.now()}`
    let target: string | null = null
    let before: any = null

    const dataOf = (page: Page, id: string) => page.evaluate(async (nid) => {
      const { useCanvasStore } = await import('/src/features/canvas/canvas.store.js')
      const n: any = (useCanvasStore().nodes || []).find((x: any) => x.id === nid)
      const d = n?.data || {}
      return { name: d.name ?? null, description: d.description ?? null }
    }, id)

    try {
      await openBoundedContextCanvas(pa)
      const picked = await pickCanvasNode(pa)
      target = picked.id
      before = await dataOf(pa, target)
      console.log(`[two-paths] 대상 ${target} · before=${JSON.stringify(before)}`)

      // bob 도 같은 캔버스를 본다 — 승인 뒤 **그의 화면**에서 확인한다
      await openBoundedContextCanvas(pb)
      await expect(pb.locator(`.vue-flow__node[data-id="${target}"]`),
        'test 창 캔버스에 같은 노드가 없다').toHaveCount(1, { timeout: 20_000 })

      // ── 프롬프트 ──
      const node = pa.locator('.vue-flow__node').nth(picked.index)
      await node.scrollIntoViewIfNeeded().catch(() => {})
      await node.click({ force: true, timeout: 20_000 })
      const chatPanel = pa.locator('.chat-panel')
      if (!(await chatPanel.isVisible({ timeout: 3_000 }).catch(() => false))) {
        await pa.locator('.right-sidebar [title="Chat"]').first().click()
      }
      await expect(chatPanel, '챗 패널이 안 열린다').toBeVisible({ timeout: 20_000 })
      expect(await chipIdsOf(pa), '캔버스에서 골랐는데 칩에 안 올라왔다').toContain(target)

      const input = pa.locator('.chat-input__textarea')
      await expect(input, '아무도 안 잡았는데 입력칸이 막혀 있다').toBeEnabled({ timeout: 15_000 })
      await input.fill(`이 요소의 description 을 정확히 "${stamp}" 로 바꿔줘. 다른 필드는 건드리지 마.`)
      await pa.locator('.chat-input__send').click()

      // ── 초안 ── LLM 왕복이다. 넉넉히 기다리되 **왜 못 받았는지**를 남긴다.
      const apply = pa.locator('.chat-drafts__apply')
      try {
        await expect(apply).toBeVisible({ timeout: 180_000 })
      } catch {
        const sys = await pa.locator('.chat-message__content').allTextContents()
        throw new Error('LLM 초안이 안 왔다 — 화면에 남은 말: ' + JSON.stringify(sys.slice(-3)))
      }

      // ── 승인 ──
      await apply.click()
      await expect
        .poll(() => dataOf(pb, target!).then((d) => JSON.stringify(d)), {
          timeout: 120_000,
          message: '승인했는데 test 창에 그 변경이 안 나타난다',
        })
        .not.toBe(JSON.stringify(before))

      const after = await dataOf(pb, target)
      console.log(`[two-paths] after(test 창)=${JSON.stringify(after)}`)
      // **개수가 아니라 내용으로 잰다.** "뭔가 바뀌었다"로 끝내면 엉뚱한 필드가
      // 바뀌어도 통과한다.
      expect(JSON.stringify(after),
        `승인한 내용이 안 보인다 — before=${JSON.stringify(before)} after=${JSON.stringify(after)}`)
        .toContain(stamp)
    } finally {
      // ── 되돌리기 — **실패하면 이 검사도 실패한다** ──
      if (target && before) {
        const restored = await pa.evaluate(async (t: any) => {
          const r = await fetch(`/api/graph/update-node/${t.id}`, {
            method: 'PUT',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ name: t.before.name, description: t.before.description }),
          })
          return { status: r.status, body: (await r.text()).slice(0, 200) }
        }, { id: target, before }).catch((e) => ({ status: -1, body: String(e) }))
        expect(restored.status,
          `되돌리기가 실패했다 — 실 데이터가 검사 값으로 남았다 (${target}): ${restored.body}`)
          .toBeLessThan(400)
      }
      await ca.close(); await cb.close()
    }
  })
})
