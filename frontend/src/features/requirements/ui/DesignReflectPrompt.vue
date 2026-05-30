<script setup>
/**
 * 설계 자동 반영 프롬프트 (034 US7).
 * Event Modeling / Design 탭 진입 시 설계가 반영되지 않은 User Story가 있으면
 * "설계에 반영하시겠습니까?"를 묻는다. 미반영 US 식별은 backend가 담당.
 */
defineProps({
  pending: { type: Array, default: () => [] }, // [PendingUS]
})
const emit = defineEmits(['confirm', 'dismiss', 'dont-ask'])
</script>

<template>
  <div class="drp-backdrop">
    <div class="drp">
      <div class="drp__head">
        <span class="drp__icon">🧩</span>
        <h3>설계에 반영하시겠습니까?</h3>
      </div>
      <p class="drp__body">
        설계(Event Modeling)에 아직 반영되지 않은 User Story가
        <strong>{{ pending.length }}개</strong> 있습니다.
        지금 설계 생성을 진행할 수 있습니다.
      </p>
      <ul class="drp__list">
        <li v-for="us in pending.slice(0, 5)" :key="us.userStoryId">
          {{ us.role }}: {{ us.action }}
        </li>
        <li v-if="pending.length > 5" class="more">… 외 {{ pending.length - 5 }}개</li>
      </ul>
      <div class="drp__actions">
        <button class="btn" @click="emit('dont-ask')">이번 세션 동안 묻지 않기</button>
        <button class="btn" @click="emit('dismiss')">아니오</button>
        <button class="btn btn--primary" @click="emit('confirm')">예, 설계 반영</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.drp-backdrop {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); z-index: 1200;
  display: flex; align-items: center; justify-content: center;
}
.drp {
  width: 480px; background: var(--color-bg-secondary); border-radius: 12px;
  padding: 18px 20px; border: 1px solid var(--color-border);
}
.drp__head { display: flex; align-items: center; gap: 8px; }
.drp__icon { font-size: 1.2rem; }
.drp__head h3 { margin: 0; font-size: 1rem; }
.drp__body { font-size: 0.86rem; color: var(--color-text); margin: 12px 0 8px; }
.drp__list { margin: 0 0 12px; padding-left: 18px; font-size: 0.78rem; color: var(--color-text-light); }
.drp__list li { margin: 2px 0; }
.drp__list .more { list-style: none; font-style: italic; }
.drp__actions { display: flex; gap: 8px; justify-content: flex-end; }
.btn { padding: 6px 12px; border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer; font-size: 0.76rem; background: var(--color-bg-tertiary); color: var(--color-text); }
.btn--primary { background: var(--color-accent); color: #fff; border-color: transparent; }
</style>
