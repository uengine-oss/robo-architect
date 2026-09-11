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

/** Announce that graph data changed. `reason`: 'ingestion-complete' | 'cleared' | 'remote-change'. */
export function emitDataChanged(reason = 'unknown') {
  // 남이 바꾼 것만 미룬다. 내가 방금 인제스천을 끝냈으면 지금 보는 게 맞다.
  if (reason === 'remote-change' && holds > 0) {
    deferred = reason
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
