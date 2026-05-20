import { test } from '@playwright/test'

/**
 * Same shape as design-tab-reopen but captures FULL stack traces from
 * pageerrors so we can see *which* file/line is hitting null vnode in Vue.
 */
test('Design tab re-open — capture stack traces', async ({ page }) => {
  test.setTimeout(180_000)
  const errs: { msg: string; stack: string }[] = []
  page.on('pageerror', err => {
    errs.push({ msg: err.message.slice(0, 200), stack: (err.stack || '').slice(0, 1500) })
  })

  await page.goto('/', { waitUntil: 'networkidle' })

  const expandBtn = page.locator('.tree-action-btn[title="Expand All"]')
  if (await expandBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await expandBtn.click()
    await page.waitForTimeout(800)
  }

  const uiHeaders = page.locator('.tree-node__icon--ui').locator('..')
  const uiCount = await uiHeaders.count()
  test.skip(uiCount < 2, `Need 2+ UI nodes, got ${uiCount}`)

  async function openDesign(idx: number) {
    const header = uiHeaders.nth(idx)
    const label = (await header.locator('.tree-node__label').textContent()) || `UI-${idx}`
    console.log(`\n[trace] === Open UI[${idx}]: "${label}" ===`)
    await header.dblclick()
    await page.waitForTimeout(2000)
    const allNodes = page.locator('.vue-flow__node')
    await allNodes.nth(await allNodes.count() - 1).dblclick()
    await page.waitForTimeout(800)
    const designTab = page.locator('.inspector-tab').filter({ hasText: 'Design' })
    if (await designTab.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await designTab.click()
    }
    await page.waitForTimeout(2500)
  }

  errs.length = 0
  await openDesign(0)
  console.log(`\n[trace] First-node errors: ${errs.length}`)
  for (const e of errs.slice(0, 3)) {
    console.log(`  msg: ${e.msg}`)
    console.log(`  stack: ${e.stack.slice(0, 800)}`)
  }

  await page.locator('.vue-flow__pane').click({ position: { x: 50, y: 50 } })
  await page.waitForTimeout(1500)

  errs.length = 0
  await openDesign(1)
  console.log(`\n[trace] Second-node errors: ${errs.length}`)
  for (const e of errs.slice(0, 8)) {
    console.log(`  msg: ${e.msg}`)
    console.log(`  stack: ${e.stack.slice(0, 1500)}`)
    console.log(`  ───────`)
  }
})
