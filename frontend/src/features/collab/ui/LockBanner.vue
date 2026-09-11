<script setup>
/**
 * "지금 누가 이걸 고치고 있다."
 *
 * 못 잡았을 때 아무 말도 안 하면, 사람은 고칠 수 있다고 믿고 고친 다음 저장할
 * 때 실패한다 — 그 사이에 친 글자는 사라진다. **막는 것보다 먼저 알리는 것**이
 * 이 배너의 일이다.
 *
 * 잠기지 않았으면 아무것도 안 그린다.
 */
defineProps({
  /** `useElementLock().blockedBy` — 남이 잡고 있으면 그 사람, 아니면 null */
  holder: { type: Object, default: null },
})
</script>

<template>
  <div v-if="holder" class="lockbar">
    <span class="lockbar__icon">🔒</span>
    <span class="lockbar__text">
      <strong>{{ holder.displayName || holder.uid }}</strong> 님이 편집 중입니다.
      지금은 읽기만 됩니다.
    </span>
  </div>
</template>

<style scoped>
.lockbar {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 0 0 8px;
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
