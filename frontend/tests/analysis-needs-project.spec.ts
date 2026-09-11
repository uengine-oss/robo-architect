import { test, expect } from '@playwright/test'

/**
 * 프로젝트 없이 분석을 돌리면 어떻게 되나.
 *
 * **설계와 분석은 막히는 방식이 다르다.** 설계는 우리 백엔드를 지나므로 프로젝트가
 * 없으면 403 으로 막힌다. 분석은 별도 서비스(5001·5502)라 그 403 이 걸리지 않는다.
 *
 *   대상 graph 를 안 넘긴다  →  analyzer 가 자기 `.env` 의 공용 graph 를 쓴다
 *   분석은 시작할 때          →  **그 graph 를 통째로 비운다**
 *
 * 그래서 프로젝트 없이 한 번 돌리면 공용 graph 에 쌓이고, 그 graph 를 짝으로 쓰는
 * 프로젝트가 있으면 그 결과가 사라진다. **오류는 안 난다.**
 *
 * 재는 것은 화면 문구가 아니라 **remote 를 띄웠는가** 다. 안내만 띄우고 뒤에서
 * 마운트하면 분석기는 그대로 돌아간다.
 */

test.use({ storageState: { cookies: [], origins: [] } })

const PROVIDER = {
  provider: 'swp', enterprise: true, callbackAllowlist: [], embeddings: {},
  devLogin: { enabled: false }, approvalRequired: true, jwtSecretConfigured: true,
  sessionTtlSeconds: 28800, enforce: false, bindConnection: true,
}

const ME = {
  authenticated: true, status: 'approved',
  user: { uid: 'DEV-TEST', displayName: '개발용 계정', role: 'admin', status: 'approved' },
}

const PAIRED = {
  graph: 'prj_aaa', displayName: '인사관리 설계', ownerUid: 'DEV-TEST',
  level: 'admin', analyzerGraph: 'prj_aaa_a',
}
const UNPAIRED = { ...PAIRED, analyzerGraph: null }

/**
 * analyzer remote 를 실제로 가져갔는지 센다. 5001 이 안 떠 있어도 재려는 것은
 * "요청했는가" 이므로 결과가 흔들리지 않는다.
 */
async function openAnalysis(page: any, projects: any[]) {
  let remoteFetches = 0
  await page.route('**/remoteEntry.js', (r: any) => { remoteFetches += 1; return r.continue() })
  await page.route('**/assets/__federation_expose_Remote-app*', (r: any) => {
    remoteFetches += 1
    return r.continue()
  })

  await page.addInitScript(() => {
    window.localStorage.setItem('robo.auth.token', 'stub-token')
  })
  await page.route('**/api/auth/provider', (r: any) => r.fulfill({ json: PROVIDER }))
  await page.route('**/api/auth/me', (r: any) => r.fulfill({ json: ME }))
  await page.route('**/api/projects', (r: any) => {
    if (r.request().method() !== 'GET') return r.fallback()
    return r.fulfill({ json: { projects } })
  })

  await page.goto('/', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Legacy' }).click()
  return () => remoteFetches
}

test('프로젝트가 없으면 분석기를 띄우지 않는다', async ({ page }) => {
  const fetched = await openAnalysis(page, [])

  await expect(page.locator('.analysis-error')).toContainText('먼저 프로젝트를 선택')
  // **여기가 본체다.** 안내를 띄우면서 뒤로 마운트하면 공용 graph 가 지워진다.
  await expect.poll(fetched, { timeout: 5000 }).toBe(0)
})

test('분석 짝이 없으면 그렇게 말한다', async ({ page }) => {
  const fetched = await openAnalysis(page, [UNPAIRED])

  // 프로젝트는 골랐다 — 할 일이 다르므로 문구도 달라야 한다.
  await expect(page.locator('.analysis-error')).toContainText('담을 곳이 지정되어 있지 않')
  await expect(page.locator('.analysis-error')).toContainText('분석 결과 바꾸기')
  await expect.poll(fetched, { timeout: 5000 }).toBe(0)
})

test('브라우저에서는 경로 모드 인자를 넘기지 않는다', async () => {
  // `projectRoot` 를 넘기면 분석기가 "로컬 폴더 분석"으로 열리고, 없으면
  // "파일을 올려 분석"으로 열린다. 그 값의 출처가 **이 브라우저의
  // localStorage** 라, 같은 서버에 붙어도 창마다 화면이 달랐다 — 한쪽은
  // 폴더를 고르라 하고 다른 쪽은 드래그하라 했다.
  //
  // 그리고 서버에 올린 Architect 에서 "로컬 폴더"는 사용자 PC 가 아니라
  // **서버의 폴더**다. 경로 모드는 런처(Electron)에서만 말이 된다.
  //
  // **화면으로 재려 했으나 못 했다.** 지금 서비스되는 분석기 번들에는 경로
  // 모드를 가려낼 표시가 없어, 막은 판과 안 막은 판의 DOM 이 같았다 —
  // 그대로 두면 늘 통과하는 빈 검사가 된다. 그래서 배선을 직접 본다:
  // `readRoot` 가 유일한 통로이고, 그 앞에 데스크톱 관문이 있어야 한다.
  const fs = await import('node:fs')
  const src = fs.readFileSync(
    new URL('../src/features/analysis/ui/AnalysisPanel.vue', import.meta.url), 'utf8')

  const body = src.slice(src.indexOf('function readRoot()'))
  const guard = body.indexOf('if (!session.isDesktop) return undefined')
  const reads = body.indexOf('localStorage.getItem(ROOT_KEY)')
  expect(guard, '데스크톱 관문이 있어야 한다').toBeGreaterThan(-1)
  expect(reads, 'localStorage 를 읽는 자리가 있어야 한다').toBeGreaterThan(-1)
  expect(guard, '관문이 읽기보다 앞이어야 한다 — 뒤면 소용이 없다')
    .toBeLessThan(reads)
  // mount 가 이 함수만 쓰는지도 본다. 다른 경로로 또 읽으면 관문을 비껴간다.
  expect(src.match(/localStorage\.getItem\(ROOT_KEY\)/g) || []).toHaveLength(1)
})

test('짝이 있으면 띄운다', async ({ page }) => {
  // "안 띄운다"만 재면 **늘 안 띄우는 것도 통과**한다. 반대쪽을 같이 재야 한다.
  const fetched = await openAnalysis(page, [PAIRED])

  await expect(page.locator('.analysis-error')).toHaveCount(0)
  await expect.poll(fetched, { timeout: 15000 }).toBeGreaterThan(0)
})
