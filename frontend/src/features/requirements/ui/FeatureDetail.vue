<script setup>
import { computed } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import ClarityRadar from './ClarityRadar.vue'

/**
 * Feature detail view (034 — US2).
 * Read-only summary: name, description, source, the child User Story list,
 * and the feature-scoped clarity radar (US4 — the store re-fetches clarity
 * for this scope on selection). Editing is via the tree's ✎ button
 * (FeatureEditForm). Selecting a story delegates to the user-story flow.
 */
const props = defineProps({
  feature: { type: Object, required: true }, // FeatureNodeDTO
})
const emit = defineEmits(['edit', 'select-user-story', 'generate-stories', 'validate', 'clarify', 'delete'])

const store = useRequirementsStore()
const stories = computed(() => props.feature.userStories || [])
</script>

<template>
  <div class="feature-detail">
    <div class="fd-head">
      <span class="fd-kind">FEAT</span>
      <h2 class="fd-title">{{ feature.name }}</h2>
      <span v-if="feature.source" class="fd-source">{{ feature.source }}</span>
      <button class="fd-gen" title="하위 User Story 자동 생성" @click="emit('generate-stories')">✨ 하위 US 자동생성</button>
      <button class="fd-validate" title="DDD 적합성 검증" @click="emit('validate')">🔎 DDD 검증</button>
      <button class="fd-validate" title="요구사항 명확화" @click="emit('clarify')">🔍 명확화</button>
      <button class="fd-edit" title="편집" @click="emit('edit', feature)">✎ 편집</button>
      <button class="fd-delete" title="삭제" @click="emit('delete')">🗑 삭제</button>
    </div>

    <p v-if="feature.description" class="fd-desc">{{ feature.description }}</p>
    <p v-else class="fd-desc fd-desc--empty">설명이 없습니다.</p>

    <div class="fd-section">
      <div class="fd-section__label">User Stories ({{ stories.length }})</div>
      <ul v-if="stories.length" class="fd-list">
        <li
          v-for="us in stories"
          :key="us.id"
          class="fd-list__item"
          @click="emit('select-user-story', us.id)"
        >
          <span class="fd-badge us">US</span>
          <span class="fd-item-name">{{ us.role }}: {{ us.action }}</span>
        </li>
      </ul>
      <div v-else class="fd-empty">
        아직 User Story가 없습니다. “+ 요구사항 추가”에서 User Story를 등록하세요.
      </div>
    </div>

    <div v-if="(feature.edgeCases || []).length" class="fd-section">
      <div class="fd-section__label">Edge Cases</div>
      <ul class="fd-speclist">
        <li v-for="(e, i) in feature.edgeCases" :key="i">{{ e }}</li>
      </ul>
    </div>
    <div v-if="(feature.assumptions || []).length" class="fd-section">
      <div class="fd-section__label">가정 (Assumptions)</div>
      <ul class="fd-speclist">
        <li v-for="(a, i) in feature.assumptions" :key="i">{{ a }}</li>
      </ul>
    </div>

    <div class="fd-section">
      <div class="fd-section__label">명확도 (이 Feature 범위)</div>
      <ClarityRadar v-if="store.clarityScores" :scores="store.clarityScores" />
      <div v-else class="fd-empty">명확도 데이터가 없습니다.</div>
    </div>
  </div>
</template>

<style scoped>
.feature-detail { padding: 14px 16px; overflow-y: auto; height: 100%; box-sizing: border-box; }
.fd-head { display: flex; align-items: center; gap: 8px; }
.fd-kind {
  font-size: 0.56rem; font-weight: 700; padding: 2px 5px; border-radius: 3px;
  background: rgba(156, 54, 181, 0.18); color: #9c36b5;
}
.fd-title { margin: 0; font-size: 1rem; flex: 1; overflow: hidden; text-overflow: ellipsis; }
.fd-source {
  font-size: 0.6rem; padding: 1px 5px; border-radius: 3px;
  background: var(--color-bg-tertiary); color: var(--color-text-light); text-transform: uppercase;
}
.fd-edit {
  border: 1px solid var(--color-border); background: var(--color-bg-tertiary);
  color: var(--color-text); border-radius: 6px; font-size: 0.72rem; padding: 3px 8px; cursor: pointer;
}
.fd-edit:hover { filter: brightness(1.1); }
.fd-gen {
  border: 1px solid var(--color-accent); background: transparent; color: var(--color-accent);
  border-radius: 6px; font-size: 0.72rem; padding: 3px 8px; cursor: pointer;
}
.fd-gen:hover { background: rgba(34, 139, 230, 0.12); }
.fd-validate {
  border: 1px solid var(--color-border); background: var(--color-bg-tertiary); color: var(--color-text);
  border-radius: 6px; font-size: 0.72rem; padding: 3px 8px; cursor: pointer;
}
.fd-validate:hover { filter: brightness(1.1); }
.fd-delete {
  border: 1px solid var(--color-border); background: var(--color-bg-tertiary); color: #e03131;
  border-radius: 6px; font-size: 0.72rem; padding: 3px 8px; cursor: pointer;
}
.fd-delete:hover { background: #e03131; color: #fff; border-color: #e03131; }
.fd-desc { font-size: 0.82rem; color: var(--color-text); margin: 10px 0 4px; white-space: pre-wrap; }
.fd-desc--empty { color: var(--color-text-light); font-style: italic; }
.fd-section { margin-top: 14px; }
.fd-section__label {
  font-size: 0.7rem; font-weight: 700; color: var(--color-text-light);
  text-transform: uppercase; margin-bottom: 6px;
}
.fd-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.fd-list__item {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer;
}
.fd-list__item:hover { background: var(--color-bg-tertiary); }
.fd-badge.us {
  font-size: 0.54rem; font-weight: 700; padding: 1px 4px; border-radius: 3px;
  background: rgba(64, 192, 87, 0.2); color: #40c057;
}
.fd-item-name { flex: 1; font-size: 0.82rem; overflow: hidden; text-overflow: ellipsis; }
.fd-empty { font-size: 0.78rem; color: var(--color-text-light); font-style: italic; padding: 6px 0; }
.fd-speclist { margin: 0; padding-left: 18px; font-size: 0.8rem; color: var(--color-text); }
.fd-speclist li { margin: 2px 0; }
</style>
