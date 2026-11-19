/**
 * 남의 변경은 짧게 모았다가 한 번 다시 읽는다(포스코 다중 사용자 측정 2026-11-19).
 * 실제 모듈을 vite 로 띄워 브라우저에서 부른다.
 */
import { expect, test } from '@playwright/test'
import { createServer, type ViteDevServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
let server: ViteDevServer
let base = ''

test.describe.configure({ mode: 'serial', timeout: 60_000 })

test.beforeAll(async () => {
  server = await createServer({
    root: ROOT, configFile: false, plugins: [vue()],
    resolve: { alias: { '@': path.join(ROOT, 'src') } },
    server: { port: 0, strictPort: false, hmr: false }, logLevel: 'error',
  })
  await server.listen()
  const addr = server.httpServer?.address()
  base = `http://localhost:${typeof addr === 'object' && addr ? addr.port : 0}`
})
test.afterAll(async () => { await server?.close() })

async function load(page) {
  await page.goto(`${base}/tests/harness/proposals.html`).catch(() => {})
  await page.evaluate(async () => {
    const m = await import('/src/app/lifecycle/dataLifecycle.js')
    ;(window as any).__dl = m
    ;(window as any).__got = []
    window.addEventListener('robo:data-changed', (e: any) => (window as any).__got.push([e.detail.reason, performance.now()]))
  })
}

test('남의 변경 여러 번은 한 번으로 묶여 잠시 뒤 간다', async ({ page }) => {
  await load(page)
  const t0 = await page.evaluate(() => {
    const dl = (window as any).__dl
    const t = performance.now()
    dl.emitDataChanged('remote-change')
    dl.emitDataChanged('remote-change-catchup')
    dl.emitDataChanged('remote-change')
    return t
  })
  expect(await page.evaluate(() => (window as any).__got.length)).toBe(0)  // 즉시 가지 않는다
  await expect.poll(() => page.evaluate(() => (window as any).__got.length), { timeout: 3000 }).toBe(1)
  const [[reason, at]] = await page.evaluate(() => (window as any).__got)
  expect(reason).toBe('remote-change')
  expect(at - t0).toBeGreaterThanOrEqual(250)
  expect(at - t0).toBeLessThan(1500)
})

test('내 변경은 바로 간다', async ({ page }) => {
  await load(page)
  await page.evaluate(() => (window as any).__dl.emitDataChanged('ingestion-complete'))
  expect(await page.evaluate(() => (window as any).__got.map((g: any) => g[0]))).toEqual(['ingestion-complete'])
})

test('편집 중이면 미뤘다가 손을 떼면 보낸다', async ({ page }) => {
  await load(page)
  await page.evaluate(() => {
    const dl = (window as any).__dl
    ;(window as any).__release = dl.holdDataRefresh()
    dl.emitDataChanged('remote-change')
  })
  await page.waitForTimeout(1200)
  expect(await page.evaluate(() => (window as any).__got.length)).toBe(0)
  await page.evaluate(() => (window as any).__release())
  await expect.poll(() => page.evaluate(() => (window as any).__got.map((g: any) => g[0]))).toEqual(['remote-change'])
})
