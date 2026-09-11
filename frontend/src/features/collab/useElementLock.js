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

/**
 * @param {import('vue').Ref<string|null>} elementId 지금 열려 있는 요소
 * @param {() => string|undefined} [labelOf] 화면에 보일 이름(선택)
 */
export function useElementLock(elementId, labelOf) {
  const collab = useCollabStore()
  /** 내가 잡았나. 못 잡았으면 읽기로 연다. */
  const held = ref(false)
  let current = null

  /** 남이 잡고 있으면 그 사람. 아니면 null. */
  const blockedBy = computed(() =>
    elementId.value ? collab.heldByOther(elementId.value) : null,
  )
  /** 이 요소를 지금 고칠 수 있나. */
  const editable = computed(() => !blockedBy.value)

  async function take(id) {
    if (!id) return
    const r = await collab.lock(id, labelOf ? labelOf() : undefined)
    // 열려 있는 요소가 그새 바뀌었으면 방금 잡은 것은 남의 것이 된다.
    if (elementId.value !== id) { collab.unlock(id); return }
    held.value = !!r.ok
  }

  function drop() {
    if (current) { collab.unlock(current); current = null }
    held.value = false
  }

  watch(
    elementId,
    (id) => {
      if (id === current) return
      drop()
      current = id || null
      if (id) take(id)
    },
    { immediate: true },
  )

  onUnmounted(drop)

  return { held, blockedBy, editable, release: drop }
}
