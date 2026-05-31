<script setup>
import { computed } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import ClarityRadar from './ClarityRadar.vue'

/**
 * Epic (BoundedContext) detail view (034 — US2).
 * Read-only summary: name, description, the child Feature list with
 * per-feature User Story counts, and the BC-scoped clarity radar (US4 —
 * the store re-fetches clarity for this scope on selection). Editing is via
 * the tree's ✎ button (EpicEditForm). Derived from the loaded tree DTO.
 */
const props = defineProps({
  epic: { type: Object, required: true }, // EpicNodeDTO
})
const emit = defineEmits(['edit', 'select-feature', 'generate-features', 'validate'])

const store = useRequirementsStore()
const features = computed(() => props.epic.features || [])
function storyCount(f) {
  return (f.userStories || []).length
}
</script>

<template>
  <div class="epic-detail">
    <div class="ed-head">
      <span class="ed-kind">EPIC</span>
      <h2 class="ed-title">{{ epic.displayName || epic.name }}</h2>
      <button class="ed-gen" title="Feature 자동 생성 (각 Feature = US·edge cases 포함)" @click="emit('generate-features')">✨ Feature 자동생성</button>
      <button class="ed-validate" title="DDD 적합성 검증" @click="emit('validate')">🔎 DDD 검증</button>
      <button class="ed-edit" title="편집" @click="emit('edit', epic)">✎ 편집</button>
    </div>

    <p v-if="epic.description" class="ed-desc">{{ epic.description }}</p>
    <p v-else class="ed-desc ed-desc--empty">설명이 없습니다.</p>

    <div class="ed-section">
      <div class="ed-section__label">Features ({{ features.length }})</div>
      <ul v-if="features.length" class="ed-list">
        <li
          v-for="f in features"
          :key="f.id"
          class="ed-list__item"
          @click="emit('select-feature', f.id)"
        >
          <span class="ed-badge feat">FEAT</span>
          <span class="ed-item-name">{{ f.name }}</span>
          <span class="ed-item-meta">US {{ storyCount(f) }}</span>
        </li>
      </ul>
      <div v-else class="ed-empty">
        아직 Feature가 없습니다. “+ 요구사항 추가”에서 Feature를 등록하세요.
      </div>
    </div>

    <div class="ed-section">
      <div class="ed-section__label">명확도 (이 Epic 범위)</div>
      <ClarityRadar v-if="store.clarityScores" :scores="store.clarityScores" />
      <div v-else class="ed-empty">명확도 데이터가 없습니다.</div>
    </div>
  </div>
</template>

<style scoped>
.epic-detail { padding: 14px 16px; overflow-y: auto; height: 100%; box-sizing: border-box; }
.ed-head { display: flex; align-items: center; gap: 8px; }
.ed-kind {
  font-size: 0.56rem; font-weight: 700; padding: 2px 5px; border-radius: 3px;
  background: rgba(92, 124, 250, 0.2); color: #5c7cfa;
}
.ed-title { margin: 0; font-size: 1rem; flex: 1; overflow: hidden; text-overflow: ellipsis; }
.ed-edit {
  border: 1px solid var(--color-border); background: var(--color-bg-tertiary);
  color: var(--color-text); border-radius: 6px; font-size: 0.72rem; padding: 3px 8px; cursor: pointer;
}
.ed-edit:hover { filter: brightness(1.1); }
.ed-gen {
  border: 1px solid var(--color-accent); background: transparent; color: var(--color-accent);
  border-radius: 6px; font-size: 0.72rem; padding: 3px 8px; cursor: pointer;
}
.ed-gen:hover { background: rgba(34, 139, 230, 0.12); }
.ed-validate {
  border: 1px solid var(--color-border); background: var(--color-bg-tertiary); color: var(--color-text);
  border-radius: 6px; font-size: 0.72rem; padding: 3px 8px; cursor: pointer;
}
.ed-validate:hover { filter: brightness(1.1); }
.ed-desc { font-size: 0.82rem; color: var(--color-text); margin: 10px 0 4px; white-space: pre-wrap; }
.ed-desc--empty { color: var(--color-text-light); font-style: italic; }
.ed-section { margin-top: 14px; }
.ed-section__label {
  font-size: 0.7rem; font-weight: 700; color: var(--color-text-light);
  text-transform: uppercase; margin-bottom: 6px;
}
.ed-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.ed-list__item {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer;
}
.ed-list__item:hover { background: var(--color-bg-tertiary); }
.ed-badge.feat {
  font-size: 0.54rem; font-weight: 700; padding: 1px 4px; border-radius: 3px;
  background: rgba(156, 54, 181, 0.18); color: #9c36b5;
}
.ed-item-name { flex: 1; font-size: 0.82rem; overflow: hidden; text-overflow: ellipsis; }
.ed-item-meta { font-size: 0.7rem; color: var(--color-text-light); }
.ed-empty { font-size: 0.78rem; color: var(--color-text-light); font-style: italic; padding: 6px 0; }
</style>
