<script setup>
import { ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

/**
 * 하위 User Story 자동 생성 — 제안 검토 창 (034 US5).
 * AI가 제안한 User Story 후보를 검토·수정·취사선택한 뒤 확정한다(HITL).
 * 확정한 항목만 그래프에 반영된다.
 */
const props = defineProps({
  // GenerateChildStoriesResponse: { scopeType, scopeId, boundedContextId, featureId, proposals }
  result: { type: Object, required: true },
  scopeName: { type: String, default: '' },
})
const emit = defineEmits(['close', 'confirmed'])

const store = useRequirementsStore()
// Each row: { selected, role, action, benefit }
const rows = ref((props.result.proposals || []).map((p) => ({
  selected: true,
  role: p.role || '',
  action: p.action || '',
  benefit: p.benefit || '',
})))
const busy = ref(false)
const errorMsg = ref('')

async function confirm() {
  const chosen = rows.value.filter((r) => r.selected && r.action.trim())
  if (!chosen.length) {
    emit('close')
    return
  }
  busy.value = true
  errorMsg.value = ''
  try {
    const data = await store.confirmChildStories({
      boundedContextId: props.result.boundedContextId,
      featureId: props.result.featureId,
      stories: chosen.map((r) => ({ role: r.role, action: r.action, benefit: r.benefit })),
    })
    emit('confirmed', data)
    emit('close')
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="dialog-backdrop" @click.self="emit('close')">
    <div class="dialog">
      <div class="dialog__head">
        <h3>하위 User Story 자동 생성 — 제안 검토</h3>
        <button class="dialog__close" @click="emit('close')">×</button>
      </div>
      <div class="dialog__body">
        <p class="dialog__hint">
          <strong>{{ scopeName }}</strong> 범위에 어울리는 User Story를 AI가 제안했습니다.
          체크된 항목만 추가됩니다. 내용은 직접 수정할 수 있습니다.
        </p>
        <p v-if="errorMsg" class="dialog__error">{{ errorMsg }}</p>
        <p v-if="!rows.length" class="dialog__empty">
          제안된 User Story가 없습니다. 잠시 후 다시 시도하거나 수동으로 추가하세요.
        </p>

        <div v-for="(r, i) in rows" :key="i" class="story-row" :class="{ off: !r.selected }">
          <input type="checkbox" v-model="r.selected" class="story-check" />
          <div class="story-fields">
            <label>역할 <input v-model="r.role" /></label>
            <label>행동 <input v-model="r.action" /></label>
            <label>효과 <input v-model="r.benefit" /></label>
          </div>
        </div>

        <div class="dialog__actions">
          <button class="btn" @click="emit('close')">취소</button>
          <button class="btn btn--primary" :disabled="busy" @click="confirm">
            {{ busy ? '추가 중...' : '선택 항목 추가' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}
.dialog {
  width: 600px; max-height: 84vh; background: var(--color-bg-secondary);
  border-radius: 10px; display: flex; flex-direction: column; overflow: hidden;
}
.dialog__head {
  display: flex; align-items: center; padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}
.dialog__head h3 { margin: 0; font-size: 0.95rem; }
.dialog__close {
  margin-left: auto; border: none; background: transparent; font-size: 1.2rem;
  cursor: pointer; color: var(--color-text-light);
}
.dialog__body { padding: 14px 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.dialog__hint { font-size: 0.78rem; color: var(--color-text-light); margin: 0; }
.dialog__error { color: #e03131; font-size: 0.78rem; margin: 0; }
.dialog__empty { font-size: 0.8rem; color: var(--color-text-light); font-style: italic; }
.story-row {
  display: flex; gap: 10px; padding: 10px; border: 1px solid var(--color-border);
  border-radius: 8px; align-items: flex-start;
}
.story-row.off { opacity: 0.45; }
.story-check { margin-top: 4px; }
.story-fields { flex: 1; display: flex; flex-direction: column; gap: 6px; }
label { display: flex; flex-direction: column; gap: 3px; font-size: 0.7rem; color: var(--color-text-light); }
label input {
  width: 100%; box-sizing: border-box; padding: 5px 8px; font-size: 0.8rem;
  background: var(--color-bg-tertiary); border: 1px solid var(--color-border);
  border-radius: 6px; color: var(--color-text);
}
.dialog__actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }
.btn { padding: 6px 14px; border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer; font-size: 0.78rem; background: var(--color-bg-tertiary); color: var(--color-text); }
.btn--primary { background: var(--color-accent); color: #fff; border-color: transparent; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
