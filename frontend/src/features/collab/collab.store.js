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
import { computed, ref } from 'vue'
import { openSse } from '@/app/sse'
import { emitDataChanged, emitRemoteChanges } from '@/app/lifecycle/dataLifecycle'
import { useAuthStore } from '@/features/auth/auth.store.js'

// 되잇기 간격. 서버가 죽었을 때 초당 한 번씩 두드리지 않도록 늘려 간다.
const RETRY_MS = [2000, 5000, 10000, 30000]

export const useCollabStore = defineStore('collab', () => {
  const viewers = ref([])
  const rev = ref(0)
  /**
   * 내가 열어 둔 요소를 남이 고쳤다. 값은 그 사람의 사번.
   *
   * **조용히 두면 안 된다.** 내 화면은 옛 값을 들고 있고, 저장하면 상대 변경을
   * 덮는다. 잠금을 잡았으면 여기까지 올 일이 없지만, 읽기로 열었거나 잠금이
   * 만료된 뒤라면 생긴다.
   */
  const conflictOnOpenElement = ref(null)
  const connected = ref(false)
  /** 지금 잡혀 있는 요소들. 서버가 밀어 준다 — 여기서 지어내지 않는다. */
  const locks = ref([])
  /** 내가 지금 열어 놓고 고치는 요소. 남의 변경이 와도 이것만은 안 건드린다. */
  const editingElementId = ref(null)

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
    if (Array.isArray(payload.locks)) locks.value = payload.locks
  }

  function onChanged(payload) {
    if (!mine(payload)) return
    apply(payload)
    // 내가 쓴 것이면 이미 내 화면은 최신이다. 다시 그리면 편집 중이던 상태를
    // 내가 날린다.
    if (payload.actorUid && payload.actorUid === myUid()) return

    // **목록이 있으면 그 요소만 갈아끼운다.** 통째로 다시 읽지 않으므로
    // 상대가 편집 중이어도 화면이 안 흔들린다.
    //
    // `changes` 가 **없는 것**과 **빈 것**은 다르다. 없으면 서버가 모른다는
    // 뜻이라 거친 길로 가야 하고, 비었으면 정말 바뀐 요소가 없다는 뜻이다.
    // 합치면 빠진 변경이 조용히 사라진다.
    if (Array.isArray(payload.changes)) {
      const open = editingElementId.value
      const safe = open
        ? payload.changes.filter((c) => c && c.targetId !== open)
        : payload.changes
      emitRemoteChanges(safe)
      // 내가 열어 둔 것이 바뀌었다면 저장할 때 덮어쓰게 된다 — 알려는 준다.
      if (open && safe.length !== payload.changes.length) {
        conflictOnOpenElement.value = payload.actorUid || true
      }
    }

    // **목록을 보냈어도 거친 쪽을 같이 울린다.**
    //
    // 요소 목록을 제자리에 반영할 줄 아는 곳은 캔버스뿐이다. 네비게이터 트리·
    // 이벤트 모델링·요구사항 화면은 여전히 `robo:data-changed` 만 듣는다. 여기서
    // 끊으면 **AI 채팅으로 이름을 바꿨을 때 캔버스만 바뀌고 트리는 영영 안
    // 바뀐다** — 실제로 그렇게 만들었다가 되돌렸다.
    //
    // 편집 중이면 이 쪽은 `holdDataRefresh` 가 미룬다(트리를 다시 그리면 편집
    // 중이던 화면이 초기화되므로). 그동안에도 캔버스는 위에서 이미 반영됐다 —
    // **급한 쪽은 즉시, 나머지는 손을 뗄 때**가 이 둘의 역할 분담이다.
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
    es.addEventListener('locks', (e) => apply(JSON.parse(e.data)))
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
    locks.value = []
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
      locks.value = []
    }
  }

  // ── 선점 잠금 ──────────────────────────────────────────────────────────
  //
  // **낙관적으로 그리지 않는다.** 눌렀을 때 먼저 잠긴 것처럼 보여 놓고 서버가
  // 거절하면, 그 짧은 사이에 사람이 글자를 친다. 서버 답을 받고 나서 그린다.

  const byId = computed(() => {
    const m = new Map()
    for (const l of locks.value) m.set(l.elementId, l)
    return m
  })

  /** 이 요소를 남이 잡고 있나. 내 잠금은 '잠김'이 아니다. */
  function heldByOther(elementId) {
    const l = byId.value.get(elementId)
    if (!l) return null
    return l.uid === myUid() ? null : l
  }

  /** 이 요소를 **내가** 잡고 있나 — 서버가 그렇게 알고 있나.
   *
   *  "내가 잡았다고 믿는 것"과 "서버가 내 것으로 들고 있는 것"은 다르다.
   *  스트림이 TTL(60초)보다 오래 멎으면 서버는 걷어가는데 화면은 계속 잡은
   *  줄 안다 — 그러면 입력칸이 열린 채 남고 저장할 때 409 를 맞는다.
   *  **서버 쪽이 진실이므로 여기서 묻는다.** */
  function heldByMe(elementId) {
    const l = byId.value.get(elementId)
    return !!l && l.uid === myUid()
  }

  /** 지금 이 요소가 누구 것인가 — `mine` · `other` · `free`.
   *  받는 쪽마다 `locks` 를 뒤져 판단하게 두면 기준이 갈린다. 한 곳에서 답한다. */
  function holderState(elementId) {
    if (!elementId) return 'free'
    if (heldByMe(elementId)) return 'mine'
    return heldByOther(elementId) ? 'other' : 'free'
  }

  /**
   * 풀기를 **잠깐 미뤄 둔 것들**. 키는 elementId.
   *
   * 화면이 잠깐 사라지는 것과 사람이 손을 떼는 것은 다르다. Design 탭은
   * 오른쪽 자리 하나를 Inspector 와 챗이 `v-if` 로 나눠 쓰기 때문에, 챗으로
   * 바꾸면 Inspector 가 unmount 되고 거기서 잠금을 푼다 — 사람은 같은 요소를
   * 계속 붙들고 있는데 서버에서는 놓아 버린다. 그 틈에 남이 집어 갈 수 있다.
   *
   * 그래서 **바로 풀지 않고 잠깐 기다린다.** 그 사이에 같은 요소를 다시
   * 잡으면(패널을 바꾼 것이었다면) 예약을 취소한다. 정말 닫았으면 시간이
   * 지나 풀린다.
   *
   * 유예는 짧게 둔다 — 길면 "손을 떼면 풀린다"가 거짓말이 된다. 서버 TTL(60초)
   * 과 스트림 끊김 시 `release_all` 이 뒤를 받쳐 준다.
   */
  const RELEASE_GRACE_MS = 5_000
  const pendingRelease = new Map()

  function cancelRelease(elementId) {
    const t = pendingRelease.get(elementId)
    if (t) { clearTimeout(t); pendingRelease.delete(elementId) }
  }

  /** 유예를 두고 푼다. 그 사이 다시 잡으면 없던 일이 된다. */
  function unlockSoon(elementId) {
    if (!graph || !elementId || pendingRelease.has(elementId)) return
    pendingRelease.set(elementId, setTimeout(() => {
      pendingRelease.delete(elementId)
      unlock(elementId)
    }, RELEASE_GRACE_MS))
  }

  async function lock(elementId, label) {
    if (!graph || !elementId) return { ok: false }
    // 다시 잡았다 = 놓은 게 아니었다.
    cancelRelease(elementId)
    const r = await fetch('/api/collab/lock', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ elementId, label }),
    })
    const body = await r.json().catch(() => ({ ok: false }))
    if (body.ok) {
      // 다음 스트림 바퀴(최대 2초)를 기다리지 않고 내 화면에 먼저 반영한다.
      // 서버가 이미 승인한 사실이라 지어내는 것이 아니다.
      if (!byId.value.has(elementId)) {
        locks.value = [...locks.value, { elementId, uid: myUid(), label }]
      }
    }
    return body
  }

  async function unlock(elementId) {
    if (!graph || !elementId) return
    cancelRelease(elementId)
    locks.value = locks.value.filter((l) => l.elementId !== elementId)
    await fetch('/api/collab/unlock', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ elementId }),
    }).catch(() => {})
  }

  /** 지금 고치고 있는 요소를 알린다. `useElementLock` 이 부른다.
   *  **한 곳에서만 판단한다** — 받는 쪽마다 "이건 내가 열어 둔 건가"를 다시
   *  재게 두면 한 곳은 빠뜨리고, 빠뜨린 곳에서 남의 변경이 내 편집을 덮는다. */
  function setEditing(id) {
    editingElementId.value = id || null
    if (!id) conflictOnOpenElement.value = null
  }

  return {
    viewers, rev, connected, locks, conflictOnOpenElement,
    heldByOther, heldByMe, holderState, lock, unlock, unlockSoon, setEditing, watch, close,
  }
})
