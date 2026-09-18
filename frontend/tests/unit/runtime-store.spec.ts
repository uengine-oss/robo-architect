/**
 * 런타임 상태 스토어 (spec 058 T026 · US1).
 *
 * ## 여기서 재는 것
 *
 * 화면이 **모르는 것을 안다고 하지 않는가.** 이 저장소에서 제일 흔한 고장은 "0건"과
 * "못 읽었다"를 같은 화면으로 보여주는 것이다.
 */

import { expect, test } from '@playwright/test'
import { createPinia, setActivePinia } from 'pinia'

import { STALL_WARNING_MS, useRuntimeStore } from '../../src/features/runtime-status/runtime.store'

const service = (id: string, state: string, stateReason: string | null = null) => ({
  id,
  owner: 'app',
  displayName: id,
  state,
  stateReason,
  probeKind: null,
  lastProbeAt: null,
  lastProbeMs: null,
  restartCount: 0,
  restartGaveUpAt: null,
  version: null,
  endpoint: null,
})

const capability = (id: string, state: string, blockedReason: string | null = null) => ({
  id,
  displayName: id,
  requires: [],
  state,
  blockedReason,
})

test.beforeEach(() => {
  setActivePinia(createPinia())
})

test.describe('모르는 것과 안 되는 것을 가른다', () => {
  test('한 번도 못 받았으면 loaded 가 false — 빈 목록이 아니다', () => {
    const store = useRuntimeStore()
    expect(store.loaded).toBe(false)
    expect(store.services).toEqual([])
  })

  test('Electron 안이 아니면 감독 대상이 아니다 — 기능을 막지 않는다', () => {
    const store = useRuntimeStore()
    // supported=false 인 초기 상태. 브라우저 모드에서 모든 탭을 잠그면 아무것도 못 한다.
    expect(store.isAvailable('design')).toBe(true)
    expect(store.blockedReason('design')).toBeNull()
  })

  test('Electron 인데 아직 못 받았으면 **열지 않는다**', () => {
    const store = useRuntimeStore()
    store.supported = true
    expect(store.loaded).toBe(false)
    expect(store.isAvailable('design')).toBe(false)
    // 조용히 빈 화면을 주지 않는다 — 이유를 말한다.
    expect(store.blockedReason('design')).toContain('확인')
  })

  test('목록이 남아 있어도 loaded 가 false 면 열지 않는다', () => {
    // **이 갈래가 `loaded` 관문의 존재 이유다.** 목록이 비어 있으면 `?.state` 가
    // undefined 라서 관문 없이도 false 가 나온다 — 그래서 빈 목록으로는 관문을 못 잰다.
    // 실제로 처음 쓴 검사가 그 모양이었고, 관문을 지워도 통과했다.
    const store = useRuntimeStore()
    store.supported = true
    store.capabilities = [capability('design', 'available')]
    expect(store.loaded).toBe(false)
    expect(store.isAvailable('design')).toBe(false)
    expect(store.blockedReason('design')).toContain('확인')
  })
})

test.describe('상태를 그대로 들고 있는다', () => {
  test('받은 판정을 다시 계산하지 않는다', () => {
    const store = useRuntimeStore()
    store.supported = true
    store.apply({
      services: [service('graph', 'ready'), service('pdf2bpmn', 'degraded', 'LLM 자격증명 401')],
      capabilities: [
        capability('design', 'available'),
        capability('bpmn-generation', 'degraded', '자격증명을 확인하세요.'),
      ],
      changedServiceIds: ['pdf2bpmn'],
    })
    expect(store.isAvailable('design')).toBe(true)
    // degraded 는 available 이 아니다 — "떴다"를 "쓸 수 있다"로 읽지 않는다.
    expect(store.isAvailable('bpmn-generation')).toBe(false)
    expect(store.blockedReason('bpmn-generation')).toContain('자격증명')
    expect(store.degraded.map((s) => s.id)).toEqual(['pdf2bpmn'])
  })

  test('표에 없는 기능은 열지 않는다', () => {
    const store = useRuntimeStore()
    store.supported = true
    store.apply({ services: [], capabilities: [capability('design', 'available')], changedServiceIds: [] })
    expect(store.isAvailable('code-generation')).toBe(false)
  })
})

test.describe('기동 중과 멎은 것을 가른다', () => {
  test('starting 이 하나라도 있으면 기동 중 — degraded 를 기동 중으로 읽지 않는다', () => {
    const store = useRuntimeStore()
    store.apply({ services: [service('graph', 'degraded'), service('analyzer', 'ready')], changedServiceIds: [] })
    expect(store.starting).toBe(false)
    store.apply({ services: [service('graph', 'starting')], changedServiceIds: ['graph'] })
    expect(store.starting).toBe(true)
  })

  test('진전이 있으면 멎은 것이 아니다', () => {
    const store = useRuntimeStore()
    store.apply({ services: [service('graph', 'starting')], changedServiceIds: ['graph'] })
    const now = store.lastProgressAt! + STALL_WARNING_MS - 1
    expect(store.stalled(now)).toBe(false)
  })

  test('한계를 넘어 아무 것도 안 바뀌면 멎었을 수 있다고 본다 — 무한 대기 금지', () => {
    const store = useRuntimeStore()
    store.apply({ services: [service('graph', 'starting')], changedServiceIds: ['graph'] })
    const now = store.lastProgressAt! + STALL_WARNING_MS + 1
    expect(store.stalled(now)).toBe(true)
  })

  test('같은 값을 다시 받은 것은 **진전이 아니다**', () => {
    const store = useRuntimeStore()
    store.apply({ services: [service('graph', 'starting')], changedServiceIds: ['graph'] })
    const first = store.lastProgressAt!
    // 바뀐 것 없이 다시 밀렸다 — 진전 시각이 갱신되면 영원히 "멎지 않은" 상태가 된다.
    store.apply({ services: [service('graph', 'starting')], changedServiceIds: [] })
    expect(store.lastProgressAt).toBe(first)
    expect(store.stalled(first + STALL_WARNING_MS + 1)).toBe(true)
  })

  test('기동 중이 아니면 멎었다고 하지 않는다', () => {
    const store = useRuntimeStore()
    store.apply({ services: [service('graph', 'ready')], changedServiceIds: ['graph'] })
    expect(store.stalled(store.lastProgressAt! + STALL_WARNING_MS * 10)).toBe(false)
  })
})

test.describe('바뀐 것만 들고 있는다', () => {
  test('changedServiceIds 를 그대로 남긴다 — 화면이 알림을 한 번만 띄운다', () => {
    const store = useRuntimeStore()
    store.apply({ services: [service('analyzer', 'failed')], changedServiceIds: ['analyzer'] })
    expect(store.lastChangedServiceIds).toEqual(['analyzer'])
  })

  test('failed 와 stopped 를 둘 다 고장으로 센다', () => {
    const store = useRuntimeStore()
    store.apply({
      services: [service('a', 'failed'), service('b', 'stopped'), service('c', 'ready')],
      changedServiceIds: [],
    })
    expect(store.broken.map((s) => s.id).sort()).toEqual(['a', 'b'])
  })
})
