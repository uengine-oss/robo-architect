<script setup>
import { computed } from 'vue'

const props = defineProps({
  userStory: { type: Object, default: null },
})

const kindLabel = { given: 'Given', when: 'When', then: 'Then' }

const hasStory = computed(() => !!props.userStory)
const criteria = computed(() => props.userStory?.acceptanceCriteria || [])
</script>

<template>
  <div class="us-detail">
    <div v-if="!hasStory" class="us-detail__empty">
      왼쪽 트리에서 User Story를 선택하세요.
    </div>
    <template v-else>
      <div class="us-detail__statement">
        <span class="frag frag--role">As a {{ userStory.role || '사용자' }}</span>
        <span class="frag frag--action">I want {{ userStory.action }}</span>
        <span v-if="userStory.benefit" class="frag frag--benefit">so that {{ userStory.benefit }}</span>
      </div>

      <div class="us-detail__meta">
        <span class="badge">우선순위: {{ userStory.priority || 'medium' }}</span>
        <span class="badge">상태: {{ userStory.status || 'draft' }}</span>
        <span v-if="userStory.commandName" class="badge badge--cmd">
          Command: {{ userStory.commandName }}
        </span>
      </div>

      <div class="us-detail__criteria">
        <h4>인수조건 (Acceptance Criteria)</h4>
        <p v-if="!criteria.length" class="us-detail__no-criteria">
          {{ userStory.commandId ? '인수조건 없음' : '연결된 Command가 없어 인수조건을 표시할 수 없습니다.' }}
        </p>
        <ul v-else>
          <li v-for="(c, i) in criteria" :key="i">
            <span class="gwt-kind" :class="`gwt-kind--${c.kind}`">{{ kindLabel[c.kind] }}</span>
            <span class="gwt-name">{{ c.name }}</span>
            <span v-if="c.description" class="gwt-desc">— {{ c.description }}</span>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<style scoped>
.us-detail { padding: 16px; overflow-y: auto; }
.us-detail__empty { color: var(--color-text-light); font-size: 0.85rem; padding: 24px 0; }
.us-detail__statement {
  display: flex; flex-direction: column; gap: 4px;
  padding: 14px; border-radius: 8px; background: var(--color-bg-tertiary);
}
.frag { font-size: 0.95rem; }
.frag--role { color: var(--color-text-light); }
.frag--action { font-weight: 700; color: var(--color-text); font-size: 1.05rem; }
.frag--benefit { color: var(--color-text-light); font-style: italic; }
.us-detail__meta { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
.badge {
  font-size: 0.68rem; padding: 2px 8px; border-radius: 10px;
  background: var(--color-bg-tertiary); color: var(--color-text-light);
}
.badge--cmd { background: rgba(92, 124, 250, 0.15); color: #5c7cfa; }
.us-detail__criteria h4 { font-size: 0.8rem; margin: 8px 0; color: var(--color-text); }
.us-detail__no-criteria { font-size: 0.8rem; color: var(--color-text-light); }
.us-detail__criteria ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.us-detail__criteria li {
  font-size: 0.82rem; padding: 8px 10px; border-radius: 6px;
  background: var(--color-bg-tertiary); display: flex; gap: 6px; flex-wrap: wrap;
}
.gwt-kind {
  font-weight: 700; font-size: 0.66rem; padding: 1px 6px; border-radius: 4px;
  text-transform: uppercase;
}
.gwt-kind--given { background: rgba(64, 192, 87, 0.2); color: #40c057; }
.gwt-kind--when { background: rgba(253, 126, 20, 0.2); color: #fd7e14; }
.gwt-kind--then { background: rgba(92, 124, 250, 0.2); color: #5c7cfa; }
.gwt-name { font-weight: 600; color: var(--color-text); }
.gwt-desc { color: var(--color-text-light); }
</style>
