<script setup>
/**
 * "지금 누가 이걸 고치고 있다."
 *
 * 못 잡았을 때 아무 말도 안 하면, 사람은 고칠 수 있다고 믿고 고친 다음 저장할
 * 때 실패한다 — 그 사이에 친 글자는 사라진다. **막는 것보다 먼저 알리는 것**이
 * 이 배너의 일이다.
 *
 * ## 뿌리가 항상 있다 — `v-if` 를 루트에 두지 않는다
 *
 * 루트에 `v-if` 를 두면 잠길 때/풀릴 때 **DOM 노드가 주석과 요소 사이를
 * 오간다.** 붙는 자리(Inspector)는 open-pencil federated 편집기를 품고 있어서,
 * 형제 목록이 한 칸 밀리면 Vue 의 패치가 죽은 서브트리로 들어간다. 실제로 그
 * 오류가 났다.
 *
 *     Cannot set properties of null (setting '__vnode')
 *     Cannot read properties of null (reading 'nextSibling')
 *
 * 같은 부류가 파일 상단에도 적혀 있다(FrameEditor 를 비동기로 못 싣는 이유).
 * 그래서 **바깥 껍데기는 늘 그대로 두고 안쪽만 바꾼다.** 비었을 때는 높이도
 * 여백도 0 이라 화면에는 없는 것과 같다.
 */
defineProps({
  /** `useElementLock().blockedBy` — 남이 잡고 있으면 그 사람, 아니면 null */
  holder: { type: Object, default: null },
})
</script>

<template>
  <div class="lockslot">
    <div v-if="holder" class="lockbar">
      <span class="lockbar__icon">🔒</span>
      <span class="lockbar__text">
        <strong>{{ holder.displayName || holder.uid }}</strong> 님이 편집 중입니다.
        지금은 읽기만 됩니다.
      </span>
    </div>
  </div>
</template>

<style scoped>
/* 비었을 때 자리를 안 차지한다. `:empty` 가 아니라 자식 유무로 재는 이유는
   주석 노드가 남기 때문이다. */
.lockslot { display: contents; }
.lockbar {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 8px 10px 0;
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
  background: rgba(220, 160, 60, 0.16);
  color: inherit;
}
.lockbar__icon { font-size: 12px; }
.lockbar__text { flex: 1; }
</style>
