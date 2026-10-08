// 실행 상태 화면이 **모든 경우에** 이름·기능·할 일을 말하는가 (spec 058 T031 · SC-002).
// 실행: npx playwright test -c playwright.unit.config.ts tests/runtime-status.spec.ts
//
// ## 왜 이렇게 재는가
//
// T031 은 "서비스를 하나씩 죽여 **모든 경우에** 이름·기능·복구 방법이 나오는지
// (누락 0건)" 다. 그걸 앱을 띄워 재려면 서비스 10개 × 상태 다섯을 **50번** 죽여야
// 하고, 한 바퀴가 수십 분이다. 그리고 그렇게 재도 **다음에 서비스가 하나 늘면
// 사람이 다시 세야 한다.**
//
// 그래서 판정을 `src/features/runtime-status/messages.js` 로 빼고(화면은 그것을 그대로
// 그린다) 여기서 **모든 조합을 돌린다**. 서비스나 상태가 늘면 이 검사가 자동으로
// 그만큼 돈다 — "모든 경우에" 를 사람이 세지 않는다.
//
// 서버 쪽 쓸기(실제로 죽여 보는 것)는 `scripts/verify_runtime_service_sweep.py` 가
// 따로 한다. 둘은 **다른 질문**이다 — 저쪽은 "감독이 잡는가", 이쪽은 "화면이 말하는가".
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import {
  missingTells,
  rowActions,
  screenTells,
  serviceLabel,
  sortedServices,
  stateText,
  headOf,
} from '../src/features/runtime-status/messages.js'

/** 감독이 다루는 서비스 열. `runtime-state.DISPLAY_NAMES` 와 같은 집합이다. */
const SERVICES = [
  { id: 'graph', displayName: '설계·분석 저장소' },
  { id: 'architect', displayName: '백엔드' },
  { id: 'analyzer', displayName: '코드 분석기' },
  { id: 'catalog', displayName: '데이터 카탈로그' },
  { id: 'fabric', displayName: '데이터 패브릭' },
  { id: 'gateway', displayName: 'API 게이트웨이' },
  { id: 'parser', displayName: '구문 분석기' },
  { id: 'pdf2bpmn', displayName: '문서→BPMN 생성기' },
  { id: 'mindsdb', displayName: '예측 엔진' },
  { id: 'wireframe', displayName: '와이어프레임' },
]

/** 감독이 낼 수 있는 상태 전부. `ManagedService["state"]` 와 같아야 한다. */
const STATES = ['ready', 'starting', 'degraded', 'failed', 'stopped', 'pending']

const CAPABILITIES = [
  { id: 'design', displayName: '설계', requires: ['graph', 'architect'] },
  { id: 'document-ingestion', displayName: '문서·리소스 업로드', requires: ['graph', 'architect'] },
  { id: 'bpmn-generation', displayName: '업무 흐름 BPMN 생성', requires: ['graph', 'architect', 'pdf2bpmn'] },
  { id: 'legacy-analysis', displayName: '레거시 코드 탐색', requires: ['graph', 'analyzer', 'catalog', 'parser', 'gateway'] },
  { id: 'code-generation', displayName: '코드 생성', requires: ['graph', 'architect'] },
  { id: 'collaboration', displayName: '동시 편집', requires: ['graph', 'architect'] },
]

/** 한 서비스만 그 상태로 두고 나머지는 멀쩡한 세계를 만든다. */
function worldWith(serviceId: string, state: string, extra: Record<string, unknown> = {}) {
  const services = SERVICES.map((s) => ({
    ...s,
    state: s.id === serviceId ? state : 'ready',
    stateReason: s.id === serviceId && state !== 'ready' ? `${s.displayName} 가 ${state} 다` : null,
    owner: s.id === 'graph' ? 'external' : 'app',
  }))
  const down = new Set(services.filter((s) => s.state !== 'ready').map((s) => s.id))
  const capabilities = CAPABILITIES.map((c) => {
    const bad = c.requires.filter((r) => down.has(r))
    return {
      id: c.id,
      displayName: c.displayName,
      state: bad.length === 0 ? 'available' : 'unavailable',
      blockedReason: bad.length ? `${bad.join(' · ')} 가 준비되지 않았습니다.` : null,
    }
  })
  return { services, capabilities, dockerAvailable: true, graphGuard: null, ...extra }
}

// ---------------------------------------------------------------------------
// 모든 서비스 × 모든 상태 — **누락 0건**
// ---------------------------------------------------------------------------

test.describe('모든 경우에 이름·기능·할 일이 나온다 (SC-002)', () => {
  for (const service of SERVICES) {
    for (const state of STATES) {
      test(`${service.id} · ${state}`, () => {
        const told = screenTells(worldWith(service.id, state))

        // 빠진 것이 **하나도** 없어야 한다. 이 한 줄이 SC-002 다.
        expect(missingTells(worldWith(service.id, state)), `${service.id}/${state} 에서 빠진 것`).toEqual([])

        if (state === 'ready') {
          // **멀쩡하면 아무것도 안 띄운다** — 늘 떠 있는 띠는 며칠이면 안 보이게 된다.
          expect(told.noticed).toBe(false)
          return
        }
        if (state === 'starting' || state === 'pending') {
          // 아직 **모르는 것**이라 문제로 올리지 않는다(기동 중 화면을 고장으로 덮지 않는다).
          expect(told.noticed).toBe(false)
          return
        }

        // 여기부터는 문제다 — 셋이 다 있어야 한다.
        expect(told.noticed).toBe(true)
        expect(told.names, '이름이 없다').toContain(service.displayName)
        expect(told.headline, '한 줄 설명이 없다').toBeTruthy()
        expect(told.actions.length, '할 일이 없다').toBeGreaterThan(0)
      })
    }
  }
})

