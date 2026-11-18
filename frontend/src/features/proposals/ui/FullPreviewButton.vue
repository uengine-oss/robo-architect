<script setup>
import { computed, ref } from 'vue'
import { collectPreviewBcIds, openFullPreview } from '../proposalPreview'

/**
 * B-4 ⑧ — 프로포절 머리의 "전체 미리보기" 단추.
 * 항목 하나를 고르지 않고 제안 전체를 Design(오버레이) 또는 Processes(읽기 전용)로 연다.
 * 실제 오케스트레이션은 App.vue 가 robo:open-preview(full) 로 받는다 — 이 컴포넌트는 뷰어를 모른다.
 */
const props = defineProps({
  proposal: { type: Object, default: null },
})

const busy = ref(false)
const bcCount = computed(() => collectPreviewBcIds(props.proposal).length)

async function open(viewer) {
  if (busy.value) return
  busy.value = true
  try {
    await openFullPreview(props.proposal, viewer)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <span class="full-preview" data-testid="full-preview">
    <button
      class="full-preview__btn"
      :disabled="busy || !proposal"
      :title="`제안 전체를 적재 전 오버레이로 봅니다${bcCount ? ` (BC ${bcCount}개)` : ''} — 읽기 전용`"
      data-testid="full-preview-design"
      @click="open('design')"
    >전체 미리보기</button>
    <button
      class="full-preview__btn full-preview__btn--sub"
      :disabled="busy || !proposal"
      title="Processes(이벤트 모델) 화면을 미리보기 상태(읽기 전용)로 엽니다"
      data-testid="full-preview-processes"
      @click="open('processes')"
    >Processes</button>
  </span>
</template>

<style scoped>
.full-preview { display: inline-flex; gap: 0; }
.full-preview__btn {
  font-size: 11px;
  padding: 2px 8px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
  color: var(--color-text);
  cursor: pointer;
  border-radius: 4px 0 0 4px;
}
.full-preview__btn--sub { border-left: none; border-radius: 0 4px 4px 0; color: var(--color-text-light); }
.full-preview__btn:hover:not(:disabled) { border-color: var(--color-accent); }
.full-preview__btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
