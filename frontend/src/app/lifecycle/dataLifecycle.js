/**
 * Data-lifecycle bus.
 *
 * A single window CustomEvent (`robo:data-changed`) signals that the graph
 * data underneath every tab has changed — fired when an ingestion completes
 * or when data is cleared. Each tab's navigator/canvas subscribes via
 * `useDataRefresh()` and re-fetches, so no tab is left showing stale data.
 *
 * Window events (not a Pinia store) keep producer and consumers decoupled —
 * the producer needn't import every consumer's store — and match the existing
 * `robo:*` window-event style (`robo:switch-tab`, `robo:hybrid-promote`).
 *
 * ## 편집 중에는 미룬다 (2026-09-11)
 *
 * 동시편집이 붙으면서 이 버스가 **남이 쓸 때마다** 울리게 됐다. 전에는 인제스천
 * 완료와 초기화 때만 울렸다 — 아무도 무언가를 열어 두고 있지 않은 순간이다.
 *
 * 열어 둔 채로 트리를 다시 그리면 두 가지가 일어난다.
 *
 *     쓰던 것이 사라진다   고치던 값·펼침·선택이 초기화된다
 *     패널이 깨진다        Inspector 안의 open-pencil federated 편집기는
 *                          형제 목록이 흔들리면 죽은 서브트리로 패치한다
 *                          ("Cannot set properties of null (setting '__vnode')")
 *
 * 그래서 **남이 바꾼 것**(`remote-change`)만 미룬다. 내가 일으킨 것(인제스천
 * 완료·초기화)은 내가 그 순간을 알고 있으므로 그대로 즉시 울린다.
 */
import { onMounted, onUnmounted } from 'vue'

const EVENT = 'robo:data-changed'

// 요소 단위 원격 변경. `robo:data-changed` 와 **일부러 따로 둔다** — 저쪽은
// "통째로 다시 읽어라"이고 이쪽은 "이것들만 갈아끼워라"다. 하나로 합치면
// 받는 쪽이 둘을 구별 못 해 결국 통째로 읽는다.
const REMOTE = 'robo:remote-changes'

// 지금 무언가를 편집 중인 화면의 수. 0 이 되면 미뤄 둔 것을 푼다.
let holds = 0
// 미뤄 둔 이유. 여러 번 와도 한 번만 울린다 — 열 번 바뀌었어도 할 일은 한 번이다.
let deferred = null

/**
 * 이 화면이 편집 중인 동안 남의 변경으로 다시 그리지 않는다.
 * 돌려주는 함수를 부르면 풀린다(안 부르면 영영 안 풀린다 — `onUnmounted` 에 건다).
 */
export function holdDataRefresh() {
  holds += 1
  let released = false
  return function release() {
    if (released) return
    released = true
    holds = Math.max(0, holds - 1)
    if (holds === 0 && deferred) {
      const reason = deferred
      deferred = null
      dispatch(reason)
    }
  }
}

/** 지금 미뤄 둔 남의 변경이 있나. 화면이 "상대가 바꿨습니다"를 띄울 때 쓴다. */
export function hasDeferredChange() {
  return deferred !== null
}

function dispatch(reason) {
  window.dispatchEvent(new CustomEvent(EVENT, { detail: { reason } }))
}

/**
 * 남의 변경은 **짧게 모았다가 한 번** 다시 읽는다.
 *
 * 남이 쓰면 보고 있던 창이 모두 같은 순간에 navigator 전체(contexts · BC 마다 full-tree …)를
 * 다시 읽는다. 창 20개면 같은 요청 100개가 한꺼번에 서버에 간다 — 포스코 로컬 측정(2026-11-19)
 * 5초마다 쓰기 한 번에 다시 읽기 p95 933ms. AI 채팅처럼 몇 번을 잇달아 쓰면 그 수만큼 또 읽는다.
 *
 * 그래서 남의 변경(`remote-change*`)은 첫 신호에서 `REMOTE_COALESCE_MS` + 창마다 다른 지연
 * (`REMOTE_JITTER_MS` 안)만큼 기다렸다가 한 번 보낸다. 그 사이 온 신호는 같이 묶인다.
 * 내 변경(인제스천 완료 · 지움 …)은 그대로 즉시 보낸다.
 */
const REMOTE_COALESCE_MS = 300
const REMOTE_JITTER_MS = 500
let remoteTimer = null
let remoteReason = null

function scheduleRemote(reason) {
  // 'remote-change' 가 하나라도 있으면 그것으로 보낸다 — 편집 중 미루기는 그 이유에만 걸린다.
  if (remoteReason !== 'remote-change') remoteReason = reason
  if (remoteTimer) return
  const delay = REMOTE_COALESCE_MS + Math.floor(Math.random() * REMOTE_JITTER_MS)
  remoteTimer = setTimeout(() => {
    remoteTimer = null
    const r = remoteReason
    remoteReason = null
    // 기다리는 사이 편집을 시작했으면 미룬다(손을 떼면 그때 보낸다).
    if (r === 'remote-change' && holds > 0) {
      deferred = r
      return
    }
    dispatch(r)
  }, delay)
}

/** Announce that graph data changed. `reason`: 'ingestion-complete' | 'cleared' | 'remote-change'. */
export function emitDataChanged(reason = 'unknown') {
  // 남이 바꾼 것만 미룬다. 내가 방금 인제스천을 끝냈으면 지금 보는 게 맞다.
  if (reason === 'remote-change' && holds > 0) {
    deferred = reason
    return
  }
  if (typeof reason === 'string' && reason.startsWith('remote-change')) {
    scheduleRemote(reason)
    return
  }
  dispatch(reason)
}

/**
 * Re-run `refreshFn` whenever graph data changes. Registers the listener on
 * mount and removes it on unmount — call once at `<script setup>` top level.
 */
export function useDataRefresh(refreshFn) {
  const handler = (e) => {
    try {
      refreshFn(e?.detail?.reason)
    } catch (err) {
      console.error('[dataLifecycle] refresh failed:', err)
    }
  }
  onMounted(() => window.addEventListener(EVENT, handler))
  onUnmounted(() => window.removeEventListener(EVENT, handler))
}


/**
 * 남이 바꾼 **요소 목록**을 알린다. 받는 쪽은 `syncAfterChanges` 로 제자리에
 * 적용한다 — 자기 창이 자기 저장을 반영할 때 쓰는 바로 그 길이다.
 *
 * 편집 중이라고 미루지 않는다. 통째로 다시 읽는 것이 아니라 그 요소만 바꾸는
 * 것이라, 내가 열어 둔 것만 빼면 화면이 흔들리지 않는다. 빼는 일은 보내는
 * 쪽(collab.store)이 한다 — 받는 쪽마다 다시 판단하게 두면 한 곳은 빠뜨린다.
 */
export function emitRemoteChanges(changes) {
  if (!Array.isArray(changes) || !changes.length) return
  window.dispatchEvent(new CustomEvent(REMOTE, { detail: { changes } }))
}

/** 남이 바꾼 요소 목록을 받는다. `<script setup>` 최상단에서 1회. */
export function useRemoteChanges(applyFn) {
  const handler = (e) => {
    try {
      applyFn(e?.detail?.changes || [])
    } catch (err) {
      console.error('[dataLifecycle] remote apply failed:', err)
    }
  }
  onMounted(() => window.addEventListener(REMOTE, handler))
  onUnmounted(() => window.removeEventListener(REMOTE, handler))
}
