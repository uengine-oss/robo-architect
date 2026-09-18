/**
 * 런타임 상태 — 지금 무엇이 준비됐고 무엇이 안 됐는가 (spec 058 T026 · US1).
 *
 * ## 왜 이 스토어가 생겼나
 *
 * 렌더러에는 런타임을 보는 구독이 **하나도 없었다.** `app:onBackendStatus` 는 메인이
 * 보내는데 `frontend/src` 에서 받는 곳이 0건이었다 — 화면은 백엔드가 죽은 것도,
 * 서비스 하나가 못 뜬 것도 모른다. 사용자는 기능을 눌러 보고 나서야 알게 된다.
 *
 * ## 이 스토어가 지키는 세 가지
 *
 * 1. **"떴다"를 "쓸 수 있다"로 읽지 않는다.** 판정은 메인이 하고(`supervisor.ts`),
 *    여기서는 그 결과를 그대로 들고 있는다. 화면이 다시 계산하면 두 곳에 같은 사실이
 *    생기고 어긋난다.
 * 2. **모르는 것과 안 되는 것을 가른다.** 아직 한 번도 못 받았으면 `loaded=false` 다 —
 *    빈 목록을 "서비스가 없다"로 보여주면 안 된다.
 * 3. **마지막 진전 시각을 남긴다.** 기동에 수 분이 걸리는 것은 정상이다(2GB tar 적재).
 *    "오래 걸리는 중"과 "멎었다"를 화면이 가르려면 이 값이 필요하다.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/** 이 값 이상 진전이 없으면 화면이 "멎었을 수 있다"고 말한다. 무한 대기 금지. */
export const STALL_WARNING_MS = 90_000

