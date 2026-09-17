import { test, expect, type Page } from '@playwright/test'
import {
  login, sharedGraph, openApp, waitConnected, openAnyElement, serverLocks, type Who,
} from './helpers/collab'

/**
 * **선점은 시계가 아니라 접속으로 재야 한다.**
 *
 * 지금 잠금의 수명을 정하는 것은 둘인데 **둘 다 사람이 거기 있는지를 안 본다.**
 *
 *     LOCK_TTL_SECONDS = 60      마지막 갱신에서 60초. 갱신은 SSE 스트림만 한다
 *     스트림 종료 시 release_all  **스트림이 끊기는 순간 잠금을 놓는다**
 *
 * 둘째가 훨씬 사납다. 절전·프록시·재연결 백오프로 스트림이 잠깐 끊기면, 사람은
 * 화면 앞에 앉아 글자를 치고 있는데 **서버는 그 순간 잠금을 놓아 버린다.** 60초를
 * 기다리지도 않는다. 그 틈에 남이 집어가면 돌아온 사람은 저장할 때 409 를 맞는다.
 *
 * 반대쪽도 있다 — 스트림 종료를 서버가 못 보면(반열림 연결·백엔드 재시작) 잠금은
 * 최대 60초를 더 산다.
 *
 * 재야 하는 것은 **"몇 초가 지났나"가 아니라 "그 사람이 아직 붙어 있나"** 다.
 *
 * spec: `specs/057-presence-bound-element-lock/`
 */

/** 끊긴 채로 버티는 시간. **60초보다 길어야 한다** — 짧게 잡으면 TTL 벽이
 *  그대로 있어도 통과해서, 이 검사가 재려던 것을 안 재게 된다. */
const OUTAGE_MS = 70_000

test.use({ storageState: { cookies: [], origins: [] } })

/** 남의 창에서 이 요소를 집어 본다. **집히면 안 되는 것을 집히는지로 잰다.** */
async function tryTake(page: Page, elementId: string) {
  return page.evaluate(async (id) => {
    const r = await fetch('/api/collab/lock', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ elementId: id, label: 'lifetime 검사' }),
    })
    return { status: r.status, body: await r.json().catch(() => ({})) }
  }, elementId)
}

/** 서버가 아는 이 요소의 주인. 없으면 null. */
async function holderOf(page: Page, elementId: string): Promise<string | null> {
  const locks = await serverLocks(page)
  return locks.find((l: any) => l.elementId === elementId)?.uid ?? null
}

/**
 * 주인과 **언제부터 잡고 있나**. 둘을 같이 봐야 한다.
 *
 * 주인만 보면 "한 번도 안 놓았다"와 "놓았는데 곧바로 되집었다"가 구별되지
 * 않는다. 실제로 그랬다 — `finally` 에서 놓는 결함을 심었는데도 검사가
 * 통과했다. 화면이 5초마다 상태를 받아 되집기 때문이다. 그 사이에 남이
 * 집으면 작업이 날아가므로 **놓은 적이 있다는 것 자체가 결함이다.**
 * 되집으면 `acquired_at` 이 새로 찍히므로 그것으로 가른다.
 */
async function holdOf(page: Page, elementId: string): Promise<{ uid: string | null; since: string | null }> {
  const l = (await serverLocks(page)).find((x: any) => x.elementId === elementId)
  return { uid: l?.uid ?? null, since: l?.since ?? null }
}

