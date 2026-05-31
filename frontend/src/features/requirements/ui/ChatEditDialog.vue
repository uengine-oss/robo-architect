<script setup>
import ChatEditPanel from './ChatEditPanel.vue'

/**
 * Modal wrapper around ChatEditPanel for Epic/Feature (035).
 * (User Story hosts the same panel inline as its "AI 편집" tab.)
 */
defineProps({
  scope: { type: String, required: true }, // 'epic' | 'feature'
  itemId: { type: String, required: true },
  itemName: { type: String, default: '' },
  current: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['close', 'applied'])
const TITLE = { epic: 'Epic', feature: 'Feature' }
</script>

<template>
  <div class="dialog-backdrop" @click.self="emit('close')">
    <div class="dialog ce-dialog">
      <div class="dialog__head">
        <h3>✨ AI 편집 — {{ TITLE[scope] || scope }} · {{ itemName }}</h3>
        <button class="dialog__close" @click="emit('close')">×</button>
      </div>
      <div class="ce-dialog__body">
        <ChatEditPanel
          :scope="scope"
          :item-id="itemId"
          :item-name="itemName"
          :current="current"
          @applied="emit('applied', $event)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.42);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
}
.dialog.ce-dialog {
  width: 640px; max-width: 94vw; height: 80vh; max-height: 720px;
  background: var(--color-bg); border-radius: 10px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35); display: flex; flex-direction: column;
}
.dialog__head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--color-border); flex-shrink: 0;
}
.dialog__head h3 { margin: 0; font-size: 0.92rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dialog__close { border: none; background: transparent; font-size: 1.2rem; cursor: pointer; color: var(--color-text-light); }
.ce-dialog__body { flex: 1; min-height: 0; display: flex; flex-direction: column; }
</style>
