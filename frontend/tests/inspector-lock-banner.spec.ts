import { test, expect } from '@playwright/test'

/**
 * 남이 잡고 있는 요소를 열었을 때 **Inspector 가 깨지지 않는가.**
 *
 * 실제로 깨졌다. alice 가 커맨드를 먼저 열어 잠갔고, test 가 같은 커맨드를
 * 열자 패널이 통째로 죽었다.
 *
 *     Cannot set properties of null (setting '__vnode')
 *     Cannot read properties of null (reading 'nextSibling')
 *
 * 이 패널은 open-pencil federated 편집기를 품고 있어서 **트리가 흔들리는 것에
 * 취약하다** — 같은 부류의 경고가 `InspectorPanel.vue` 상단에도 적혀 있다.
 * 동시편집을 붙이며 흔드는 길을 둘 만들었다.
 *
 *     1  배너가 뿌리에 `v-if` 를 가져 노드가 주석↔요소를 오갔다
 *     2  **남이 쓸 때마다** `robo:data-changed` 가 울려 트리를 다시 그렸다
 *        전에는 인제스천 완료·초기화 때만 울렸다 — 아무도 무언가를 열어 두고
 *        있지 않은 순간이다
 *
 * 2 가 더 크다. 패널이 안 깨지더라도 **고치던 값이 남의 저장으로 초기화된다.**
 * 그래서 여기서 재는 것은 화면이 아니라 그 두 규칙이다.
 */

test.use({ storageState: { cookies: [], origins: [] } })

async function lifecycle(page: any) {
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  return page.evaluate(async () => {
    const m = await import('/src/app/lifecycle/dataLifecycle.js')
    const seen: string[] = []
    window.addEventListener('robo:data-changed', (e: any) =>
      seen.push(e?.detail?.reason))
    ;(window as any).__lc = m
    ;(window as any).__seen = seen
  })
}

test('편집 중에는 남의 변경으로 다시 그리지 않는다', async ({ page }) => {
  await lifecycle(page)

  const seen = await page.evaluate(() => {
    const m = (window as any).__lc
    const release = m.holdDataRefresh()
    m.emitDataChanged('remote-change')
    m.emitDataChanged('remote-change')
    const during = [...(window as any).__seen]
    const pending = m.hasDeferredChange()
    release()
    return { during, pending, after: [...(window as any).__seen] }
  })

  expect(seen.during, '편집 중에 울리면 고치던 값이 초기화된다').toEqual([])
  expect(seen.pending, '미뤄 뒀다는 사실은 알 수 있어야 한다').toBe(true)
  // 열 번 바뀌었어도 다시 읽는 일은 한 번이다.
  expect(seen.after, '풀리면 한 번만 울린다').toEqual(['remote-change'])
})

test('내가 일으킨 변경은 편집 중에도 즉시 울린다', async ({ page }) => {
  await lifecycle(page)

  // 인제스천을 끝낸 사람은 그 순간을 알고 있다. 미루면 결과가 안 보인다.
  const seen = await page.evaluate(() => {
    const m = (window as any).__lc
    const release = m.holdDataRefresh()
    m.emitDataChanged('ingestion-complete')
    m.emitDataChanged('cleared')
    release()
    return [...(window as any).__seen]
  })

  expect(seen).toEqual(['ingestion-complete', 'cleared'])
})

test('편집하는 화면이 둘이면 둘 다 닫혀야 푼다', async ({ page }) => {
  await lifecycle(page)

  const seen = await page.evaluate(() => {
    const m = (window as any).__lc
    const a = m.holdDataRefresh()
    const b = m.holdDataRefresh()
    m.emitDataChanged('remote-change')
    a()
    const afterFirst = [...(window as any).__seen]
    b()
    return { afterFirst, afterBoth: [...(window as any).__seen] }
  })

  expect(seen.afterFirst, '하나만 닫혔는데 울리면 남은 쪽이 초기화된다').toEqual([])
  expect(seen.afterBoth).toEqual(['remote-change'])
})

test('같은 함수를 두 번 불러도 잠금이 두 번 풀리지 않는다', async ({ page }) => {
  await lifecycle(page)

  const seen = await page.evaluate(() => {
    const m = (window as any).__lc
    const a = m.holdDataRefresh()
    const b = m.holdDataRefresh()
    a(); a(); a()          // 실수로 여러 번
    m.emitDataChanged('remote-change')
    const stillHeld = [...(window as any).__seen]
    b()
    return { stillHeld, after: [...(window as any).__seen] }
  })

  expect(seen.stillHeld, '한 쪽이 여러 번 풀면 남의 잠금까지 풀린다').toEqual([])
  expect(seen.after).toEqual(['remote-change'])
})

test('잠금 배너는 잠김 여부와 무관하게 같은 종류의 노드를 둔다', async ({ page }) => {
  /**
   * **이것은 재현된 원인이 아니라 방어선이다.** 정직하게 적어 둔다 — 배너의
   * 뿌리 `v-if` 를 되돌려도 위의 오류는 재현되지 않았다. 개수는 어느 쪽이든
   * 1이다(거짓일 때 주석 노드가 남는다).
   *
   * 그래도 뿌리를 고정해 둔 이유는, 이 자리가 federated 편집기 옆이고
   * **주석↔요소 전환이 앵커를 바꾸는 것**은 사실이기 때문이다. 비용이 0 이라
   * 남겨 둔다. 진짜 원인으로 짚은 것은 이 파일의 나머지 네 검사다.
   */
  await page.goto('/', { waitUntil: 'domcontentloaded' })

  const kinds = await page.evaluate(async () => {
    const { createApp, h, ref } = await import('/node_modules/.vite/deps/vue.js')
    const Banner = (await import('/src/features/collab/ui/LockBanner.vue')).default

    const holder = ref<any>(null)
    const mountPoint = document.createElement('div')
    document.body.appendChild(mountPoint)
    createApp({ render: () => h(Banner, { holder: holder.value }) }).mount(mountPoint)

    // 1 = 요소 · 8 = 주석. 이 값이 오가면 앵커가 바뀐다.
    const kind = () => [...mountPoint.childNodes].map((n) => n.nodeType)
    const before = kind()
    holder.value = { uid: 'A', displayName: '앨리스' }
    await new Promise((r) => setTimeout(r, 60))
    const during = kind()
    const barVisible = !!mountPoint.querySelector('.lockbar')
    holder.value = null
    await new Promise((r) => setTimeout(r, 60))
    return { before, during, after: kind(), barVisible }
  })

  expect(kinds.barVisible, '배너가 아예 안 뜨면 위 셋은 아무것도 안 잰 것이다').toBe(true)
  expect([kinds.before, kinds.during, kinds.after],
    '뿌리가 주석↔요소로 오가면 옆 형제의 앵커가 바뀐다')
    .toEqual([[1], [1], [1]])
})
