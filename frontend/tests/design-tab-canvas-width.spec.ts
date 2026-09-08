import { test, expect } from '@playwright/test'
import { writeFileSync } from 'fs'

/**
 * Design 탭의 편집 캔버스가 쓸 만한 폭을 갖는지.
 *
 * FrameEditor 의 속성 패널은 **요소를 선택했을 때만** 뜨고 260px 을 고정으로
 * 가져간다. 인스펙터 폭이 360px 이라 본문이 325px 밖에 안 되고, 선택하는
 * 순간 캔버스가 **65px** 로 찌그러졌다 — 하필 그릴 자리가 가장 필요한 때다.
 * 편집기는 멀쩡히 마운트되니 오류로는 안 보이고, "제대로 동작하지 않는다"로만
 * 보인다.
 */
test.describe('Design 탭 캔버스 폭', () => {
  test.setTimeout(240_000)

  test('요소를 선택해도 캔버스가 좁아지지 않는다', async ({ page, request }) => {
    const errs: string[] = []
    page.on('pageerror', e => errs.push(`pageerror: ${e.message.slice(0, 200)}`))
    page.on('console', m => {
      if (m.type() === 'error' || m.type() === 'warning') errs.push(`${m.type()}: ${m.text().slice(0, 200)}`)
    })

    const bcs = await (await request.get('http://localhost:8000/api/contexts')).json()
    let target: any = null
    for (const bc of bcs) {
      const g = await (await request.get(`http://localhost:8000/api/graph/expand-with-bc/${bc.id}`)).json()
      const hit = (g.nodes || []).find((n: any) => n.type === 'UI' && n.sceneGraph)
      if (hit) { target = hit; break }
    }
    expect(target).not.toBeNull()
    const sg = JSON.parse(target.sceneGraph)
    console.log(`[test] ${target.name} · sceneGraph 노드 ${Object.keys(sg.nodes).length} · rootId ${sg.rootId}`)

    await page.goto('/', { waitUntil: 'networkidle' })
    const designTop = page.locator('.top-bar__tab, .app-tab, button').filter({ hasText: /^Design$/ }).first()
    if (await designTop.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await designTop.click(); await page.waitForTimeout(1500)
    }
    const expandBtn = page.locator('.tree-action-btn[title="Expand All"]')
    for (let i = 0; i < 4; i++) {
      if (await expandBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await expandBtn.click(); await page.waitForTimeout(2500)
      }
      if (await page.locator('.tree-node__icon--ui').count() > 0) break
    }
    const nm = target.displayName || target.name
    const rows = page.locator('.tree-node__icon--ui').locator('..')
    let header = rows.filter({ hasText: nm }).first()
    if (!(await header.count())) header = rows.filter({ hasText: target.name }).first()
    await expect(header).toBeVisible({ timeout: 15_000 })
    await header.dblclick(); await page.waitForTimeout(2500)

    const cn = page.locator('.vue-flow__node')
    let cnode = cn.filter({ hasText: nm }).first()
    if (!(await cnode.count())) cnode = cn.filter({ hasText: target.name }).first()
    await cnode.dblclick(); await page.waitForTimeout(1500)

    // Design 탭
    await page.locator('.inspector-tab').filter({ hasText: 'Design' }).first().click()
    await page.waitForTimeout(4000)

    const states = {
      'FrameEditor 마운트': await page.locator('.frame-editor').count(),
      'Loading 표시': await page.locator('.inspector-design-editor__loading').count(),
      '디자인 없음': await page.locator('.inspector-design-editor__empty').count(),
      'canvas 요소': await page.locator('.inspector-design-editor canvas').count(),
    }
    console.log('[test] Design 탭 상태:', JSON.stringify(states, null, 0))

    if (states['canvas 요소'] > 0) {
      const box = await page.locator('.inspector-design-editor canvas').first().boundingBox()
      console.log(`[test] canvas 크기: ${box?.width}x${box?.height}`)
    }
    // 캔버스가 왜 좁은지 — 조상들의 폭을 훑는다.
    const chain = await page.locator('.inspector-design-editor canvas').first().evaluate((el) => {
      const out: any[] = []
      let n: any = el
      while (n && n.tagName !== 'BODY' && out.length < 12) {
        const r = n.getBoundingClientRect()
        const cs = getComputedStyle(n)
        out.push({
          tag: n.tagName.toLowerCase(),
          cls: (n.className || '').toString().split(' ').filter(Boolean).slice(0, 2).join('.'),
          w: Math.round(r.width), h: Math.round(r.height),
          display: cs.display, flex: cs.flex, overflow: cs.overflow, position: cs.position,
        })
        n = n.parentElement
      }
      return out
    })
    console.log('[test] 캔버스에서 위로 — 폭 사슬')
    for (const c of chain) console.log(`    ${String(c.w).padStart(5)}x${String(c.h).padStart(4)}  ${c.tag}.${c.cls}  display=${c.display} flex=${c.flex} overflow=${c.overflow}`)

    // 속성 패널은 **선택했을 때만** 뜬다. 그때가 캔버스가 가장 좁아지는 순간이다.
    const canvasEl = page.locator('.inspector-design-editor canvas').first()
    const cbox = await canvasEl.boundingBox()
    if (cbox) {
      await canvasEl.click({ position: { x: cbox.width / 2, y: cbox.height / 2 } })
      await page.waitForTimeout(1200)
    }
    const after = await canvasEl.boundingBox()
    const hasProps = await page.locator('.frame-editor__properties').count()
    console.log(`[test] 선택 후 — 속성 패널 ${hasProps}개 · canvas ${Math.round(after?.width || 0)}x${Math.round(after?.height || 0)}`)
    const bodyW = (await page.locator('.frame-editor__body').first().boundingBox())?.width || 0
    writeFileSync('/tmp/design-tab-diag.json', JSON.stringify({
      node: target.name, props: hasProps,
      canvasW: Math.round(after?.width || 0), bodyW: Math.round(bodyW),
      ratio: bodyW ? +((after?.width || 0) / bodyW).toFixed(2) : 0,
    }, null, 1))

    const sibs = await page.locator('.frame-editor__body').first().evaluate((el) => {
      return Array.from(el.children).map((c: any) => {
        const r = c.getBoundingClientRect(); const cs = getComputedStyle(c)
        return { cls: (c.className || '').toString().split(' ').slice(0, 2).join('.'),
                 w: Math.round(r.width), flex: cs.flex, minW: cs.minWidth, width: cs.width }
      })
    })
    console.log('[test] frame-editor__body 의 자식들')
    for (const s2 of sibs) console.log(`    ${String(s2.w).padStart(5)}px  ${s2.cls}  flex=${s2.flex} min-width=${s2.minW} width=${s2.width}`)

    const buttons = await page.locator('.frame-editor button').evaluateAll(
      els => els.map(e => (e.getAttribute('title') || e.textContent || '').trim().slice(0, 20)).filter(Boolean))
    console.log('[test] FrameEditor 버튼:', JSON.stringify(buttons))

    console.log('[test] 오류/경고:', errs.length)
    errs.slice(0, 8).forEach(e => console.log('   ', e))

    expect(states['FrameEditor 마운트'], 'Design 탭에 FrameEditor 가 떠야 한다').toBeGreaterThan(0)
    expect(hasProps, '선택하면 속성 패널이 떠야 한다 — 이게 0 이면 검사가 성립하지 않는다').toBeGreaterThan(0)
    const ratio = (after?.width || 0) / (bodyW || 1)
    expect(ratio, `캔버스가 편집기 폭의 80% 는 돼야 한다 (지금 ${Math.round((after?.width || 0))}/${Math.round(bodyW)})`)
      .toBeGreaterThan(0.8)
  })
})
