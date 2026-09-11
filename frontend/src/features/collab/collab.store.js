/**
 * 같은 프로젝트를 여럿이 볼 때 — 남의 변경을 새로고침 없이 받는다.
 *
 * **응답은 늘 최신인데 다시 물을 계기가 없었다.** 실측이다 — bob 이 0 을 세고,
 * alice 가 쓰고, bob 이 다시 세면 1 이다. 화면이 틀린 게 아니라 **묻지 않은**
 * 것이다.
 *
 * 받는 쪽은 이미 다 있다 — 탭 네비게이터·캔버스·이벤트 모델링이 전부
 * `robo:data-changed` 에 붙어 있다(`app/lifecycle/dataLifecycle.js`). 여기서는
 * 서버가 밀어 준 변경을 그 버스에 얹기만 한다. **화면 코드는 한 줄도 안 바뀐다.**
 *
 * ## 자기 변경은 건너뛴다
 *
 * 내가 쓴 것도 알림으로 돌아온다. 그대로 갱신하면 방금 내가 만든 화면 상태를
 * 스스로 날린다(편집 중이던 선택·펼침이 접힌다). 서버가 누가 바꿨는지 실어
 * 주므로 내 것이면 흘린다.
 *
 * ## 끊기면 다시 잇는다 — 여기만
 *
 * `app/sse.js` 의 `openSse` 는 일부러 재연결을 안 한다. 그쪽 스트림들은 한 번
 * 돌고 끝나는 작업이라 되잇는 것이 LLM 을 한 번 더 태우는 것과 같기 때문이다.
 * **이 스트림은 반대다** — 계속 붙어 있는 것이 목적이고, 끊긴 채 두면 조용히
 * 옛 화면을 보게 된다. 그래서 여기서만 되잇는다.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { openSse } from '@/app/sse'
import { emitDataChanged } from '@/app/lifecycle/dataLifecycle'
import { useAuthStore } from '@/features/auth/auth.store.js'

// 되잇기 간격. 서버가 죽었을 때 초당 한 번씩 두드리지 않도록 늘려 간다.
const RETRY_MS = [2000, 5000, 10000, 30000]

export const useCollabStore = defineStore('collab', () => {
  const viewers = ref([])
  const rev = ref(0)
  const connected = ref(false)

  let source = null
  let graph = null
  let retry = 0
  let retryTimer = null
  let stopped = true

  function myUid() {
    return (useAuthStore().user || {}).uid || null
  }

  /** 이 알림이 지금 보고 있는 프로젝트의 것인가. 프로젝트를 바꾼 직후 옛
   *  스트림의 마지막 이벤트가 도착할 수 있다 — 그걸 받아들이면 **남의
   *  프로젝트 변경으로 내 화면을 다시 그린다.** */
  function mine(payload) {
    return !!payload && payload.graph === graph
  }

  function apply(payload) {
    if (!mine(payload)) return
    if (typeof payload.rev === 'number') rev.value = payload.rev
    if (Array.isArray(payload.viewers)) viewers.value = payload.viewers
  }

  function onChanged(payload) {
    if (!mine(payload)) return
    apply(payload)
    // 내가 쓴 것이면 이미 내 화면은 최신이다. 다시 그리면 편집 중이던 상태를
    // 내가 날린다.
    if (payload.actorUid && payload.actorUid === myUid()) return
    emitDataChanged('remote-change')
  }

  function scheduleRetry() {
    if (stopped) return
    const wait = RETRY_MS[Math.min(retry, RETRY_MS.length - 1)]
    retry += 1
    clearTimeout(retryTimer)
    retryTimer = setTimeout(() => { if (!stopped) open() }, wait)
  }

  function open() {
    close(false)
    if (!graph) return
    const es = openSse('/api/collab/stream')
    source = es
    es.addEventListener('hello', (e) => {
      connected.value = true
      retry = 0
      apply(JSON.parse(e.data))
    })
    es.addEventListener('changed', (e) => onChanged(JSON.parse(e.data)))
    es.addEventListener('viewers', (e) => apply(JSON.parse(e.data)))
    es.addEventListener('ping', () => { connected.value = true })
    es.onerror = () => {
      connected.value = false
      scheduleRetry()
    }
  }

  /** 이 프로젝트를 보기 시작한다. 프로젝트를 바꾸면 다시 부른다. */
  function watch(nextGraph) {
    if (nextGraph === graph && source) return
    stopped = false
    graph = nextGraph || null
    viewers.value = []
    rev.value = 0
    retry = 0
    if (graph) open()
    else close()
  }

  function close(hard = true) {
    clearTimeout(retryTimer)
    if (source) { try { source.close() } catch { /* 이미 닫힘 */ } }
    source = null
    connected.value = false
    if (hard) {
      stopped = true
      viewers.value = []
    }
  }

  return { viewers, rev, connected, watch, close }
})
