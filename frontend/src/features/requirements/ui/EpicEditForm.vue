<script setup>
import { ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

/**
 * Epic (BoundedContext) edit dialog (034 — US3).
 * Renames / re-describes an Epic via PATCH /bounded-context. Child Features
 * and User Stories stay attached (relationships preserved server-side).
 */
const props = defineProps({
  epic: { type: Object, required: true }, // { id, name, displayName, description }
})
const emit = defineEmits(['close', 'saved'])

const store = useRequirementsStore()
const name = ref(props.epic.displayName || props.epic.name || '')
const description = ref(props.epic.description || '')
const busy = ref(false)
const errorMsg = ref('')

async function save() {
  if (!name.value.trim()) {
    errorMsg.value = 'Epic 이름은 비울 수 없습니다.'
    return
  }
  busy.value = true
  errorMsg.value = ''
  try {
    await store.updateEpic(props.epic.id, {
      name: name.value.trim(),
      description: description.value,
    })
    emit('saved')
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
        <h3>Epic 편집</h3>
        <button class="dialog__close" @click="emit('close')">×</button>
      </div>
      <div class="dialog__body">
        <p v-if="errorMsg" class="dialog__error">{{ errorMsg }}</p>
        <label>이름 <input v-model="name" /></label>
        <label>설명 <textarea v-model="description" rows="3" /></label>
        <div class="dialog__actions">
          <button class="btn" @click="emit('close')">취소</button>
          <button class="btn btn--primary" :disabled="busy || !name.trim()" @click="save">
            {{ busy ? '저장 중...' : '저장' }}
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
  width: 440px; background: var(--color-bg-secondary); border-radius: 10px;
  display: flex; flex-direction: column; overflow: hidden;
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
.dialog__body { padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.dialog__error { color: #e03131; font-size: 0.78rem; margin: 0; }
label { display: flex; flex-direction: column; gap: 3px; font-size: 0.72rem; color: var(--color-text-light); }
label input, label textarea {
  width: 100%; box-sizing: border-box; padding: 6px 8px; font-size: 0.8rem;
  background: var(--color-bg-tertiary); border: 1px solid var(--color-border);
  border-radius: 6px; color: var(--color-text);
}
.dialog__actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }
.btn { padding: 6px 14px; border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer; font-size: 0.78rem; background: var(--color-bg-tertiary); color: var(--color-text); }
.btn--primary { background: var(--color-accent); color: #fff; border-color: transparent; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
