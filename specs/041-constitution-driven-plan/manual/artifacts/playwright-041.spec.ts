import { test, expect } from '@playwright/test'

/**
 * 041 Constitution-driven Plan — 사용자 매뉴얼용 화면 캡처.
 * 백엔드는 전부 모킹(라이브 claude CLI/Neo4j 불필요)하여 신규 UI 상태를 결정적으로 캡처한다.
 */

const SHOTS = '/Users/uengine/main-robo-arch/robo-architect/specs/041-constitution-driven-plan/manual/screenshots'
const APP = 'http://localhost:5173'

test.use({ viewport: { width: 1400, height: 900 } })

const CONSTITUTION_RAW = `# 주문 플랫폼 Constitution

## Core Principles
- 이벤트 드리븐, 느슨한 결합
- 테스트 우선

## Technology Constraints
- Backend: JDK 21 / Spring Boot 3
- Frontend: Vue 3 + Vite
- Datastore: PostgreSQL, Kafka

## Architecture
- Style: MICROSERVICES
- Repository Strategy: REPO_PER_SERVICE (split-git)
`

const PLAN = {
  version: 1,
  architectureDecisions: [
    { aspect: 'DEPLOYMENT_ENV', decision: 'Kubernetes (EKS)', rationale: '독립 확장/배포', constitutionRef: 'Technology Constraints' },
    { aspect: 'INGRESS', decision: 'nginx ingress', rationale: '단일 진입점', constitutionRef: 'Architecture' },
    { aspect: 'SERVICE_MESH_FRAMEWORK', decision: 'Spring Boot 3 + Spring Cloud', rationale: '팀 친숙도', constitutionRef: 'Technology Constraints' },
    { aspect: 'FRONTEND', decision: 'Vue 3 + Vite', rationale: '기존 스택', constitutionRef: 'Technology Constraints' },
    { aspect: 'REPO_MAPPING', decision: '서비스별 레포 (Ordering/Payment/Fulfillment)', rationale: 'repo-per-service', constitutionRef: 'Architecture' },
  ],
  constitutionGaps: ['SERVICE_MESH (관측성 도구 미정)'],
  interContextIntegrations: [
    { fromContext: 'Ordering', toContext: 'Payment', message: 'ChargePayment', kind: 'COMMAND', sync: true, rationale: '외부 PG 동기 호출' },
    { fromContext: 'Payment', toContext: 'Ordering', message: 'PaymentConfirmed', kind: 'EVENT', sync: false, rationale: '비동기 pub/sub' },
    { fromContext: 'Ordering', toContext: 'Fulfillment', message: 'OrderConfirmed', kind: 'EVENT', sync: false, rationale: '배송 트리거' },
  ],
  messagingChannel: 'Kafka',
  serviceDevEnvironments: [
    { service: 'Ordering', runtime: 'JDK 21 / Spring Boot 3', dockerBaseImage: 'eclipse-temurin:21-jre', dependencies: ['kafka', 'postgres'], composeServices: ['kafka', 'postgres'], scopeNote: 'Ordering 개발자는 kafka+postgres 만 로컬 구동' },
    { service: 'Payment', runtime: 'JDK 21 / Spring Boot 3', dockerBaseImage: 'eclipse-temurin:21-jre', dependencies: ['kafka'], composeServices: ['kafka'], scopeNote: 'Payment 개발자는 kafka 만 구동, 외부 PG 는 모킹' },
  ],
  tacticalSummary: '주문/결제/배송 3개 서비스로 분리, 결제 확인은 이벤트로 비동기 연동.',
}

const TACTICAL = [
  { nodeId: 'AGG-order', nodeLabel: 'Aggregate', nodeTitle: '주문(Order)', changeType: 'CREATE', impactLevel: 'HIGH' },
  { nodeId: 'CMD-charge', nodeLabel: 'Command', nodeTitle: '결제 청구(ChargePayment)', changeType: 'CREATE', impactLevel: 'MEDIUM' },
  { nodeId: 'EVT-confirmed', nodeLabel: 'Event', nodeTitle: '결제 확인(PaymentConfirmed)', changeType: 'CREATE', impactLevel: 'LOW' },
]

