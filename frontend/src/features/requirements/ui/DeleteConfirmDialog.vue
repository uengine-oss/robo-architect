<script setup>
import { ref, watch, computed } from 'vue'

/**
 * Delete confirmation (034 — recoverable deletion).
 *
 * Asks for confirmation and two opt-in choices:
 *  - removeDesign: also remove design elements this requirement *exclusively*
 *    implements (shared design is preserved). Default OFF (user decision).
 *  - disposition (Feature/Epic with children): delete child stories vs keep.
 *
 * Always notes the deletion is recoverable from "삭제 이력" — a snapshot is
 * archived before removal.
 */
const props = defineProps({
  target: { type: Object, default: null }, // { scope, id, name, hasChildren }
})
const emit = defineEmits(['confirm', 'cancel'])

const removeDesign = ref(false)
const deleteChildren = ref(true)

watch(
  () => props.target,
  () => {
    removeDesign.value = false
    deleteChildren.value = true
  },
)

const label = computed(() => {
  switch (props.target?.scope) {
    case 'epic':
      return 'Epic'
    case 'feature':
      return 'Feature'
    default:
      return 'User Story'
  }
})
const showChildren = computed(
  () => (props.target?.scope === 'feature' || props.target?.scope === 'epic') && props.target?.hasChildren,
)

function confirm() {
  emit('confirm', {
    removeDesign: removeDesign.value,
    disposition: deleteChildren.value ? 'delete' : 'unassign',
  })
}
</script>

<template>
  <div v-if="target" class="dialog-backdrop" @click.self="emit('cancel')">
    <div class="dialog dc">
      <div class="dialog__head">
        <h3>🗑 {{ label }} 삭제</h3>
        <button class="dialog__close" @click="emit('cancel')">×</button>
      </div>
      <div class="dialog__body">
        <p class="dc__name">
          <strong>{{ target.name }}</strong> 을(를) 삭제할까요?
        </p>

        <label v-if="showChildren" class="dc__opt">
          <input type="checkbox" v-model="deleteChildren" />
          <span v-if="target.scope === 'epic'">하위 Feature·User Story도 함께 삭제</span>
          <span v-else>하위 User Story도 함께 삭제 (해제 시 미분류로 이동)</span>
        </label>

        <label class="dc__opt">
          <input type="checkbox" v-model="removeDesign" />
          <span>
            관련 <strong>디자인도 함께 제거</strong>
            <em class="dc__hint">— 이 요구사항만 구현하는 설계 요소만 제거(공유 요소는 보존)</em>
          </span>
        </label>

        <p class="dc__recover">
          ↩︎ 삭제 내용은 스냅샷으로 보관되어 <strong>“삭제 이력”에서 복구</strong>할 수 있습니다.
        </p>
      </div>
      <div class="dialog__foot">
        <button class="btn" @click="emit('cancel')">취소</button>
        <button class="btn btn--danger" @click="confirm">삭제</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.42);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
}
.dialog.dc { width: 440px; max-width: 92vw; background: var(--color-bg); border-radius: 10px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35); overflow: hidden; }
.dialog__head { display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--color-border); }
.dialog__head h3 { margin: 0; font-size: 0.95rem; }
.dialog__close { border: none; background: transparent; font-size: 1.2rem; cursor: pointer;
  color: var(--color-text-light); }
.dialog__body { padding: 14px 16px; display: flex; flex-direction: column; gap: 12px; }
.dc__name { margin: 0; font-size: 0.86rem; }
.dc__opt { display: flex; align-items: flex-start; gap: 8px; font-size: 0.82rem; cursor: pointer; }
.dc__opt input { margin-top: 2px; }
.dc__hint { color: var(--color-text-light); font-style: normal; font-size: 0.74rem; display: block; }
.dc__recover { margin: 0; font-size: 0.76rem; color: var(--color-text-light);
  background: var(--color-bg-tertiary); padding: 8px 10px; border-radius: 6px; }
.dialog__foot { display: flex; justify-content: flex-end; gap: 8px;
  padding: 12px 16px; border-top: 1px solid var(--color-border); }
.btn { border: 1px solid var(--color-border); background: var(--color-bg-tertiary);
  color: var(--color-text); border-radius: 6px; padding: 5px 14px; font-size: 0.8rem; cursor: pointer; }
.btn--danger { border-color: #e03131; background: #e03131; color: #fff; }
.btn--danger:hover { filter: brightness(1.06); }
</style>
