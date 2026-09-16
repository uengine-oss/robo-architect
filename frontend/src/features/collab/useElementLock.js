/**
 * 요소를 여는 동안만 잡는다.
 *
 * 잠그는 순간을 "저장 버튼"이 아니라 **여는 순간**으로 잡는 이유는, 저장할 때
 * 잠가 봐야 이미 둘이 각자 고친 뒤라서다. 그때는 막을 것이 없고 한쪽 작업이
 * 사라진다.
 *
 * ## 못 잡아도 화면은 뜬다
 *
 * 남이 잡고 있으면 **읽기로 연다.** 아예 못 열게 하면 옆 사람이 뭘 하는지도
 * 못 보고, 그 사람이 창을 그냥 켜 둔 채 점심을 가면 아무도 아무것도 못 한다.
 * 잠금은 실수로 겹쳐 쓰는 것을 막는 것이지 사람을 막는 것이 아니다.
 *
 * ## 잠금이 남지 않게 하는 것
 *
 * 세 겹이다. 하나만 두면 반드시 유령 잠금이 남는다.
 *
 *     닫을 때        여기서 `unlock`
 *     창을 닫을 때   스트림이 끊기면 서버가 `release_all`
 *     그래도 남으면  60초 TTL — 브라우저를 강제 종료한 경우
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useCollabStore } from '@/features/collab/collab.store.js'
import { holdDataRefresh } from '@/app/lifecycle/dataLifecycle'

/**
 * @param {import('vue').Ref<string|null>} elementId 지금 열려 있는 요소
 * @param {() => string|undefined} [labelOf] 화면에 보일 이름(선택)
 */