const STRATEGIC = {
  version: 2,
  epics: [{ op: 'CREATE', entityType: 'Epic', entityTitle: '주문 처리' }],
  features: [{ op: 'CREATE', entityType: 'Feature', entityTitle: '주문 생성/결제/배송' }],
  userStories: [
    { op: 'CREATE', entityType: 'UserStory', entityTitle: '고객이 주문을 생성한다' },
    { op: 'CREATE', entityType: 'UserStory', entityTitle: '결제가 승인되면 배송이 시작된다' },
  ],
  processes: [{ op: 'CREATE', entityType: 'Process', entityTitle: '주문→결제→배송' }],
}

const DETAIL = {
  id: 'PRO-DEMO', title: '주문/결제/배송 마이크로서비스', originalPrompt: '주문·결제·배송을 마이크로서비스로, nginx ingress 뒤에, Vue 프론트엔드로 만든다.',
  author: 'demo', createdAt: '2026-06-11T00:00:00Z', status: 'DRAFT', statusHistory: [],
  strategicDiff: STRATEGIC, tacticalDiff: TACTICAL,
  implementationPlan: PLAN, constitutionHash: 'newhash', planStale: true,
  impactMap: [{ nodeId: 'AGG-order', nodeLabel: 'Aggregate', nodeTitle: '주문(Order)', conflictLevel: 'LOW', reason: '신규 생성' }],
}

const QUESTIONS_SSE =
  'event: question\ndata: {"index":1,"question":"아키텍처 스타일은? (복잡성 게이트)","options":["MONOLITH","MICROSERVICES"],"recommended":"MICROSERVICES","rationale":"다수 컨텍스트·독립 배포 신호"}\n\n' +
  'event: question\ndata: {"index":2,"question":"기술 스택(백엔드/프론트엔드)?","options":["Spring Boot + Vue","FastAPI + React"],"seeded":true,"prefilled":"Spring Boot + Vue"}\n\n' +
  'event: question\ndata: {"index":3,"question":"레포 전략?","options":["MONOREPO","REPO_PER_SERVICE"],"recommended":"REPO_PER_SERVICE","rationale":"독립 릴리스 주기"}\n\n'

async function mock(page) {
  // 가장 일반적인 catch-all 을 먼저 등록(가장 나중에 등록된 것이 우선 매칭됨).
  await page.route('**/api/**', (route) => {
    const u = route.request().url()
    if (u.includes('/stream/')) {
      return route.fulfill({ status: 204, contentType: 'text/event-stream', body: '' })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })

  let cstStream = 0
  await page.route('**/api/proposals/PRO-DEMO/stream/constitution', (route) => {
    cstStream += 1
    if (cstStream === 1) return route.fulfill({ status: 200, contentType: 'text/event-stream', body: QUESTIONS_SSE })
    return route.fulfill({ status: 204, contentType: 'text/event-stream', body: '' }) // 재연결 금지
  })
  await page.route('**/api/proposals/PRO-DEMO/constitution/answer', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }))
  await page.route('**/api/proposals/PRO-DEMO/constitution', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json',
      body: JSON.stringify({ exists: true, raw: CONSTITUTION_RAW, fields: { architectureStyle: 'MICROSERVICES', repoStrategy: 'REPO_PER_SERVICE', repoMode: 'SPLIT_GIT' }, architectureStyle: 'MICROSERVICES', repoStrategy: 'REPO_PER_SERVICE', repoMode: 'SPLIT_GIT', constitutionHash: 'newhash' }) }))
  await page.route('**/api/proposals/PRO-DEMO/plan', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(PLAN) }))
  await page.route('**/api/proposals/PRO-DEMO', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(DETAIL) }))
  await page.route(/\/api\/proposals\/(\?.*)?$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([
      { id: 'PRO-DEMO', title: '주문/결제/배송 마이크로서비스', status: 'DRAFT', author: 'demo', createdAt: '2026-06-11T00:00:00Z', originalPrompt: '주문·결제·배송을 마이크로서비스로...' },
    ]) }))
}

