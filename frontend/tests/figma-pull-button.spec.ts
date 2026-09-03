import { test, expect } from '@playwright/test'

/**
 * "Figma 에서 가져오기" 버튼이 실제로 화면에 뜨는지.
 *
 * 버튼은 두 곳에 있고 조건이 서로 다르다.
 *   UI Preview 탭 — `node.data.figmaNodeId` 가 있을 때 'Figma: <id>' 옆
 *   Design 탭     — FrameEditor 의 `.frame-editor__pull-btn`
 *                   (`hasFigmaConnection` 이 참일 때만 on-pull 이 전달된다)
 *
 * 코드에 있다는 것과 뜬다는 것은 다르다. 투영이 필드를 빼면 조건이 조용히
 * 거짓이 되고, 아무 오류 없이 버튼만 사라진다 — 실제로 그랬다.
 */
test.describe('Figma pull button', () => {
  test.setTimeout(180_000)

  test('renders on a UI node that carries figmaNodeId', async ({ page, request }) => {
    // 그래프에서 figmaNodeId 를 가진 UI 이름을 하나 고른다.
    const bcResp = await request.get('http://localhost:8000/api/contexts')
    expect(bcResp.ok()).toBeTruthy()
    const bcs = await bcResp.json()
    const list = Array.isArray(bcs) ? bcs : (bcs.contexts || bcs.items || [])
    expect(list.length).toBeGreaterThan(0)

    let target: { name: string; displayName: string; figmaNodeId: string } | null = null
    for (const bc of list) {
      const r = await request.get(`http://localhost:8000/api/graph/expand-with-bc/${bc.id}`)
      if (!r.ok()) continue
      const g = await r.json()
      const hit = (g.nodes || []).find((n: any) => n.type === 'UI' && n.figmaNodeId)
      if (hit) { target = { name: hit.name, displayName: hit.displayName || hit.name, figmaNodeId: hit.figmaNodeId }; break }
    }
    expect(target, 'figmaNodeId 를 가진 UI 가 그래프에 있어야 한다').not.toBeNull()
    console.log(`[test] target UI "${target!.name}" figmaNodeId=${target!.figmaNodeId}`)

    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('#app')).toBeVisible()

    // UI 노드의 더블클릭은 탭을 바꾸지 않는다 — Design 탭이 떠 있어야 캔버스가 산다.
    const designTopTab = page.locator('.top-bar__tab, .app-tab, button').filter({ hasText: /^Design$/ }).first()
    if (await designTopTab.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await designTopTab.click()
      await page.waitForTimeout(1500)
    }

    const expandBtn = page.locator('.tree-action-btn[title="Expand All"]')
    // 트리는 지연 로딩이라 한 번의 Expand All 로는 UI 깊이까지 안 내려간다.
    for (let i = 0; i < 4; i++) {
      if (await expandBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await expandBtn.click()
        await page.waitForTimeout(2500)
      }
      if (await page.locator('.tree-node__icon--ui').count() > 0) break
    }
    const uiNames = await page.locator('.tree-node__icon--ui').locator('..')
      .locator('.tree-node__label').allTextContents()
    console.log(`[test] 트리의 UI ${uiNames.length}개: ${uiNames.slice(0, 8).join(', ')}`)

    // 트리는 유비쿼터스 언어 모드에서 displayName 을 쓴다 — 둘 다 받는다.
    const rows = page.locator('.tree-node__icon--ui').locator('..')
    let header = rows.filter({ hasText: target!.displayName }).first()
    if (!(await header.count())) header = rows.filter({ hasText: target!.name }).first()
    await expect(header).toBeVisible({ timeout: 15_000 })
    await header.dblclick()
    await page.waitForTimeout(2500)

    const cnodes = page.locator('.vue-flow__node')
    console.log(`[test] 캔버스 노드 ${await cnodes.count()}개: ${(await cnodes.allTextContents()).slice(0, 10).map(t => t.replace(/\s+/g, ' ').slice(0, 24)).join(' | ')}`)
    let canvasNode = cnodes.filter({ hasText: target!.displayName }).first()
    if (!(await canvasNode.count())) canvasNode = cnodes.filter({ hasText: target!.name }).first()
    await expect(canvasNode).toBeVisible({ timeout: 15_000 })
    await canvasNode.dblclick()
    await page.waitForTimeout(1500)

    // ── UI Preview 탭 ──
    const previewTab = page.locator('.inspector-tab').filter({ hasText: 'UI Preview' }).first()
    await expect(previewTab).toBeVisible({ timeout: 10_000 })
    await previewTab.click()
    await page.waitForTimeout(1000)

    // 'Figma: <id>' 줄이 떠야 투영이 필드를 실은 것이다.
    await expect(page.getByText(target!.figmaNodeId, { exact: false }).first())
      .toBeVisible({ timeout: 10_000 })

    const previewPull = page.locator('button[title="Figma에서 가져오기"]')
    await expect(previewPull).toBeVisible({ timeout: 10_000 })
    console.log('[test] UI Preview 탭 가져오기 버튼 — 보임')

    // 내보내기는 오래도록 Design 탭 저장에 딸려 나가기만 했다 — 짝이 없으면
    // 한쪽만 되는 것처럼 보인다. 둘 다 있어야 한다.
    const previewPush = page.locator('button[title="Figma로 내보내기"]')
    await expect(previewPush).toBeVisible({ timeout: 10_000 })
    console.log('[test] UI Preview 탭 내보내기 버튼 — 보임')

    // 'Copy design to Figma clipboard' 는 항상 칠해져 있어서 손을 올리지도
    // 않았는데 눌린 것처럼 보였다. 쉴 때는 형제 버튼들과 같아야 한다.
    const figmaClip = page.locator('.ui-preview-panel__btn--figma').first()
    await expect(figmaClip).toBeVisible({ timeout: 10_000 })
    const bg = (el) => el.evaluate((n) => getComputedStyle(n).backgroundColor)
    const sibling = page.locator('.ui-preview-panel__actions .ui-preview-panel__btn')
      .filter({ hasNot: page.locator('.ui-preview-panel__btn--figma') }).first()
    const restFigma = await bg(figmaClip)
    const restSibling = await bg(sibling)
    console.log(`[test] 쉴 때 배경 — figma ${restFigma} / 형제 ${restSibling}`)
    expect(restFigma, '쉴 때 배경이 형제 버튼과 같아야 한다').toBe(restSibling)

    await figmaClip.hover()
    await page.waitForTimeout(400)
    const hoverFigma = await bg(figmaClip)
    console.log(`[test] hover 배경 — ${hoverFigma}`)
    expect(hoverFigma, 'hover 에서는 칠해져야 한다').not.toBe(restFigma)
    // 마우스를 치워 다음 단계에 영향이 없게 한다.
    await page.mouse.move(0, 0)

    // 내보내기가 실제로 어디를 부르는지 — 실제 Figma 파일은 건드리지 않는다.
    let pushedUrl = ''
    await page.route('**/api/figma-binding/update-frame/**', async (route) => {
      pushedUrl = route.request().url()
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, nodesCreated: 7 }),
      })
    })
    await previewPush.click()
    await expect(page.getByText('Figma로 내보냄', { exact: false }).first())
      .toBeVisible({ timeout: 10_000 })
    expect(pushedUrl).toContain('/api/figma-binding/update-frame/')
    console.log(`[test] 내보내기 호출 → ${pushedUrl.replace(/^https?:\/\/[^/]+/, '')}`)
    await page.unroute('**/api/figma-binding/update-frame/**')

    // ── Design 탭 ──
    const designTab = page.locator('.inspector-tab').filter({ hasText: 'Design' }).first()
    await designTab.click()
    const frameEditor = page.locator('.frame-editor')
    const editorUp = await frameEditor.isVisible({ timeout: 30_000 }).catch(() => false)
    if (editorUp) {
      await expect(page.locator('.frame-editor__pull-btn')).toBeVisible({ timeout: 10_000 })
      console.log('[test] Design 탭 가져오기 버튼 — 보임')
    } else {
      // sceneGraph 가 없으면 편집기 자체가 안 뜬다 — 버튼 조건과 무관하다.
      console.log('[test] FrameEditor 미표시(sceneGraph 없음) — Design 탭 검사 생략')
    }
  })
})
