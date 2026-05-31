<script setup>
import { onMounted, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

/**
 * Deletion history + recovery (034 — option B snapshot).
 * Lists :DeletionRecord batches; a batch can be restored (re-creates the
 * snapshotted subtree) or permanently purged.
 */
const emit = defineEmits(['close'])
const store = useRequirementsStore()
const busy = ref(null) // batchId currently restoring/purging

const SCOPE_LABEL = { epic: 'Epic', feature: 'Feature', user_story: 'User Story' }

onMounted(() => store.fetchDeletionRecords())

async function restore(r) {
  busy.value = r.batchId
  try {
    const res = await store.restoreDeletion(r.batchId)
    if (!res.restored) window.alert(`복구할 수 없습니다: ${res.reason || '알 수 없음'}`)
  } catch (e) {
    window.alert(`복구 실패: ${e}`)
  } finally {
    busy.value = null
  }
}
async function purge(r) {
  if (!window.confirm(`'${r.rootName}' 삭제 기록을 영구 삭제할까요? 더 이상 복구할 수 없습니다.`)) return
  busy.value = r.batchId
  try {
    await store.purgeDeletion(r.batchId)
  } catch (e) {
    window.alert(`영구 삭제 실패: ${e}`)
  } finally {
    busy.value = null
  }
}
function when(iso) {
  return (iso || '').replace('T', ' ').slice(0, 16)
}
</script>

<template>
  <div class="dialog-backdrop" @click.self="emit('close')">
    <div class="dialog dh">
      <div class="dialog__head">
        <h3>↩︎ 삭제 이력</h3>
        <button class="dialog__close" @click="emit('close')">×</button>
      </div>
      <div class="dialog__body">
        <p class="dh__hint">
          삭제된 요구사항은 스냅샷으로 보관됩니다. <strong>복구</strong>하면 하위 항목과
          관계가 함께 되살아납니다. 영구 삭제하면 더 이상 복구할 수 없습니다.
        </p>
        <div v-if="!store.deletionRecords.length" class="dh__empty">삭제 이력이 없습니다.</div>
        <ul v-else class="dh__list">
          <li v-for="r in store.deletionRecords" :key="r.batchId" class="dh__item">
            <div class="dh__main">
              <span class="dh__scope" :class="r.scope">{{ SCOPE_LABEL[r.scope] || r.rootLabel }}</span>
              <span class="dh__name" :class="{ restored: r.restored }">{{ r.rootName }}</span>
              <span class="dh__meta">노드 {{ r.nodeCount }} · 관계 {{ r.relCount }} · {{ when(r.createdAt) }}</span>
            </div>
            <div class="dh__actions">
              <span v-if="r.restored" class="dh__badge">복구됨</span>
              <button v-else class="dh__btn dh__btn--restore" :disabled="busy === r.batchId" @click="restore(r)">
                복구
              </button>
              <button class="dh__btn dh__btn--purge" :disabled="busy === r.batchId" @click="purge(r)">
                영구삭제
              </button>
            </div>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.42);
  display: flex; align-items: center; justify-content: center; z-index: 2000;
}
.dialog.dh { width: 560px; max-width: 94vw; max-height: 80vh; background: var(--color-bg);
  border-radius: 10px; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35); display: flex; flex-direction: column; }
.dialog__head { display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--color-border); }
.dialog__head h3 { margin: 0; font-size: 0.95rem; }
.dialog__close { border: none; background: transparent; font-size: 1.2rem; cursor: pointer; color: var(--color-text-light); }
.dialog__body { padding: 12px 16px; overflow-y: auto; }
.dh__hint { margin: 0 0 12px; font-size: 0.76rem; color: var(--color-text-light); }
.dh__empty { font-size: 0.82rem; color: var(--color-text-light); font-style: italic; padding: 20px 0; text-align: center; }
.dh__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.dh__item { display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 7px; }
.dh__main { display: flex; align-items: center; gap: 8px; min-width: 0; flex-wrap: wrap; }
.dh__scope { font-size: 0.56rem; font-weight: 700; padding: 1px 5px; border-radius: 3px; flex-shrink: 0; }
.dh__scope.epic { background: rgba(92, 124, 250, 0.2); color: #5c7cfa; }
.dh__scope.feature { background: rgba(156, 54, 181, 0.18); color: #9c36b5; }
.dh__scope.user_story { background: rgba(64, 192, 87, 0.2); color: #40c057; }
.dh__name { font-size: 0.84rem; font-weight: 600; overflow: hidden; text-overflow: ellipsis; }
.dh__name.restored { text-decoration: line-through; color: var(--color-text-light); }
.dh__meta { font-size: 0.68rem; color: var(--color-text-light); }
.dh__actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.dh__badge { font-size: 0.66rem; color: #40c057; font-weight: 700; }
.dh__btn { border: 1px solid var(--color-border); background: var(--color-bg-tertiary);
  color: var(--color-text); border-radius: 6px; padding: 3px 10px; font-size: 0.74rem; cursor: pointer; }
.dh__btn:disabled { opacity: 0.5; cursor: default; }
.dh__btn--restore { border-color: var(--color-accent); color: var(--color-accent); background: transparent; }
.dh__btn--purge:hover { color: #e03131; border-color: #e03131; }
</style>