export const useRuntimeStore = defineStore('runtime', () => {
  /** 한 번이라도 받았는가. **빈 목록과 구분한다.** */
  const loaded = ref(false)
  /** 이 창이 Electron 안인가. 브라우저면 런타임 감독 대상이 아니다. */
  const supported = ref(false)
  const services = ref([])
  const capabilities = ref([])
  const graphGuard = ref(null)
  const dockerAvailable = ref(null)
  const releaseId = ref(null)
  /** 마지막으로 **무언가 바뀐** 시각. 같은 값을 다시 받은 것은 진전이 아니다. */
  const lastProgressAt = ref(null)
  const lastChangedServiceIds = ref([])

  let unsubscribe = null

  const byId = computed(() => {
    const map = {}
    for (const service of services.value) map[service.id] = service
    return map
  })

  const capabilityById = computed(() => {
    const map = {}
    for (const capability of capabilities.value) map[capability.id] = capability
    return map
  })

  /**
   * 기동 중인가. **`starting` 이 하나라도 있으면 그렇다.**
   *
   * `!ready` 로 판단하면 `degraded`(떴지만 일할 수 없음)까지 "기동 중"으로 보이고,
   * 화면이 영원히 기다리게 된다.
   */
  const starting = computed(() =>
    services.value.some((service) => service.state === 'starting' || service.state === 'pending'),
  )

  const broken = computed(() =>
    services.value.filter((service) => service.state === 'failed' || service.state === 'stopped'),
  )
  const degraded = computed(() => services.value.filter((service) => service.state === 'degraded'))

  /**
   * 기동이 멎은 것처럼 보이는가.
   *
   * **"오래 걸린다"와 "멎었다"는 다른 사실이다.** 시간만으로는 못 가리므로, 마지막
   * 진전 시각을 기준으로 삼는다. 이 값이 `true` 여도 실패로 단정하지 않는다 —
   * 화면은 "확인해 보세요" 라고 말하고 진단 경로를 준다.
   */
  function stalled(now = Date.now()) {
    if (!starting.value || lastProgressAt.value === null) return false
    return now - lastProgressAt.value > STALL_WARNING_MS
  }

  function apply(payload) {
    if (!payload) return
    // 바뀐 것이 있을 때만 진전으로 센다. 메인이 "바뀔 때만" 보내기로 했지만,
    // **보내는 쪽 약속을 받는 쪽이 믿고만 있으면** 약속이 깨진 날 조용히 틀린다.
    const changed = Array.isArray(payload.changedServiceIds) ? payload.changedServiceIds : []
    if (!loaded.value || changed.length > 0) lastProgressAt.value = Date.now()
    lastChangedServiceIds.value = changed
    if (Array.isArray(payload.services)) services.value = payload.services
    if (Array.isArray(payload.capabilities)) capabilities.value = payload.capabilities
    if ('graphGuard' in payload) graphGuard.value = payload.graphGuard ?? null
    if ('dockerAvailable' in payload) dockerAvailable.value = payload.dockerAvailable ?? null
    if ('releaseId' in payload) releaseId.value = payload.releaseId ?? null
    loaded.value = true
  }

  /**
   * 구독을 켠다. **두 번 불러도 구독이 둘이 되지 않는다** — 한 사실을 두 곳에서
   * 알리면 알림이 두 번 뜬다.
   */
  async function start() {
    const bridge = typeof window !== 'undefined' ? window.desktop : undefined
    supported.value = Boolean(bridge?.runtime)
    if (!supported.value) return

    // 먼저 현재 상태를 한 번 읽는다 — push 만 기다리면 아무 일도 안 바뀌는 동안
    // 화면이 비어 있다.
    try {
      const result = await bridge.app.getRuntimeState()
      const state = result?.ok ? result.data : result
      if (state) {
        apply({
          services: state.services ?? [],
          capabilities: state.capabilities ?? [],
          graphGuard: state.graphGuard ?? null,
          dockerAvailable: state.dockerAvailable ?? null,
          releaseId: state.releaseId ?? null,
          changedServiceIds: [],
        })
      }
    } catch {
      // 못 읽은 것은 "서비스가 없다"가 아니다. loaded 를 켜지 않고 넘어간다.
    }

    if (unsubscribe) return
    unsubscribe = bridge.runtime.onStatus(apply)
  }

  function stop() {
    if (unsubscribe) {
      unsubscribe()
      unsubscribe = null
    }
  }

  async function retryService(serviceId) {
    const bridge = window?.desktop?.runtime
    if (!bridge) return { ok: false, error: 'runtime bridge unavailable' }
    return bridge.retryService({ serviceId })
  }

  async function openDiagnostics(serviceId) {
    const bridge = window?.desktop?.runtime
    if (!bridge) return { ok: false, error: 'runtime bridge unavailable' }
    return bridge.openDiagnostics({ serviceId })
  }

  /**
   * 기능을 쓸 수 있는가 — 화면의 진입점이 이걸 보고 열고 닫는다.
   *
   * **모르면 열지 않는다.** 아직 못 받았거나 표에 없는 기능은 `false` 다.
   * 조용히 빈 화면을 주는 것보다 "아직 확인 중"이라고 말하는 쪽이 낫다.
   */
  function isAvailable(capabilityId) {
    if (!supported.value) return true // 브라우저 모드는 이 감독의 대상이 아니다
    if (!loaded.value) return false
    return capabilityById.value[capabilityId]?.state === 'available'
  }

  /** 못 쓰는 이유 + 사용자가 할 수 있는 일. 없으면 `null`. */
  function blockedReason(capabilityId) {
    if (!supported.value) return null
    if (!loaded.value) return '런타임 상태를 확인하고 있습니다.'
    return capabilityById.value[capabilityId]?.blockedReason ?? null
  }

  return {
    loaded,
    supported,
    services,
    capabilities,
    graphGuard,
    dockerAvailable,
    releaseId,
    lastProgressAt,
    lastChangedServiceIds,
    byId,
    capabilityById,
    starting,
    broken,
    degraded,
    stalled,
    apply,
    start,
    stop,
    retryService,
    openDiagnostics,
    isAvailable,
    blockedReason,
  }
})
