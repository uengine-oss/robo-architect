import { test, expect, type Page } from '@playwright/test'
import { login, sharedGraph, openApp, waitConnected, type Who } from './helpers/collab'

/**
 * **끊긴 동안 남이 고친 것을 따라잡는가.**
 *
 * 남의 변경이 화면에 오는 정밀한 길은 SSE 의 `changed` 하나뿐이다. 스트림이
 * 끊긴 동안 일어난 변경은 그 길로 **영영 안 온다** — 서버가 나중에 "그 사이에
 * 무엇이 바뀌었다"를 다시 말해 주지 않기 때문이다.
 *
 * 실측(고치기 전):
 *
 * ```
 * 끊긴 동안   rev 167 → 168 (심장박동이 가져온다)   data-changed 0건
 * 재연결 후   rev 168 그대로                        data-changed 0건
 * ```
 *
 * **오류도 빈 화면도 아니다.** 옛 값을 계속 보고, 그 위에 덮어쓴다. 이 저장소가
 * 가장 자주 내는 부류다.
 *
 * 고친 방법은 **목록 없이 "통째로 다시 읽어라"** 로 메우는 것이다(이미 있는
 * 거친 길). 정밀한 길은 스트림에만 있고, 그건 되살릴 수 없다.
 *
 * spec: `specs/057-presence-bound-element-lock/` (US5 보강)
 */

test.use({ storageState: { cookies: [], origins: [] } })

/** 남의 창에서 실제 쓰기 — 챗 확정과 같은 목(`notify.after_request`)을 지난다. */
async function writeAsOther(page: Page, id: string, description: string) {
  return page.evaluate(async (t: any) => {
    const r = await fetch(`/api/graph/update-node/${t.id}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ description: t.description }),
    })
    return r.status
  }, { id, description })
}

function seenOf(page: Page): Promise<string[]> {
  return page.evaluate(() => ((window as any).__seen || []).slice())
}

async function watchChanges(page: Page) {
  await page.evaluate(() => {
    ;(window as any).__seen = []
    window.addEventListener('robo:data-changed', (e: any) =>
      (window as any).__seen.push(e?.detail?.reason))
  })
}

test.describe('끊긴 동안의 남의 변경', () => {
  let alice: Who, tester: Who, graph: string

  test.beforeAll(async () => {
    ;[alice, tester] = await Promise.all([login('alice'), login('test')])
    graph = await sharedGraph(alice, tester)
  })

  /**
   * ① 스트림이 죽어 있어도 **심장박동이 따라잡는다.**
   *
   * 반대쪽도 같이 잰다 — 아무도 안 고쳤으면 울리지 않아야 한다. 그게 없으면
   * "매 박동마다 통째로 다시 읽기"를 해 놓고도 통과한다.
   */
  test('스트림이 죽어 있어도 심장박동이 남의 변경을 따라잡는다', async ({ browser }) => {
    test.setTimeout(240_000)
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    let target: any = null
    try {
      target = await pb.evaluate(async () => {
        const rows = await (await fetch('/api/contexts')).json().catch(() => [])
        const bc = (Array.isArray(rows) ? rows : []).find((b: any) => b?.id)
        return bc ? { id: bc.id, description: bc.description ?? '' } : null
      })
      expect(target, '고칠 BoundedContext 가 없다').not.toBeNull()

      await watchChanges(pa)
      await pa.route('**/api/collab/stream*', (r) => r.abort())
      await pa.evaluate(() => (window as any).__collab?.close?.(false))
      await expect
        .poll(() => pa.evaluate(() => !!(window as any).__collab?.connected), { timeout: 15_000 })
        .toBe(false)

      // **아무도 안 고쳤을 때는 조용해야 한다.**
      await pa.waitForTimeout(15_000)
      expect(await seenOf(pa),
        '아무도 안 고쳤는데 화면이 통째로 다시 읽는다 — 매 박동마다 읽으면 이 검사는 의미가 없다')
        .toEqual([])

      const stamp = `끊김검사 ${Date.now()}`
      expect(await writeAsOther(pb, target.id, stamp), 'test 가 저장하지 못했다').toBeLessThan(400)

      await expect
        .poll(() => seenOf(pa).then((v) => v.length), {
          timeout: 40_000,
          message: '스트림이 끊긴 동안 남이 고쳤는데 화면이 한 번도 안 울린다 — 옛 값 위에 덮어쓰게 된다',
        })
        .toBeGreaterThan(0)
      expect((await seenOf(pa))[0]).toBe('remote-change-catchup')
    } finally {
      await pa.unroute('**/api/collab/stream*').catch(() => {})
      if (target) {
        const back = await writeAsOther(pb, target.id, target.description)
        expect(back, `되돌리기가 실패했다 — 실 데이터가 검사 값으로 남았다 (${target.id})`)
          .toBeLessThan(400)
      }
      await ca.close(); await cb.close()
    }
  })

  /**
   * ② 심장박동도 못 돌았으면 **되붙는 순간**이 따라잡는다.
   *
   * 절전에서 깬 직후가 이 모양이다 — 타이머도 안 돌고 스트림도 끊겨 있다.
   * 여기서 안 메우면 그 변경은 영영 안 온다.
   */
  test('심장박동도 못 돌았으면 재연결이 따라잡는다', async ({ browser }) => {
    test.setTimeout(240_000)
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    let target: any = null
    try {
      target = await pb.evaluate(async () => {
        const rows = await (await fetch('/api/contexts')).json().catch(() => [])
        const bc = (Array.isArray(rows) ? rows : []).find((b: any) => b?.id)
        return bc ? { id: bc.id, description: bc.description ?? '' } : null
      })
      expect(target, '고칠 BoundedContext 가 없다').not.toBeNull()

      await watchChanges(pa)
      // **두 길을 다 막는다** — 스트림도 심장박동도 못 나간다.
      await pa.route('**/api/collab/stream*', (r) => r.abort())
      await pa.route('**/api/collab/state*', (r) => r.abort())
      await pa.evaluate(() => (window as any).__collab?.close?.(false))
      await pa.waitForTimeout(3_000)

      const stamp = `재연결검사 ${Date.now()}`
      expect(await writeAsOther(pb, target.id, stamp), 'test 가 저장하지 못했다').toBeLessThan(400)
      await pa.waitForTimeout(12_000)
      expect(await seenOf(pa), '두 길을 다 막았는데 화면이 울렸다 — 검사가 재려던 상태가 아니다')
        .toEqual([])

      // 돌아온다
      await pa.unroute('**/api/collab/state*')
      await pa.unroute('**/api/collab/stream*')
      await pa.evaluate((g) => (window as any).__collab?.watch?.(g), graph)

      await expect
        .poll(() => seenOf(pa).then((v) => v.length), {
          timeout: 40_000,
          message: '되붙었는데 끊긴 동안의 변경을 안 따라잡는다 — 조용히 옛 값을 본다',
        })
        .toBeGreaterThan(0)
    } finally {
      await pa.unroute('**/api/collab/state*').catch(() => {})
      await pa.unroute('**/api/collab/stream*').catch(() => {})
      if (target) {
        const back = await writeAsOther(pb, target.id, target.description)
        expect(back, `되돌리기가 실패했다 — 실 데이터가 검사 값으로 남았다 (${target.id})`)
          .toBeLessThan(400)
      }
      await ca.close(); await cb.close()
    }
  })
})
