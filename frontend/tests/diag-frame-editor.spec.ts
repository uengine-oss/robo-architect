import { test, expect } from '@playwright/test'

/**
 * Diagnostic / regression test for the "Loading design editor..." stuck state.
 *
 * Root cause: `deserializeSceneGraph` was calling `Object.entries(data.nodes)` and
 * `Object.entries(data.images)` without null-guards. If a stored sceneGraph was
 * missing either field, setup() of FrameEditor threw — and the parent <Suspense>
 * stayed in its "Loading design editor..." fallback forever.
 *
 * This suite verifies deserializeSceneGraph tolerates missing/empty fields, and
 * that FrameEditor's setup() does not throw on the same edge-case data.
 */

test('deserializeSceneGraph tolerates missing nodes/images/rootId', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(500)

  const result = await page.evaluate(async () => {
    const importer = new Function('m', 'return import(m)') as (s: string) => Promise<any>
    const mod = await importer('/@fs/Users/uengine/robo-architect/open-pencil/src/federation/bridge/serialize.ts')
    const cases = [
      { label: 'fully empty', data: {} },
      { label: 'missing images', data: { nodes: {}, rootId: 'root' } },
      { label: 'missing nodes', data: { rootId: 'root', images: {} } },
      { label: 'null nodes', data: { nodes: null, images: null, rootId: 'root' } },
      { label: 'undefined data', data: undefined },
    ]
    const results: Array<{ label: string; ok: boolean; err?: string }> = []
    for (const c of cases) {
      try {
        const g = mod.deserializeSceneGraph(c.data)
        results.push({ label: c.label, ok: !!g })
      } catch (e: any) {
        results.push({ label: c.label, ok: false, err: e?.message || String(e) })
      }
    }
    return results
  })

  console.log('=== deserialize edge cases ===')
  for (const r of result) console.log(`  ${r.label}: ${r.ok ? 'OK' : 'FAIL ' + r.err}`)
  for (const r of result) expect(r.ok, `${r.label}: ${r.err || ''}`).toBeTruthy()
})

test('FrameEditor setup() does not throw on a sceneGraph with no images field', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', err => pageErrors.push(err.message))

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1000)

  const result = await page.evaluate(async () => {
    const log: string[] = []
    try {
      const importer = new Function('m', 'return import(m)') as (s: string) => Promise<any>
      const Vue = await importer('/@fs/Users/uengine/robo-architect/frontend/node_modules/vue/dist/vue.runtime.esm-bundler.js')
      const FE = await importer('/@fs/Users/uengine/robo-architect/open-pencil/src/federation/FrameEditor.vue')

      // sceneData missing the `images` field — the exact shape that was crashing
      const sceneData = {
        rootId: 'root',
        nodes: {
          root: { id: 'root', type: 'DOCUMENT', parentId: null, childIds: ['page1'], x:0, y:0, width:0, height:0 },
          page1: { id: 'page1', type: 'CANVAS', parentId: 'root', childIds: ['frame1'], name: 'Page 1', x:0, y:0, width:0, height:0 },
          frame1: { id: 'frame1', type: 'FRAME', parentId: 'page1', childIds: [], name: 'Frame 1', x: 0, y: 0, width: 400, height: 300 },
        },
      }

      let setupError: string | null = null
      const host = document.createElement('div')
      host.style.cssText = 'width:600px;height:400px;position:fixed;top:0;left:0;visibility:hidden;'
      document.body.appendChild(host)
      const app = Vue.createApp(FE.default, { sceneData, frameId: 'frame1' })
      app.config.errorHandler = (err: any, _i: any, info: string) => {
        if (info === 'setup function') setupError = err?.message || String(err)
        log.push(`[errorHandler/${info}] ${err?.message || String(err)}`)
      }
      app.mount(host)
      await new Promise(r => setTimeout(r, 800))
      app.unmount()
      host.remove()

      return { setupError, log }
    } catch (e: any) {
      log.push(`THROWN: ${e?.message || String(e)}`)
      return { setupError: e?.message, log }
    }
  })

  console.log('=== setup test log ===')
  for (const l of result.log) console.log(l)
  for (const e of pageErrors) console.log('[pageerror]', e.slice(0, 400))

  // Setup must not throw. Render-phase errors from standalone mount (e.g. reka-ui
  // outside its expected provider context) are acceptable for this regression check.
  expect(result.setupError, 'setup() should not throw').toBeNull()
})
