// E2E walkthrough for Feature 028 (aggregate-tab-drilldown).
// Playwright lives under frontend/node_modules, so run this from the frontend/
// directory:  cp specs/028-aggregate-tab-drilldown/e2e/run.mjs frontend/ && node run.mjs
// Requires the backend (:8000) and the Vite dev server (:5174) to be running.
import { chromium } from 'playwright'

const BASE = 'http://localhost:5174'
const IMG = '/Users/uengine/robo-architect/specs/028-aggregate-tab-drilldown/manual/images'
const BC_NAME = 'TermsAndAuthenticationManagement'
const AGG1 = '인증 이력'        // AuthenticationHistory (displayName)
const AGG2 = '약관 동의'        // TermsConsent (displayName)
const AGG1_ID = '933c43dc-e220-4c28-817d-2de43a44d363'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (...a) => console.log('[e2e]', ...a)

async function shot(page, name) {
  await page.screenshot({ path: `${IMG}/${name}.png`, fullPage: false })
  log('screenshot:', name)
}

async function clipShot(page, locator, name, pad = 14) {
  try {
    const box = await locator.boundingBox()
    if (!box) { log('clipShot: no box for', name); return }
    await page.screenshot({
      path: `${IMG}/${name}.png`,
      clip: {
        x: Math.max(0, box.x - pad), y: Math.max(0, box.y - pad),
        width: box.width + pad * 2, height: box.height + pad * 2,
      },
    })
    log('screenshot (clip):', name)
  } catch (e) { log('clipShot failed:', name, e.message) }
}

// HTML5 drag-and-drop with a shared DataTransfer attached via defineProperty.
async function html5Drop(page, srcHandle, tgtHandle) {
  await page.evaluate(({ s, t }) => {
    const dt = new DataTransfer()
    const fire = (el, type) => {
      const rect = el.getBoundingClientRect()
      const ev = new DragEvent(type, {
        bubbles: true, cancelable: true,
        clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2,
      })
      Object.defineProperty(ev, 'dataTransfer', { value: dt })
      el.dispatchEvent(ev)
    }
    fire(s, 'dragstart')
    fire(t, 'dragenter')
    fire(t, 'dragover')
    fire(t, 'drop')
    fire(s, 'dragend')
  }, { s: srcHandle, t: tgtHandle })
}

const tabBtn = (page, name) => page.locator('button.top-bar__tab', { hasText: name })
const bcHeader = (page) =>
  page.locator('.tree-node__header:has(.tree-node__icon--boundedcontext)', { hasText: BC_NAME }).first()
const aggHeader = (page, label) =>
  page.locator('.tree-node__header:has(.tree-node__icon--aggregate)', { hasText: label }).first()