test.describe('선점 수명 — 접속에 묶인다', () => {
  let alice: Who, tester: Who, graph: string

  test.beforeAll(async () => {
    ;[alice, tester] = await Promise.all([login('alice'), login('test')])
    graph = await sharedGraph(alice, tester)
    console.log(`[lifetime] ${alice.uid} · ${tester.uid} · graph=${graph}`)
  })

  /**
   * US1 — 스트림이 죽어도 **앱이 살아 있으면** 선점은 내 것이다.
   *
   * 스트림만 끊고 보통 HTTP 는 살려 둔다. 그게 실제로 가장 흔한 모양이다
   * (프록시가 SSE 만 끊는다 · 재연결 백오프 30초 · 절전에서 깬 직후).
   * **오프라인으로 만들면 안 된다** — 그건 사람이 정말 사라진 것이고, 그때는
   * 잠금이 풀리는 것이 맞다. 여기서 재는 것은 그 반대 경우다.
   */
  test('스트림이 끊겨도 앱이 살아 있으면 선점이 유지된다', async ({ browser }) => {
    test.setTimeout(240_000)
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    let elementId: string | null = null
    try {
      elementId = await openAnyElement(pa)
      const held0 = await holdOf(pb, elementId)
      expect(held0.uid, '열었는데 서버에 alice 잠금이 없다').toBe(alice.uid)
      expect(held0.since, '잡은 시각이 없으면 연속성을 못 잰다').toBeTruthy()

      // ── 스트림만 끊는다 ────────────────────────────────────────────────
      // 새 스트림은 막고(재연결 실패), 열려 있던 것은 닫는다. 서버는 이것을
      // **끊긴 것**으로 본다 — 사람이 떠난 것과 구별해야 하는 바로 그 사건이다.
      await pa.route('**/api/collab/stream*', (r) => r.abort())
      await pa.evaluate(() => (window as any).__collab?.close?.(false))
      await expect
        .poll(() => pa.evaluate(() => !!(window as any).__collab?.connected),
          { timeout: 15_000, message: '스트림을 끊었는데 화면은 아직 붙어 있다고 한다' })
        .toBe(false)

      // ── 60초보다 오래 버틴다 ──────────────────────────────────────────
      const started = Date.now()
      const gaps: string[] = []
      while (Date.now() - started < OUTAGE_MS) {
        await pa.waitForTimeout(2_000)
        const h = await holdOf(pb, elementId)
        const t = Math.round((Date.now() - started) / 1000)
        // **한 번이라도 비거나 잡은 시각이 바뀌면 놓은 것이다.**
        if (h.uid !== alice.uid || h.since !== held0.since) {
          gaps.push(`+${t}s ${h.uid ?? '없음'}/${h.since ?? '-'}`)
        }
        if (t % 10 === 0) console.log(`[lifetime] +${t}s holder=${h.uid ?? '없음'}`)
      }

      // ① 끊긴 내내 **놓은 적이 없어야 한다**
      expect(gaps,
        `스트림이 끊긴 동안 alice 의 선점이 끊겼다 — 그 틈에 남이 집으면 작업이 날아간다: ${gaps.join(' · ')}`)
        .toEqual([])
      const heldEnd = await holdOf(pb, elementId)
      expect(heldEnd.uid, `${OUTAGE_MS / 1000}초 뒤 alice 의 선점이 사라졌다`).toBe(alice.uid)
      expect(heldEnd.since, '잡은 시각이 바뀌었다 — 한 번 놓았다가 되집은 것이다')
        .toBe(held0.since)

      // ② **남이 집으면 안 된다.** ①만 재면 "목록에는 남아 있는데 아무나 집을
      //    수 있는" 상태를 통과시킨다.
      const stolen = await tryTake(pb, elementId)
      expect(stolen.body?.ok,
        `alice 가 붙어 있는데 test 가 선점을 가져갔다 (${JSON.stringify(stolen.body)})`)
        .toBe(false)
      expect(stolen.body?.uid, '못 집었는데 주인이 alice 가 아니다').toBe(alice.uid)
    } finally {
      await pa.unroute('**/api/collab/stream*').catch(() => {})
      if (elementId) {
        await pa.evaluate((id) => fetch('/api/collab/unlock', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ elementId: id }),
        }), elementId).catch(() => {})
      }
      await ca.close(); await cb.close()
    }
  })

  /**
   * US2-1 — 창을 정상적으로 닫으면 **즉시** 풀린다.
   *
   * 위(US1)를 고치느라 "끊겨도 안 푼다"로 바꾸면 이쪽이 조용히 망가진다.
   * 두 개를 같이 잰다 — **막는 것만 재면 전부 잠가 놓고도 통과한다.**
   */
  test('창을 닫으면 선점이 즉시 사라진다', async ({ browser }) => {
    test.setTimeout(180_000)
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    try {
      const elementId = await openAnyElement(pa)
      expect(await holderOf(pb, elementId), '열었는데 서버에 alice 잠금이 없다').toBe(alice.uid)

      // **문서를 실제로 내린다.** `context.close()` 로는 이걸 못 잰다 —
      // Playwright 가 컨텍스트를 통째로 걷어내서 `keepalive` 요청이 나가기 전에
      // 사라진다. 그건 "정상 종료"가 아니라 **강제 종료**이고, 바로 아래 검사가
      // 따로 재는 갈래다. 여기서 재려는 것은 창이 떠나면서 알려 주고 가는 길
      // (`pagehide` → `/api/collab/leave`)이다.
      await pa.goto('about:blank', { waitUntil: 'domcontentloaded' })

      // **유예를 기다리지 않는다.** 정상 종료는 알려 주고 가는 것이므로 즉시다.
      await expect
        .poll(() => holderOf(pb, elementId), {
          timeout: 12_000,
          message: '창을 닫았는데 선점이 남아 있다 — 아무도 그 요소를 못 고친다',
        })
        .toBeNull()

      const mine = await tryTake(pb, elementId)
      expect(mine.body?.ok, '창을 닫았는데 test 가 못 집는다').toBe(true)
      await pb.evaluate((id) => fetch('/api/collab/unlock', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ elementId: id }),
      }), elementId)
    } finally {
      await ca.close().catch(() => {}); await cb.close()
    }
  })

  /**
   * US2-2 — 브라우저를 **강제 종료**하면 유예 안에 사라진다.
   *
   * 정상 종료 경로(`leave`)가 안 도는 갈래다. 여기서 안 풀리면 그 요소는
   * 아무도 못 고친다 — 이 저장소가 가장 자주 내는 부류의 고장이다.
   */
  test('브라우저를 강제로 죽여도 선점이 남지 않는다', async ({ browser, playwright }) => {
    test.setTimeout(180_000)
    // 죽일 브라우저는 **따로 띄운다.** 공용 브라우저를 죽이면 나머지 검사가
    // 같이 죽는다.
    //
    // `launchServer` 로 띄우는 이유는 **프로세스를 잡아야 하기 때문**이다.
    // `browser.close()` 는 강제 종료가 아니다 — 문서를 정상적으로 내리므로
    // `pagehide` 가 돌고 `/api/collab/leave` 가 나간다. 그걸로 재면 바로 위
    // 검사(정상 종료)를 한 번 더 재는 셈이고, 실제로 그렇게 써서 **결함을
    // 심어도 안 무는 검사**를 만들 뻔했다.
    const server = await playwright.chromium.launchServer()
    const victim = await playwright.chromium.connect(server.wsEndpoint())
    const cv = await victim.newContext()
    const cb = await browser.newContext()
    const pv = await openApp(cv, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pv, 'alice')
    await waitConnected(pb, 'test')

    let elementId: string | null = null
    try {
      elementId = await openAnyElement(pv)
      expect(await holderOf(pb, elementId), '열었는데 서버에 alice 잠금이 없다').toBe(alice.uid)

      // **프로세스를 죽인다.** 알려 주고 갈 틈을 안 준다.
      server.process().kill('SIGKILL')

      await expect
        .poll(() => holderOf(pb, elementId), {
          timeout: 60_000,   // 유예(25초) + 여유. **60초 TTL 로는 못 잰다**
          message: '브라우저를 죽였는데 선점이 안 풀린다',
        })
        .toBeNull()
    } finally {
      if (elementId) {
        await pb.evaluate((id) => fetch('/api/collab/unlock', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ elementId: id }),
        }), elementId).catch(() => {})
      }
      await server.close().catch(() => {}); await cb.close()
    }
  })
})