test('고장 난 서비스가 막는 기능을 **이름으로** 말한다', () => {
  const told = screenTells(worldWith('analyzer', 'failed'))
  expect(told.blocked).toContain('레거시 코드 탐색')
  // 나머지 기능은 멀쩡하다고 해야 한다 — 하나 죽었다고 전부 막힌 것처럼 보이면
  // 사용자는 쓸 수 있는 것까지 포기한다.
  expect(told.blocked).not.toContain('설계')
})

test('`degraded` 는 **경고**, 죽은 것은 **빨강** — 같은 색이면 급한 것을 못 가린다', () => {
  expect(screenTells(worldWith('pdf2bpmn', 'degraded')).tone).toBe('warn')
  expect(screenTells(worldWith('pdf2bpmn', 'failed')).tone).toBe('bad')
})

// ---------------------------------------------------------------------------
// 도커가 없을 때 — **원인이 하나인데 열 개가 실패로 보인다** (T030)
// ---------------------------------------------------------------------------

test('도커가 꺼졌으면 **그것부터** 말한다', () => {
  const world = {
    ...worldWith('analyzer', 'failed'),
    dockerAvailable: false,
  }
  const told = screenTells(world)
  expect(told.cause).toBe('docker')
  expect(told.headline).toContain('Docker Desktop')
  // **할 일**이 있어야 한다. "꺼져 있습니다" 만으로는 사용자가 할 수 있는 것이 없다.
  expect(told.actions).toContain('docker-start')
  expect(missingTells(world)).toEqual([])
})

test('도커를 **아직 못 쟀으면**(null) 안내를 띄우지 않는다', () => {
  // 모르는 것을 "도커가 없다" 로 바꿔 말하면 멀쩡한 PC 에 그 안내가 뜬다.
  const told = screenTells({ ...worldWith('analyzer', 'ready'), dockerAvailable: null })
  expect(told.noticed).toBe(false)
})

// ---------------------------------------------------------------------------
// 그래프 가드 — 서비스는 전부 멀쩡한데 기능이 잠긴 경우
// ---------------------------------------------------------------------------

test('설계·분석 저장소가 같으면 **서비스가 다 멀쩡해도** 말한다', () => {
  const world = {
    ...worldWith('analyzer', 'ready'),
    graphGuard: { designGraph: 'robo', analysisGraph: 'robo', separated: false, evidence: 'names', reason: null },
  }
  const told = screenTells(world)
  expect(told.noticed).toBe(true)
  expect(told.cause).toBe('graph-guard')
  expect(told.headline).toContain('레거시 코드 탐색')
  expect(missingTells(world)).toEqual([])
})

// ---------------------------------------------------------------------------
// 행의 모양 — 막다른 행을 만들지 않는다
// ---------------------------------------------------------------------------

test('로그는 **어느 상태에서도** 읽을 수 있다', () => {
  for (const state of STATES) {
    expect(rowActions({ state }), state).toContain('logs')
    expect(rowActions({ state }), state).toContain('folder')
  }
})

test('손댈 수 있는 상태에만 **다시 시도**가 붙는다', () => {
  for (const state of ['failed', 'stopped', 'degraded']) {
    expect(rowActions({ state }), state).toContain('retry')
  }
  for (const state of ['ready', 'starting', 'pending']) {
    expect(rowActions({ state }), state).not.toContain('retry')
  }
})

test('모르는 상태도 **그대로 보여준다** — 삼키면 디버깅이 막힌다', () => {
  expect(stateText('ready')).toBe('준비됨')
  expect(stateText('무슨상태')).toBe('무슨상태')
})

test('이름이 없으면 id 로, 둘 다 없으면 **빈 칸을 주지 않는다**', () => {
  expect(serviceLabel({ id: 'parser' })).toBe('parser')
  expect(serviceLabel({})).toBe('(이름 없음)')
})

test('문제 있는 것이 **먼저** 온다', () => {
  const services = [
    { id: 'a', state: 'ready' },
    { id: 'b', state: 'failed' },
    { id: 'c', state: 'starting' },
    { id: 'd', state: 'degraded' },
  ]
  expect(sortedServices(services).map((s) => s.id)).toEqual(['b', 'd', 'c', 'a'])
})

test('조사를 **받침으로** 고른다 — `을(를)` 로 때우지 않는다', () => {
  // 받침 있는 이름 / 없는 이름 둘 다 자연스러워야 한다.
  const withBatchim = screenTells(worldWith('analyzer', 'failed')).headline // "코드 분석기" → 받침 없음
  expect(withBatchim).not.toContain('을(를)')
  expect(withBatchim).not.toContain('이(가)')
})

// ---------------------------------------------------------------------------
// 긴 덩이는 **머리만** (2026-10-08 — 스택을 붙이자 한 줄이 40줄이 됐다)
// ---------------------------------------------------------------------------

test('짧은 줄은 **그대로** 둔다', () => {
  expect(headOf('한 줄')).toBe('한 줄')
  expect(headOf('a\nb\nc')).toBe('a\nb\nc')
})

test('긴 덩이는 머리 3줄 + **몇 줄이 더 있는지** 말한다', () => {
  const row = ['NoResourceFoundException: No static resource', '\tat A', '\tat B', '\tat C', '\tat D'].join('\n')
  const head = headOf(row)
  const lines = head.split('\n')
  expect(lines).toHaveLength(4) // 머리 3줄 + 안내 한 줄
  // **원인은 첫 줄에 있다** — 그것이 안 잘려야 한다.
  expect(lines[0]).toContain('NoResourceFoundException')
  expect(lines[3]).toContain('2줄 더')
  expect(lines[3]).toContain('전문에서')
})