export function useElementLock(elementId, labelOf) {
  const collab = useCollabStore()
  /** 내가 잡았나. 못 잡았으면 읽기로 연다. */
  const held = ref(false)
  let current = null

  // **잡은 동안에만** 남의 변경으로 다시 그리지 않는다.
  //
  // 이 자리(Inspector)는 open-pencil federated 편집기를 품고 있어서, 남이 쓸
  // 때마다 트리를 다시 그리면 죽은 서브트리로 패치가 들어간다. 고치던 값이
  // 초기화되는 문제도 같이 없어진다. 그래서 잠금을 잡은 동안은 미룬다.
  //
  // **그런데 열기만 하면 무조건 미루게 해 뒀던 것이 문제였다.** 읽기로 보는
  // 사람까지 막혔다. 그 사람은 덮어쓸 글자가 없는데, 옆 사람이 저장해도 아무
  // 일이 안 일어나고 **옛 값을 계속 본다** — "실시간이 안 된다"는 보고가 이것이다.
  //
  //     잡았다    미룬다   내가 치던 것이 날아가면 안 된다
  //     읽기      안 미룬다 잃을 것이 없다. 최신을 봐야 한다
  //
  // 목록 없는 쓰기(`changes` 가 안 실린 경우)는 거친 알림밖에 없어서, 이걸
  // 막으면 그 변경은 **영영 안 보인다.** 그래서 갈래를 나눈다.
  let releaseRefreshHold = null
  function holdWhileEditing(on) {
    if (on && !releaseRefreshHold) releaseRefreshHold = holdDataRefresh()
    else if (!on && releaseRefreshHold) { releaseRefreshHold(); releaseRefreshHold = null }
  }

  /** 남이 잡고 있으면 그 사람. 아니면 null. */
  const blockedBy = computed(() =>
    elementId.value ? collab.heldByOther(elementId.value) : null,
  )
  /** 이 요소를 지금 고칠 수 있나. */
  const editable = computed(() => !blockedBy.value)

  // 다시 집는 요청이 겹치지 않게. 스트림이 2초마다 도는데 그때마다 새로 집으면
  // 답이 오기 전에 또 보낸다.
  //
  // **그런데 이 빗장은 스스로 풀려야 한다.** 요청 하나가 영영 안 끝나면
  // (백엔드 포화·네트워크 블랙홀) `taking` 이 true 로 굳고, 그 뒤로는 서버가
  // 아무리 'free' 를 줘도 **다시 집는 일이 영영 안 일어난다.** 이건 §58 이
  // 고치려던 바로 그 모양 — "만료 뒤 돌아갈 길이 없다" — 이 다른 이유로
  // 되살아난 것이다. 그래서 시간 제한을 둔다.
  const TAKE_TIMEOUT_MS = 10_000
  let taking = false

  async function take(id) {
    if (!id || taking) return
    taking = true
    try {
      await Promise.race([
        _take(id),
        new Promise((resolve) => setTimeout(resolve, TAKE_TIMEOUT_MS)),
      ])
    } finally {
      // 늦게 끝난 요청이 남아 있어도 빗장은 푼다. 그 요청이 나중에 성공하면
      // 서버 상태가 'mine' 으로 오고, 위 watch 가 `held` 를 맞춰 준다.
      taking = false
    }
  }

  async function _take(id) {
    const r = await collab.lock(id, labelOf ? labelOf() : undefined)
    // 열려 있는 요소가 그새 바뀌었으면 방금 잡은 것은 남의 것이 된다.
    if (elementId.value !== id) { collab.unlock(id); return }
    held.value = !!r.ok
    // 잡았으면 그때부터 미룬다. 못 잡았으면 읽기이므로 계속 받는다.
    holdWhileEditing(held.value)
    // **잡았을 때만 '편집 중'이다.** 못 잡았으면 나는 읽기로 보고 있는
    // 것이고, 그때는 상대 변경이 **보여야 한다** — 안 보이면 옛 값을 보면서
    // "실시간이 안 된다"고 하게 된다. 실제로 그렇게 나왔다.
    collab.setEditing(r.ok ? id : null)
  }

  function drop() {
    if (current) { collab.unlock(current); current = null }
    collab.setEditing(null)
    held.value = false
    holdWhileEditing(false)
  }

  watch(
    elementId,
    (id) => {
      if (id === current) return
      drop()
      current = id || null
      // 잠금을 잡기 **전**에는 편집 중이 아니다. 여기서 미리 표시하면, 못 잡는
      // 경우에도 잠깐 상대 변경이 막힌다.
      collab.setEditing(null)
      if (id) take(id)
    },
    { immediate: true },
  )

  // ── 서버가 진실이다 — 내 잠금이 사라졌으면 다시 집는다 ────────────────
  //
  // **오래 잡고 있으면 선점이 풀리고 그 뒤로 아무것도 안 됐다.**
  //
  // 서버 TTL 은 60초이고 스트림이 2초마다 갱신한다. 절전·네트워크 끊김·재연결
  // 백오프(최대 30초)로 스트림이 그보다 오래 멎으면 잠금이 걷힌다. 그런데
  // `take()` 는 **열린 요소가 바뀔 때만** 돌고 `held` 는 서버 목록과 안 맞춰져서,
  // 화면은 계속 내가 잡은 줄 알았다 — 입력칸은 열려 있고, 저장하면 409 를 맞고,
  // 닫았다 다시 열기 전에는 되돌아갈 길이 없었다.
  //
  // 그래서 **서버가 들고 있는 상태를 따라간다.**
  //
  //     mine    내 것이다            held 를 맞춘다
  //     free    아무도 안 잡았다      **다시 집는다** — 내가 아직 열어 두고 있으니까
  //     other   남이 가져갔다        읽기로 내린다. 배너는 `blockedBy` 가 띄운다
  //
  // 끊긴 동안에는 목록이 낡아서 `mine` 으로 남는다 — 그때는 아무것도 안 한다.
  // 다시 붙으면 `hello` 가 새 목록을 주고, 그 자리에서 `free` 가 되어 되집는다.
  watch(
    () => (elementId.value ? collab.holderState(elementId.value) : null),
    (state) => {
      const id = elementId.value
      if (!id || id !== current || !state) return
      if (state === 'mine') {
        if (!held.value) {
          held.value = true
          holdWhileEditing(true)
          collab.setEditing(id)
        }
        return
      }
      if (state === 'other') {
        // **뺏긴 것을 숨기지 않는다.** 읽기로 내려야 입력칸이 잠기고 배너가 뜬다.
        if (held.value) {
          held.value = false
          holdWhileEditing(false)
          collab.setEditing(null)
        }
        return
      }
      // free — 아무도 안 잡았다. 내가 열어 두고 있으면 내 것이어야 한다.
      take(id)
    },
  )

  onUnmounted(() => {
    // `drop` 이 미루기까지 푼다. 안 풀면 이 창은 영영 남의 변경을 안 받는다.
    drop()
  })

  return { held, blockedBy, editable, release: drop }
}