/**
 * US3 — **끊긴 것을 화면이 말한다.**
 *
 * 선점의 수명이 "붙어 있나"로 정해지므로, 두 채널이 다 끊긴 채로 오래 있으면
 * 편집권을 잃는다. 그 사실을 화면이 안 알리면 사람은 **잃을 글자를 계속 친다** —
 * 이 저장소가 반복해서 낸 고장이 정확히 그 모양이다(서버는 아는데 화면이
 * 아무 말도 안 한다).
 */
test.describe('선점 수명 — 화면이 말한다', () => {
  let alice: Who, tester: Who, graph: string

  test.beforeAll(async () => {
    ;[alice, tester] = await Promise.all([login('alice'), login('test')])
    graph = await sharedGraph(alice, tester)
  })

  test('스트림이 끊기면 위험을 알리고, 돌아오면 사라진다', async ({ browser }) => {
    test.setTimeout(180_000)
    const ca = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    await waitConnected(pa, 'alice')

    try {
      const elementId = await openAnyElement(pa)
      const risk = pa.locator('.inspector-panel .lockbar--risk')
      const taken = pa.locator('.inspector-panel .lockbar:not(.lockbar--risk)')

      // 붙어 있을 때는 **아무 말도 없어야 한다.** 이걸 안 재면 늘 띄워 놓고도 통과한다.
      await expect(risk, '멀쩡히 붙어 있는데 경고가 떠 있다').toHaveCount(0)

      await pa.route('**/api/collab/stream*', (r) => r.abort())
      await pa.evaluate(() => (window as any).__collab?.close?.(false))

      await expect(risk, '스트림이 끊겼는데 화면이 아무 말도 안 한다')
        .toBeVisible({ timeout: 30_000 })
      await expect(risk).toContainText('연결이 끊겼습니다')
      // **남이 잡았을 때의 배너와 섞이면 안 된다** — 원인이 다르고 할 일도 다르다.
      await expect(taken, '끊긴 것을 "남이 편집 중"으로 말하고 있다').toHaveCount(0)

      // 끊긴 동안에도 **고칠 수는 있어야 한다.** 아직 뺏긴 것이 아니다.
      const openFields = await pa.evaluate(() => {
        const panel = document.querySelector('.inspector-panel')
        const fields = [...(panel?.querySelectorAll('input, textarea, select') || [])]
          .filter((el: any) => el.type !== 'hidden' && el.offsetParent !== null)
        return { total: fields.length, open: fields.filter((el: any) => !el.matches(':disabled') && !el.readOnly).length }
      })
      expect(openFields.total, '입력칸이 없으면 아무것도 안 잰 것이다').toBeGreaterThan(0)
      expect(openFields.open, '끊겼을 뿐인데 입력칸을 잠갔다').toBe(openFields.total)

      // ── 돌아온다 ──
      await pa.unroute('**/api/collab/stream*')
      await pa.evaluate((g) => (window as any).__collab?.watch?.(g), graph)
      await expect(risk, '연결이 돌아왔는데 경고가 안 사라진다').toHaveCount(0, { timeout: 30_000 })
      expect(await holderOf(pa, elementId), '돌아왔더니 내 선점이 아니다').toBe(alice.uid)

      await pa.evaluate((id) => fetch('/api/collab/unlock', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ elementId: id }),
      }), elementId)
    } finally {
      await ca.close()
    }
  })

  /**
   * 정말 사라졌다 돌아오면 — **뺏긴 것을 숨기지 않는다.**
   *
   * 여기서는 스트림만이 아니라 **모든 길**을 끊는다. 그게 사람이 정말 없는
   * 것이고, 그때는 선점이 풀리는 것이 맞다. 위 검사와 정확히 반대쪽이다.
   */
  test('정말 끊겼다 돌아오면 누가 가져갔는지 보인다', async ({ browser }) => {
    test.setTimeout(240_000)
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    let elementId: string | null = null
    try {
      elementId = await openAnyElement(pa)
      expect(await holderOf(pb, elementId), '열었는데 서버에 alice 잠금이 없다').toBe(alice.uid)

      // **두 채널을 다 끊는다.** 심장박동도 못 나간다 → 서버는 alice 가 없다고 본다.
      await ca.setOffline(true)
      await expect
        .poll(() => holderOf(pb, elementId!), {
          timeout: 60_000,
          message: 'alice 가 완전히 끊겼는데도 선점이 안 풀린다 — 아무도 그 요소를 못 고친다',
        })
        .toBeNull()

      const took = await tryTake(pb, elementId)
      expect(took.body?.ok, '풀렸는데 test 가 못 집는다').toBe(true)

      // alice 가 돌아온다
      await ca.setOffline(false)
      await pa.evaluate((g) => (window as any).__collab?.watch?.(g), graph)

      await expect(pa.locator('.inspector-panel .lockbar:not(.lockbar--risk)'),
        '뺏겼는데 alice 화면이 아무 말도 안 한다')
        .toBeVisible({ timeout: 40_000 })
      await expect(pa.locator('.inspector-panel .lockbar:not(.lockbar--risk)'))
        .toContainText('편집 중')

      // **입력칸도 잠겨야 한다.** 배너만 뜨고 칠 수 있으면 글자가 사라진다.
      await expect
        .poll(() => pa.evaluate(() => {
          const panel = document.querySelector('.inspector-panel')
          const fields = [...(panel?.querySelectorAll('input, textarea, select') || [])]
            .filter((el: any) => (el as any).type !== 'hidden' && (el as any).offsetParent !== null)
          return fields.length ? fields.filter((el: any) => el.matches(':disabled') || el.readOnly).length / fields.length : 0
        }), { timeout: 20_000, message: '뺏겼는데 입력칸이 열려 있다' })
        .toBe(1)
    } finally {
      await ca.setOffline(false).catch(() => {})
      if (elementId) {
        await pb.evaluate((id) => fetch('/api/collab/unlock', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ elementId: id }),
        }), elementId).catch(() => {})
      }
      await ca.close(); await cb.close()
    }
  })
})
