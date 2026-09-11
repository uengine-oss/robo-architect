<script setup>
/**
 * 지금 이 프로젝트를 누가 보고 있나.
 *
 * **잠금보다 이것이 먼저다.** 요소를 선점 잠그더라도 "누가 잡았다"를 읽을
 * 근거가 없으면, 잠긴 요소는 그냥 안 고쳐지는 요소가 된다. 사람 목록이 먼저
 * 보여야 잠금이 말이 된다.
 *
 * 나 혼자일 때는 아무것도 안 그린다 — 늘 내 이름 하나가 떠 있으면 그 자리가
 * 정보가 아니라 장식이 된다.
 */
import { computed } from 'vue'
import { useCollabStore } from '@/features/collab/collab.store.js'
import { useAuthStore } from '@/features/auth/auth.store.js'

const collab = useCollabStore()
const auth = useAuthStore()

const others = computed(() => {
  const me = (auth.user || {}).uid
  return collab.viewers.filter((v) => v.uid !== me)
})

function initials(v) {
  const name = (v.displayName || v.uid || '').trim()
  return name.slice(0, 2) || '?'
}
</script>

<template>
  <div v-if="others.length" class="vchips" :title="`${others.length}명이 함께 보고 있습니다`">
    <span
      v-for="v in others.slice(0, 4)"
      :key="v.uid"
      class="vchips__one"
      :title="`${v.displayName} (${v.uid})`"
    >{{ initials(v) }}</span>
    <span v-if="others.length > 4" class="vchips__more">+{{ others.length - 4 }}</span>
  </div>
</template>

<style scoped>
.vchips { display: inline-flex; align-items: center; gap: 3px; margin-left: 8px; }
.vchips__one, .vchips__more {
  font-size: 10px;
  line-height: 1;
  padding: 4px 5px;
  border-radius: 999px;
  background: rgba(90, 140, 230, 0.22);
  white-space: nowrap;
}
.vchips__more { background: rgba(127, 127, 127, 0.18); }
</style>
