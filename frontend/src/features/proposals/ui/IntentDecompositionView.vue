<template>
  <div class="intent-view">
    <!-- Strategic Diff -->
    <section class="diff-section">
      <h4 class="diff-section__title">Strategic Diff <span class="badge badge--blue">전략적 변경</span></h4>
      <div v-if="!hasSd" class="diff-section__empty">Strategic Diff 없음</div>
      <div v-else>
        <div v-if="sd.epics?.length" class="diff-group">
          <h5>Epic</h5>
          <div v-for="e in sd.epics" :key="e.entityId || e.entityTitle" class="diff-entry">
            <span :class="opClass(e.op)">{{ e.op }}</span>
            <span class="diff-entry__title">{{ e.entityTitle }}</span>
            <template v-if="e.fields">
              <div v-for="(v, k) in e.fields" :key="k" class="diff-entry__field">
                <span class="field-key">{{ k }}:</span>
                <span class="field-before">{{ v?.before ?? '—' }}</span>
                <span class="arrow">→</span>
                <span class="field-after">{{ v?.after ?? '—' }}</span>
              </div>
            </template>
          </div>
        </div>
        <div v-if="sd.features?.length" class="diff-group">
          <h5>Feature</h5>
          <div v-for="f in sd.features" :key="f.entityId || f.entityTitle" class="diff-entry">
            <span :class="opClass(f.op)">{{ f.op }}</span>
            <span class="diff-entry__title">{{ f.entityTitle }}</span>
          </div>
        </div>
        <div v-if="sd.userStories?.length" class="diff-group">
          <h5>User Story</h5>
          <div v-for="us in sd.userStories" :key="us.entityId || us.entityTitle" class="diff-entry">
            <span :class="opClass(us.op)">{{ us.op }}</span>
            <span class="diff-entry__title">{{ us.entityTitle }}</span>
            <template v-if="us.acceptanceCriteria?.length">
              <ul class="ac-list">
                <li v-for="(ac, i) in us.acceptanceCriteria" :key="i">{{ ac }}</li>
              </ul>
            </template>
            <template v-if="us.fields">
              <div v-for="(v, k) in us.fields" :key="k" class="diff-entry__field">
                <span class="field-key">{{ k }}:</span>
                <span class="field-before">{{ v?.before ?? '—' }}</span>
                <span class="arrow">→</span>
                <span class="field-after">{{ v?.after ?? '—' }}</span>
              </div>
            </template>
          </div>
        </div>
        <div v-if="sd.processes?.length" class="diff-group">
          <h5>Process</h5>
          <div v-for="pc in sd.processes" :key="pc.entityId || pc.entityTitle" class="diff-entry">
            <StrategicEntry :entry="pc" :op-class="opClass" />
          </div>
        </div>
        <!-- 미지의 전략 카테고리(프로젝트별 맞춤 키)를 제네릭하게 렌더 -->
        <div v-for="grp in extraGroups" :key="grp.key" class="diff-group">
          <h5>{{ grp.label }}</h5>
          <div v-for="(en, i) in grp.entries" :key="en.entityId || en.entityTitle || i" class="diff-entry">
            <StrategicEntry :entry="en" :op-class="opClass" />
          </div>
        </div>
      </div>
    </section>

    <!-- Tactical Diff -->
    <section class="diff-section">
      <h4 class="diff-section__title">Tactical Diff <span class="badge badge--orange">전술적 변경</span></h4>
      <div v-if="!hasTd" class="diff-section__empty">Tactical Diff 없음</div>
      <div v-else>
        <div v-for="item in td" :key="item.nodeId || item.nodeTitle" class="diff-entry diff-entry--tactical">
          <div class="diff-entry__header">
            <span :class="opClass(item.changeType)">{{ item.changeType }}</span>
            <span class="diff-entry__label">{{ item.nodeLabel }}</span>
            <span class="diff-entry__title">{{ item.nodeTitle }}</span>
            <span :class="['impact-badge', `impact-badge--${(item.impactLevel || 'LOW').toLowerCase()}`]">
              {{ item.impactLevel }}
            </span>
            <OpenInViewerLink
              v-if="proposalId"
              :proposalId="proposalId"
              :nodeId="item.nodeId"
              :nodeLabel="item.nodeLabel"
              :nodeTitle="item.nodeTitle"
            />
          </div>
          <div v-if="item.semanticDiff?.ops?.length" class="semantic-ops">
            <div v-for="(op, oi) in item.semanticDiff.ops" :key="oi" class="semantic-op">
              <code>{{ op.field }}</code>
              <span class="op-type">{{ op.op }}</span>
              <span class="op-value">{{ opValue(op) }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StrategicEntry from './StrategicEntry.vue'
import OpenInViewerLink from './OpenInViewerLink.vue'

const props = defineProps({
  strategicDiff: { type: Object, default: null },
  tacticalDiff: { type: Array, default: null },
  // 040 — 있으면 Tactical 엔트리마다 '열기'(미리보기 뷰어) 진입점을 표시.
  proposalId: { type: String, default: null },
})

// 1급(고착) 전략 카테고리 키. 나머지 배열 키는 제네릭 폴백으로 렌더한다.
const FIRST_CLASS_KEYS = ['version', 'epics', 'features', 'userStories', 'processes']

const sd = computed(() => props.strategicDiff || {})
const td = computed(() => props.tacticalDiff || [])

// camelCase/snake_case 키 → 보기 좋은 제목 ("businessRules" → "Business Rules")
function prettyLabel(key) {
  return String(key)
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// 프로젝트별 맞춤 스킬이 추가한 미지의 전략 카테고리(1급 외 배열 키)
const extraGroups = computed(() => {
  const out = []
  for (const [key, value] of Object.entries(sd.value)) {
    if (FIRST_CLASS_KEYS.includes(key)) continue
    if (Array.isArray(value) && value.length) {
      out.push({ key, label: prettyLabel(key), entries: value })
    }
  }
  return out
})

const hasSd = computed(() =>
  sd.value.epics?.length ||
  sd.value.features?.length ||
  sd.value.userStories?.length ||
  sd.value.processes?.length ||
  extraGroups.value.length
)
const hasTd = computed(() => td.value.length > 0)

function opClass(op) {
  const map = { CREATE: 'op-badge op-badge--create', MODIFY: 'op-badge op-badge--modify', DELETE: 'op-badge op-badge--delete' }
  return map[op] || 'op-badge'
}

function opValue(op) {
  if (op.value != null) return JSON.stringify(op.value)
  if (op.obj_data) return JSON.stringify(op.obj_data)
  if (op.items) return JSON.stringify(op.items)
  return ''
}
</script>

<style scoped>
.intent-view { font-size: 13px; }
.diff-section { margin-bottom: 20px; }
.diff-section__title { font-size: 14px; font-weight: 600; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; color: var(--color-text-bright); }
.diff-section__empty { color: var(--color-text-light); font-style: italic; }
.badge { font-size: 11px; padding: 2px 6px; border-radius: 9999px; }
.badge--blue { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.badge--orange { background: var(--status-orange-bg); color: var(--status-orange-fg); }
.diff-group { margin-bottom: 12px; }
.diff-group h5 { font-size: 12px; font-weight: 600; color: var(--color-text-light); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
.diff-entry { background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; }
.diff-entry__header { display: flex; align-items: center; gap: 6px; }
.diff-entry--tactical .diff-entry__header { flex-wrap: wrap; }
.diff-entry__label { font-size: 11px; color: var(--color-text-light); background: var(--color-bg-tertiary); padding: 1px 5px; border-radius: 3px; }
.diff-entry__title { font-weight: 500; color: var(--color-text); }
.diff-entry__field { font-size: 12px; color: var(--color-text-light); margin-top: 4px; display: flex; gap: 6px; align-items: center; }
.field-key { font-weight: 600; color: var(--color-text); }
.field-before { color: var(--color-danger); text-decoration: line-through; }
.arrow { color: var(--color-text-light); }
.field-after { color: var(--color-success); }
.op-badge { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; text-transform: uppercase; }
.op-badge--create { background: var(--status-green-bg); color: var(--status-green-fg); }
.op-badge--modify { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.op-badge--delete { background: var(--status-red-bg); color: var(--status-red-fg); }
.impact-badge { font-size: 10px; font-weight: 600; padding: 1px 5px; border-radius: 3px; margin-left: auto; }
.impact-badge--high { background: var(--status-red-bg); color: var(--status-red-fg); }
.impact-badge--medium { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.impact-badge--low { background: var(--status-green-bg); color: var(--status-green-fg); }
.impact-badge--none { background: var(--status-neutral-bg); color: var(--status-neutral-fg); }
.ac-list { margin: 4px 0 0 16px; padding: 0; font-size: 12px; color: var(--color-text); }
.ac-list li { margin-bottom: 2px; }
.semantic-ops { margin-top: 6px; }
.semantic-op { display: flex; gap: 8px; font-size: 12px; align-items: baseline; margin-bottom: 3px; }
.semantic-op code { background: var(--color-bg-tertiary); padding: 1px 4px; border-radius: 3px; }
.op-type { color: var(--color-policy); font-style: italic; }
.op-value { color: var(--color-text); }
</style>
