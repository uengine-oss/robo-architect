import { test, expect } from '@playwright/test'

/**
 * 서버가 돌려준 변경이 **화면에 실제로 반영되는가.**
 *
 * 실측으로 드러난 일 — Inspector 에서 `displayName` 을 고치고 저장하면
 *
 *     서버       적용됨. appliedChanges 에 {updates:{displayName:"…ㅇㅇ"}}
 *     내 화면    그대로
 *     남의 화면  그대로
 *
 * `syncAfterChanges` 가 **평평한 필드만** 읽고 `change.updates` 를 안 봤다.
 * 원격 반영을 붙이면서 드러났을 뿐, 원래부터 자기 창에서도 안 됐다.
 *
 * 그래서 여기서 재는 것은 "함수가 뭘 돌려주나"가 아니라 **노드의 값이 바뀌나** 다.
 */

test.use({ storageState: { cookies: [], origins: [] } })

async function store(page: any) {
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  return page.evaluate(async () => {
    const m = await import('/src/features/canvas/canvas.store.js')
    const s = m.useCanvasStore()
    s.clearCanvas()
    s.addNode({ id: 'n1', name: 'BankLookup', type: 'Command',
                displayName: '은행 조회', description: '옛 설명' })
    ;(window as any).__s = s
    return s.nodes.length
  })
}

test('updates 안의 값이 노드에 반영된다', async ({ page }) => {
  expect(await store(page)).toBe(1)

  const after = await page.evaluate(() => {
    const s = (window as any).__s
    s.syncAfterChanges([{
      action: 'update', targetId: 'n1', targetType: 'Command',
      updates: { displayName: '은행/결제사 정보 조회ㅇㅇ' },
    }])
    const n = s.nodes.find((x: any) => x.id === 'n1')
    return { displayName: n?.data?.displayName, name: n?.data?.name }
  })

  expect(after.displayName, 'updates 를 안 보면 화면이 그대로다')
    .toBe('은행/결제사 정보 조회ㅇㅇ')
  // 안 건드린 필드는 그대로여야 한다 — updates 를 통째로 덮으면 나머지가 날아간다.
  expect(after.name).toBe('BankLookup')
})

test('updates 의 이름이 라벨까지 따라간다', async ({ page }) => {
  await store(page)
  const after = await page.evaluate(() => {
    const s = (window as any).__s
    s.syncAfterChanges([{
      action: 'rename', targetId: 'n1', targetType: 'Command',
      updates: { name: 'BankInquiry' },
    }])
    const n = s.nodes.find((x: any) => x.id === 'n1')
    return { name: n?.data?.name, label: n?.data?.label }
  })
  expect(after).toEqual({ name: 'BankInquiry', label: 'BankInquiry' })
})

test('옛 평평한 모양도 계속 받는다', async ({ page }) => {
  // 다른 생산자들이 아직 이 모양으로 보낸다. 깨뜨리면 그쪽이 조용히 멈춘다.
  await store(page)
  const after = await page.evaluate(() => {
    const s = (window as any).__s
    s.syncAfterChanges([{
      action: 'update', targetId: 'n1', targetType: 'Command',
      targetName: 'Flat', description: '새 설명',
    }])
    const n = s.nodes.find((x: any) => x.id === 'n1')
    return { name: n?.data?.name, description: n?.data?.description }
  })
  expect(after).toEqual({ name: 'Flat', description: '새 설명' })
})
