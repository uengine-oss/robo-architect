'use strict'
// 홈이 **ready 이후의 서비스 상태**를 읽는 법 (라이트 지적 A-3 ①).
//
// ## 왜 따로 있나
//
// 감독(main/supervision.ts)은 ready 뒤에도 5초마다 서비스를 재고, 바뀌면
// `runtime:onStatus` 로 민다. 탭 안 SPA 는 그걸 받아 RuntimeStatusBanner 를 띄운다.
// 그런데 **홈(이 셸)은 `app:onBackendStatus` 만 들었다** — 그 채널은 기동 경로에서만
// 값이 바뀐다. 그래서 컨테이너가 ready 뒤에 내려가도 홈은 "Ontological 연결됨" 초록 점을
// 계속 보였다. 거꾸로, 홈이 다시 읽은 `getRuntimeState().status` 는 감독이 파생한
// 값이라 컨테이너 하나만 빠져도 `starting-db` 가 되고, 홈은 멀쩡한 백엔드를 두고
// "그래프 DB 와 서비스를 올리는 중…" 으로 **기동 화면으로 돌아갔다.**
//
// 판정은 main 이 이미 했다(`ManagedService.state`). 여기서는 **다시 계산하지 않고**
// 그 값을 홈이 그릴 말로만 옮긴다 — 순수 함수라 검사(desktop/tests/unit)가 직접 부른다.
;(function (root, factory) {
  const api = factory()
  if (typeof module === 'object' && module.exports) module.exports = api
  else root.RaRuntimeView = api
})(typeof self !== 'undefined' ? self : this, function () {
  /** 문제로 볼 상태. `starting`·`pending` 은 아직 모르는 것이라 문제가 아니다(SPA messages.js 와 같다). */
  const BROKEN = new Set(['failed', 'stopped'])
  const UP = new Set(['ready', 'degraded'])
  const label = (s) => (s && (s.displayName || s.id)) || '(이름 없음)'

  /**
   * 홈이 "준비됐다" 로 볼 것인가.
   *
   * 한 번 ready 를 본 뒤에는 **백엔드(architect)가 살아 있는 한** 준비된 것으로 둔다 —
   * 컨테이너 하나가 빠진 것은 기동이 아니라 고장이고, 그건 `summarize` 가 따로 말한다.
   * 백엔드가 죽으면(파생 status `fatal`, 또는 backend-crashed) 그때는 준비가 아니다.
   */
  function homeReady(status, services, everReady) {
    if (status === 'ready') return true
    if (!everReady) return false
    if (status === 'fatal' || status === 'backend-crashed') return false
    const architect = (services || []).find((s) => s.id === 'architect')
    return !!architect && UP.has(architect.state)
  }

  /**
   * 서비스 목록 → 홈이 그릴 한 줄. 멀쩡하면 `null`(아무것도 안 띄운다).
   *
   * `graphDown` 은 Ontological 행이 따로 쓴다 — 홈의 첫 줄이 "그래프 DB" 이기 때문이다.
   */
  function summarize(services) {
    const list = Array.isArray(services) ? services : []
    const broken = list.filter((s) => BROKEN.has(s.state))
    const degraded = list.filter((s) => s.state === 'degraded')
    const graph = list.find((s) => s.id === 'graph')
    const graphDown = !!graph && BROKEN.has(graph.state)
    if (broken.length === 0 && degraded.length === 0) return { tone: 'ok', graphDown, names: [], reason: '', headline: '' }
    const stuck = [...broken, ...degraded]
    const names = stuck.map(label)
    const reason = (stuck.find((s) => s.stateReason) || {}).stateReason || ''
    const tone = broken.length > 0 ? 'bad' : 'warn'
    const headline = broken.length > 0
      ? `${names.join(' · ')} 멈춤 — 앱이 다시 살리는 중입니다. 돌아오면 이 표시는 사라집니다.`
      : `${names.join(' · ')} 응답은 하지만 일을 못 합니다 — 쓰는 기능에 따라 영향이 없을 수도 있습니다.`
    return { tone, graphDown, names, reason, headline }
  }

  return { homeReady, summarize }
})