async function run() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1680, height: 1000 } })
  page.on('pageerror', (e) => log('PAGE ERROR:', e.message))
  page.on('console', (m) => {
    const t = m.text()
    if (t.includes('AggregatePanel') || t.includes('Failed') || t.includes('aggregate')) log('PAGE:', t)
  })

  await page.goto(BASE, { waitUntil: 'networkidle' })
  await sleep(2500)
  await shot(page, '01-app-initial')

  // ---- PHASE A: Aggregate tab + BC load (US4 styling, US3 BC-drop) ----
  try {
    await tabBtn(page, 'Aggregate').click()
    await sleep(1500)
    await shot(page, '02-aggregate-tab-empty')

    const bc = bcHeader(page)
    await bc.scrollIntoViewIfNeeded()
    await bc.click()        // expand
    await sleep(700)
    await bc.dblclick()     // addToCanvas -> fetchAggregatesForBC
    await sleep(4500)
    await shot(page, '03-aggregate-bc-loaded')
    await clipShot(page, page.locator('.aggregate-container-node').first(), '04-aggregate-container-closeup')
  } catch (e) { log('PHASE A failed:', e.message) }

  // ---- PHASE B: single-aggregate drop (US3) ----
  try {
    await page.goto(BASE, { waitUntil: 'networkidle' })
    await sleep(2000)
    await tabBtn(page, 'Aggregate').click()
    await sleep(1200)

    const bc = bcHeader(page)
    await bc.scrollIntoViewIfNeeded()
    await bc.click()        // expand to reveal aggregate children
    await sleep(900)

    const canvasH = await page.locator('.aggregate-viewer__canvas').elementHandle()
    const agg1H = await aggHeader(page, AGG1).elementHandle()
    await html5Drop(page, agg1H, canvasH)
    await sleep(4000)
    await shot(page, '05-aggregate-dropped-single')

    const agg2H = await aggHeader(page, AGG2).elementHandle()
    await html5Drop(page, agg2H, canvasH)
    await sleep(4000)
    const countAfterTwo = await page.locator('.aggregate-container-node').count()
    log('container count after two drops:', countAfterTwo)
    await shot(page, '06-aggregate-dropped-second')

    await html5Drop(page, agg1H, canvasH)   // re-drop first → no duplicate
    await sleep(2500)
    // Fit all so both containers are visible — proves no third container.
    await page.locator('.aggregate-canvas-toolbar__btn[title="Fit View"]').click()
    await sleep(1200)
    const countAfterRedrop = await page.locator('.aggregate-container-node').count()
    log('container count after re-drop (expect 2):', countAfterRedrop)
    await shot(page, '07-aggregate-redrop-no-duplicate')
  } catch (e) { log('PHASE B failed:', e.message) }

  // ---- PHASE C: drill-down from Design tab (US1) ----
  try {
    await page.goto(BASE, { waitUntil: 'networkidle' })
    await sleep(2000)
    await tabBtn(page, 'Design').click()
    await sleep(1000)

    const bc = bcHeader(page)
    await bc.scrollIntoViewIfNeeded()
    await bc.dblclick()
    await sleep(5000)
    await shot(page, '08-design-canvas-loaded')

    // Double-click the aggregate node (by graph id) → opens the inspector.
    // dispatchEvent bypasses edge-overlay hit-testing.
    const aggNode = page.locator(`.vue-flow__node[data-id="${AGG1_ID}"]`)
    await aggNode.scrollIntoViewIfNeeded()
    await aggNode.dispatchEvent('dblclick')
    await sleep(3000)
    await shot(page, '09-design-inspector-open')

    const btn = page.locator('.inspector-aggregate-detail__btn')
    await btn.waitFor({ state: 'visible', timeout: 8000 })
    await btn.scrollIntoViewIfNeeded()
    await sleep(500)
    await clipShot(page, btn, '10-detail-button-closeup', 10)
    await shot(page, '11-design-with-detail-button')
    await btn.click()
    await sleep(5000)
    await shot(page, '12-drilldown-result')
  } catch (e) {
    log('PHASE C failed:', e.message)
    await shot(page, '12-phaseC-failure-state')
  }

  // ---- PHASE D: tab-switch carry-over (US2) ----
  try {
    await page.goto(BASE, { waitUntil: 'networkidle' })
    await sleep(2000)
    await tabBtn(page, 'Design').click()
    await sleep(1000)

    const bc = bcHeader(page)
    await bc.scrollIntoViewIfNeeded()
    await bc.dblclick()
    await sleep(5000)

    // Select the aggregate on the Design canvas (double-click selects + opens inspector).
    const aggNode = page.locator(`.vue-flow__node[data-id="${AGG1_ID}"]`)
    await aggNode.dispatchEvent('dblclick')
    await sleep(2000)
    await shot(page, '13-design-aggregate-selected')

    // Switch to the Aggregate tab via the tab bar (NOT the detail button).
    await tabBtn(page, 'Aggregate').click()
    await sleep(5000)
    await shot(page, '14-tabswitch-carryover')
  } catch (e) {
    log('PHASE D failed:', e.message)
    await shot(page, '14-phaseD-failure-state')
  }

  await browser.close()
  log('done')
}

run().catch((e) => { console.error(e); process.exit(1) })
