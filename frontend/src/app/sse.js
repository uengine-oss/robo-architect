/**
 * 인증이 실리는 SSE — `EventSource` 대체.
 *
 * **`EventSource` 는 헤더를 못 싣는다.** 우리 인터셉터(`app/http.js`)는
 * `window.fetch` 를 감싸므로 `EventSource` 로 연 스트림에는
 * `Authorization` 도 `X-Project-Graph` 도 안 붙는다. 인증을 켠 뒤로 탐색·룰
 * 매핑이 통째로 401 이었다.
 *
 *     GET /api/ingest/hybrid/process/{sid}/{pid}/explore  →  401 Unauthorized
 *
 * 인증을 통과하더라도 프로젝트 헤더가 없으면 **엉뚱한 graph** 를 본다. 둘 다
 * 같은 뿌리다 — 스트림이 앱의 요청 경로를 안 지난다.
 *
 * `fetch` + `ReadableStream` 으로 읽으면 인터셉터를 그대로 지난다.
 *
 * ## EventSource 와 일부러 다른 점
 *
 * **자동 재연결이 없다.** 이 스트림들은 한 번 돌고 끝나는 작업(탐색·인제스천)
 * 이라, 끊겼을 때 되잇는 것은 같은 작업을 다시 시작하는 것과 같다 — LLM 을
 * 두 번 태우고 결과가 겹친다. 끊기면 끝난 것으로 본다.
 */

/**
 * @param {string} url 같은 출처 SSE 경로
 * @param {{ signal?: AbortSignal, endAsError?: boolean }} [opts]
 *   endAsError — 서버가 스트림을 닫았는데 호출부가 아직 안 닫았으면 `onerror` 를 부른다.
 *   `EventSource` 가 그렇게 한다(그리고 다시 붙는다 — 그것만 안 한다). 끝 신호를 `onerror` 로
 *   받던 호출부를 그대로 옮겨 올 때 쓴다(`openEventSource`).
 * @returns {{ addEventListener: Function, close: Function, onerror: Function|null }}
 *   `EventSource` 와 호환되는 최소 표면. 호출부를 안 고치고 바꿔 끼우기 위한 것.
 */
export function openSse(url, opts = {}) {
  const listeners = new Map()
  const controller = new AbortController()
  let closed = false
  const handle = {
    onerror: null,
    // EventSource 와 같은 이름 — 호출부를 안 고치고 바꿔 끼운다.
    onmessage: null,
    onopen: null,
    readyState: 0, // 0 CONNECTING · 1 OPEN · 2 CLOSED
    CONNECTING: 0,
    OPEN: 1,
    CLOSED: 2,
    addEventListener(name, fn) {
      const list = listeners.get(name) || []
      list.push(fn)
      listeners.set(name, list)
    },
    close() {
      if (closed) return
      closed = true
      handle.readyState = 2
      controller.abort()
    },
  }

  function emit(name, data) {
    for (const fn of listeners.get(name) || []) {
      // 한 구독자가 던져도 스트림을 끊지 않는다.
      try { fn({ data }) } catch { /* 구독자 사정 */ }
    }
    if (name === 'message' && typeof handle.onmessage === 'function') {
      try { handle.onmessage({ data }) } catch { /* 구독자 사정 */ }
    }
  }

  function fail(err) {
    if (closed) return
    if (typeof handle.onerror === 'function') {
      try { handle.onerror(err) } catch { /* 구독자 사정 */ }
    }
  }

  ;(async () => {
    try {
      const res = await fetch(url, {
        headers: { Accept: 'text/event-stream' },
        signal: opts.signal || controller.signal,
      })
      if (!res.ok || !res.body) {
        handle.readyState = 2
        fail(new Error(`SSE ${res.status}`))
        return
      }
      handle.readyState = 1
      if (typeof handle.onopen === 'function') {
        try { handle.onopen({}) } catch { /* 구독자 사정 */ }
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        // SSE 는 빈 줄로 이벤트를 가른다. \r\n 도 받는다.
        let cut
        while ((cut = buffer.search(/\r?\n\r?\n/)) !== -1) {
          const chunk = buffer.slice(0, cut)
          buffer = buffer.slice(cut).replace(/^\r?\n\r?\n/, '')
          let name = 'message'
          const dataLines = []
          for (const raw of chunk.split(/\r?\n/)) {
            if (raw.startsWith('event:')) name = raw.slice(6).trim()
            else if (raw.startsWith('data:')) dataLines.push(raw.slice(5).replace(/^ /, ''))
          }
          if (dataLines.length) emit(name, dataLines.join('\n'))
        }
      }
      // 서버가 닫았다 = 작업이 끝났다. 되잇지 않는다.
      if (opts.endAsError && !closed) {
        handle.readyState = 2
        fail(new Error('SSE closed by server'))
      }
      handle.close()
    } catch (err) {
      if (!closed) fail(err)
    }
  })()

  return handle
}

/**
 * `new EventSource(url)` 자리에 그대로 끼우는 판 — 인증·프로젝트 헤더가 실린다.
 *
 * 2026-11-18: 인증을 켠 서버 판(포스코 웹)에서 `new EventSource` 로 연 스트림이 전부 401 이었다.
 * 요구사항 명확화는 세션을 만들고 스트림을 못 받아 "딥 에이전트가 모호성을 스캔 중입니다…" 에서
 * 끝나지 않았다(서버는 스캔을 끝내거나 실패했는데 화면이 그것을 못 들었다).
 * 인증이 없는 판(lite)에서도 `X-Project-Graph` 가 안 실려 엉뚱한 graph 를 볼 수 있었다.
 *
 * `EventSource` 와 다른 점은 하나 — **다시 붙지 않는다**(한 번 도는 작업을 두 번 태우지 않는다).
 */
export function openEventSource(url) {
  return openSse(url, { endAsError: true })
}