async function gotoProposals(page) {
  await page.goto(APP)
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.waitForTimeout(800)
  const tab = page.getByText('Proposals', { exact: false }).first()
  await tab.click({ timeout: 8000 }).catch(() => {})
  await page.waitForTimeout(800)
}

async function openDetail(page) {
  const item = page.locator('.proposal-item').first()
  await item.click({ timeout: 8000 }).catch(() => {})
  await page.waitForTimeout(1000)
}

async function clickTab(page, label) {
  await page.locator('.proposal-detail-pane button', { hasText: label }).first()
    .click({ timeout: 6000 }).catch(async () => {
      await page.getByRole('button', { name: label }).first().click({ timeout: 6000 }).catch(() => {})
    })
  await page.waitForTimeout(900)
}

test('01 — Proposals 목록', async ({ page }) => {
  await mock(page)
  await gotoProposals(page)
  await page.screenshot({ path: `${SHOTS}/01_proposals_list.png` })
})

test('02 — Intent (전략 only)', async ({ page }) => {
  await mock(page)
  await gotoProposals(page)
  await openDetail(page)
  await clickTab(page, 'Intent')
  const pane = page.locator('.proposal-detail-pane')
  await (await pane.count() ? pane.first() : page).screenshot({ path: `${SHOTS}/02_intent_strategic.png` })
})

test('03 — Constitution 보기(저장된 헌장)', async ({ page }) => {
  await mock(page)
  await gotoProposals(page)
  await openDetail(page)
  await clickTab(page, 'Constitution')
  await page.waitForTimeout(600)
  const v = page.locator('.constitution-view')
  await (await v.count() ? v.first() : page).screenshot({ path: `${SHOTS}/03_constitution_view.png` })
})

test('04 — Constitution 인터뷰(시드/추천/최소질문)', async ({ page }) => {
  await mock(page)
  await gotoProposals(page)
  await openDetail(page)
  await clickTab(page, 'Constitution')
  // 보기 모드 → 인터뷰 모드로 전환 후 시작
  await page.getByRole('button', { name: '인터뷰로 돌아가기' }).first().click({ timeout: 4000 }).catch(() => {})
  await page.getByRole('button', { name: '인터뷰 시작' }).first().click({ timeout: 4000 }).catch(() => {})
  await page.waitForTimeout(1500)
  const v = page.locator('.constitution-view')
  await (await v.count() ? v.first() : page).screenshot({ path: `${SHOTS}/04_constitution_interview.png` })
})

test('05 — Plan (아키텍처·연동·개발환경)', async ({ page }) => {
  await mock(page)
  await gotoProposals(page)
  await openDetail(page)
  await clickTab(page, 'Plan')
  await page.locator('.dev-card').first().waitFor({ timeout: 8000 }).catch(() => {})
  await page.locator('.integ-card').nth(2).waitFor({ timeout: 4000 }).catch(() => {})
  await page.waitForTimeout(600)
  // 스크롤 컨테이너의 클리핑을 풀어 전체 plan 내용을 한 장에 담는다.
  await page.evaluate(() => {
    document.querySelectorAll('*').forEach((el) => {
      const s = getComputedStyle(el)
      if (['auto', 'scroll'].includes(s.overflowY) || ['auto', 'scroll'].includes(s.overflow)) {
        el.style.overflow = 'visible'
        el.style.height = 'auto'
        el.style.maxHeight = 'none'
      }
    })
  })
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${SHOTS}/05_plan_architecture.png`, fullPage: true, animations: 'disabled' })
})

test('06 — 제출 게이트(Plan stale 배너)', async ({ page }) => {
  await mock(page)
  await gotoProposals(page)
  await openDetail(page)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.waitForTimeout(500)
  const pane = page.locator('.proposal-detail-pane')
  await (await pane.count() ? pane.first() : page).screenshot({ path: `${SHOTS}/06_submit_gate_stale.png` })
})
