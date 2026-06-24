<template>
  <div class="intent-view">
    <!-- Strategic Diff -->
    <section class="diff-section">
      <h4 class="diff-section__title">{{ t('proposals.term.strategicDesign') }} <span class="badge badge--blue">{{ t('proposals.intent.strategicBadge') }}</span></h4>
      <div v-if="!hasSd" class="diff-section__empty">{{ t('proposals.intent.noStrategic') }}</div>
      <div v-else>
        <!-- 프로세스 — Event Storming 식 이벤트 흐름을 먼저 보여준다 -->
        <div v-if="sd.processes?.length" class="diff-group">
          <h5>{{ t('proposals.term.process') }}</h5>
          <div v-for="pc in sd.processes" :key="keyOf(pc)" class="diff-entry diff-entry--process">
            <div class="entry-header">
              <span class="entry-title">{{ pc.entityTitle }}</span>
              <span :class="opClass(pc.op)">{{ pc.op }}</span>
            </div>
            <!-- 설명: 레이블 없이 이벤트 흐름 위에 본문으로 -->
            <p v-if="descOf(pc)" class="entry-desc">{{ descOf(pc) }}</p>
            <!-- Events: 각 이벤트를 오렌지 칩으로(→ 흐름) -->
            <div v-if="eventsOf(pc).length" class="event-flow">
              <template v-for="(ev, i) in eventsOf(pc)" :key="i">
                <span class="event-chip">{{ ev }}</span>
                <span v-if="i < eventsOf(pc).length - 1" class="event-arrow">→</span>
              </template>
            </div>
            <!-- steps/events/description 외 다른 필드는 폴백 렌더 -->
            <div v-for="[k, v] in otherProcessFields(pc)" :key="k" class="diff-entry__field">
              <span class="field-key">{{ k }}:</span>
              <span class="field-before">{{ v?.before ?? '—' }}</span>
              <span class="arrow">→</span>
              <span class="field-after">{{ v?.after ?? '—' }}</span>
            </div>
          </div>
        </div>

        <!-- BoundedContext → Feature → UserStory 계층 트리 (collapse 가능, 기본 열림) -->
        <div v-if="tree.epicNodes.length" class="diff-group">
          <h5>{{ t('proposals.term.boundedContext') }}</h5>
          <div v-for="ep in tree.epicNodes" :key="keyOf(ep.node)" class="bc-block">
            <div class="diff-entry diff-entry--bc">
              <div
                class="entry-header"
                :class="{ 'entry-header--clickable': hasChildren(ep) }"
                @click="hasChildren(ep) && toggle(keyOf(ep.node))"
              >
                <span v-if="hasChildren(ep)" class="caret" :class="{ 'caret--open': isOpen(keyOf(ep.node)) }">▶</span>
                <span class="entry-title entry-title--bc">{{ ep.node.entityTitle }}</span>
                <span v-if="classLabel(ep.node)" class="class-chip" :class="classChip(ep.node)">{{ classLabel(ep.node) }}</span>
                <span :class="opClass(ep.node.op)">{{ ep.node.op }}</span>
              </div>
              <p v-if="descOf(ep.node)" class="entry-desc">{{ descOf(ep.node) }}</p>
              <div v-for="[k, v] in otherFields(ep.node)" :key="k" class="diff-entry__field">
                <span class="field-key">{{ k }}:</span>
                <span class="field-before">{{ v?.before ?? '—' }}</span>
                <span class="arrow">→</span>
                <span class="field-after">{{ v?.after ?? '—' }}</span>
              </div>
            </div>
            <div v-if="hasChildren(ep) && isOpen(keyOf(ep.node))" class="children">
              <div v-for="ft in ep.features" :key="keyOf(ft.node)" class="feature-block">
                <FeatureNode :feature="ft" :op-class="opClass" :is-open="isOpen" :toggle="toggle" :key-of="keyOf" />
              </div>
              <!-- BC 직속(매칭되는 Feature 없는) UserStory -->
              <div v-for="us in ep.looseUserStories" :key="keyOf(us)" class="diff-entry diff-entry--us">
                <StrategicEntry :entry="us" :op-class="opClass" :type-label="t('proposals.term.userStory')" />
              </div>
            </div>
          </div>
        </div>

        <!-- 부모 BC 를 못 찾은 Feature(고아) -->
        <div v-if="tree.orphanFeatures.length" class="diff-group">
          <h5>{{ t('proposals.term.feature') }}</h5>
          <div v-for="ft in tree.orphanFeatures" :key="keyOf(ft.node)" class="feature-block">
            <FeatureNode :feature="ft" :op-class="opClass" :is-open="isOpen" :toggle="toggle" :key-of="keyOf" />
          </div>
        </div>

        <!-- 부모 Feature/BC 를 못 찾은 UserStory(고아) -->
        <div v-if="tree.orphanUserStories.length" class="diff-group">
          <h5>{{ t('proposals.term.userStory') }}</h5>
          <div v-for="us in tree.orphanUserStories" :key="keyOf(us)" class="diff-entry diff-entry--us">
            <StrategicEntry :entry="us" :op-class="opClass" :type-label="t('proposals.term.userStory')" />
          </div>
        </div>

        <!-- 미지의 전략 카테고리(프로젝트별 맞춤 키)를 제네릭하게 렌더 -->
        <div v-for="grp in extraGroups" :key="grp.key" class="diff-group">
          <h5>{{ grp.label }}</h5>
          <div v-for="(en, i) in grp.entries" :key="keyOf(en) || i" class="diff-entry">
            <StrategicEntry :entry="en" :op-class="opClass" />
          </div>
        </div>
      </div>
    </section>
    <!-- 041 — Intent 단계는 Strategic Diff 만 렌더한다(FR-006).
         Tactical Diff/아키텍처는 Plan 단계(PlanView)로 이동했다. -->
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import StrategicEntry from './StrategicEntry.vue'
import FeatureNode from './FeatureNode.vue'
import { useI18n } from '../../../app/i18n'

const { t } = useI18n()

const props = defineProps({
  strategicDiff: { type: Object, default: null },
  // 040 — preview 진입점 등에서 참조될 수 있어 유지(현재 Strategic 렌더에는 미사용).
  proposalId: { type: String, default: null },
})

// 1급(고착) 전략 카테고리 키. 나머지 배열 키는 제네릭 폴백으로 렌더한다.
const FIRST_CLASS_KEYS = ['version', 'epics', 'features', 'userStories', 'processes']

const sd = computed(() => props.strategicDiff || {})

// 항목의 안정 키 — MODIFY 는 실제 entityId, CREATE 는 tempId, 없으면 제목.
function keyOf(entry) {
  return entry?.entityId || entry?.tempId || entry?.entityTitle
}

// Collapse 상태 — 닫힌 키만 보관(기본은 모두 열림).
const collapsed = ref(new Set())
function isOpen(key) {
  return !collapsed.value.has(key)
}
function toggle(key) {
  const next = new Set(collapsed.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsed.value = next
}
function hasChildren(ep) {
  return ep.features.length > 0 || ep.looseUserStories.length > 0
}

// fields 에서 단일 값(after 우선, 없으면 before) 추출.
function fieldVal(entry, key) {
  const f = entry?.fields?.[key]
  if (!f) return null
  return f.after ?? f.before ?? null
}
function descOf(entry) {
  return fieldVal(entry, 'description')
}
// classification → 칩 라벨/스타일. classification·description 외 필드는 폴백 렌더.
function classLabel(entry) {
  const v = fieldVal(entry, 'classification')
  if (!v) return ''
  return String(v).charAt(0).toUpperCase() + String(v).slice(1)
}
function classChip(entry) {
  const k = String(fieldVal(entry, 'classification') || '').toLowerCase()
  if (k === 'core') return 'class-chip--core'
  if (k === 'supporting') return 'class-chip--supporting'
  return 'class-chip--generic'
}
function otherFields(entry) {
  const f = entry?.fields
  if (!f) return []
  return Object.entries(f).filter(([k]) => k !== 'classification' && k !== 'description')
}

// 프로세스의 steps/events 문자열 → 화살표 기준 개별 이벤트 배열.
function eventsOf(entry) {
  const raw = fieldVal(entry, 'steps') || fieldVal(entry, 'events')
  if (!raw) return []
  return String(raw)
    .split(/→|->|=>/)
    .map((s) => s.trim())
    .filter(Boolean)
}
// 프로세스에서 events/steps/description 외 나머지 필드(폴백 렌더용).
function otherProcessFields(entry) {
  const f = entry?.fields
  if (!f) return []
  return Object.entries(f).filter(([k]) => !['steps', 'events', 'description'].includes(k))
}

// 부모 참조(ref)가 entry 의 실제 id(MODIFY) 또는 tempId(CREATE) 중 하나와 일치하는가.
function matchesRef(entry, ref) {
  return ref != null && (entry.entityId === ref || entry.tempId === ref)
}

// 평탄한 epics/features/userStories 를 BC → Feature → UserStory 계층으로 조립.
// 부모를 못 찾은 항목은 고아(orphan)로 분리해 끝에 따로 렌더한다.
const tree = computed(() => {
  const epics = sd.value.epics || []
  const features = sd.value.features || []
  const userStories = sd.value.userStories || []

  const usedFeature = new Set()
  const usedUs = new Set()

  // 아직 소비되지 않은 UserStory 중 parent[refField] 가 일치하는 것들을 수집.
  function storiesFor(parent, refField) {
    const out = []
    userStories.forEach((us, ui) => {
      if (!usedUs.has(ui) && matchesRef(parent, us[refField])) {
        out.push(us)
        usedUs.add(ui)
      }
    })
    return out
  }

  const epicNodes = epics.map((e) => {
    const featureNodes = []
    features.forEach((f, fi) => {
      if (matchesRef(e, f.epicId)) {
        usedFeature.add(fi)
        featureNodes.push({ node: f, userStories: storiesFor(f, 'featureId') })
      }
    })
    // Feature 에 안 붙은 BC 직속 UserStory(boundedContextId 직접 참조)
    const looseUserStories = storiesFor(e, 'boundedContextId')
    return { node: e, features: featureNodes, looseUserStories }
  })

  const orphanFeatures = []
  features.forEach((f, fi) => {
    if (!usedFeature.has(fi)) {
      orphanFeatures.push({ node: f, userStories: storiesFor(f, 'featureId') })
    }
  })

  const orphanUserStories = userStories.filter((_, ui) => !usedUs.has(ui))

  return { epicNodes, orphanFeatures, orphanUserStories }
})

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

function opClass(op) {
  const map = { CREATE: 'op-badge op-badge--create', MODIFY: 'op-badge op-badge--modify', DELETE: 'op-badge op-badge--delete' }
  return map[op] || 'op-badge'
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
/* BC → Feature → US 계층: 왼쪽 들여쓰기 + 가이드 라인으로 소속을 드러낸다 */
.bc-block { margin-bottom: 14px; }
.feature-block { margin-bottom: 6px; }
.children { margin-left: 10px; padding-left: 12px; border-left: 2px solid var(--color-border); margin-top: 6px; }
.diff-entry--bc { background: var(--color-bg-tertiary); border-color: var(--color-border); }
.diff-entry--feature { background: var(--color-bg-secondary); }
.diff-entry--us { background: var(--color-bg-secondary); }
/* 펼침/접힘 헤더 */
.entry-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.entry-header--clickable { cursor: pointer; user-select: none; }
.caret { font-size: 9px; color: var(--color-text-light); display: inline-block; transition: transform 0.15s ease; }
.caret--open { transform: rotate(90deg); }
.entry-title { font-weight: 500; color: var(--color-text); }
.entry-title--bc { font-weight: 600; font-size: 14px; color: var(--color-text-bright); }
/* 설명부 — 레이블 없이 본문으로 더 잘 보이게 */
.entry-desc { margin: 7px 0 0; color: var(--color-text); font-size: 12.5px; line-height: 1.55; }
/* classification 칩 */
.class-chip { font-size: 10px; font-weight: 700; padding: 1px 8px; border-radius: 9999px; text-transform: capitalize; letter-spacing: 0.02em; }
.class-chip--core { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.class-chip--supporting { background: var(--status-green-bg); color: var(--status-green-fg); }
.class-chip--generic { background: var(--status-neutral-bg); color: var(--status-neutral-fg); }
/* 프로세스(Event Storming) — 이벤트를 오렌지 칩으로 */
.diff-entry--process { background: var(--color-bg-tertiary); }
.event-flow { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
/* Design 탭 Event 노드와 동일한 컬러(--color-event) 재사용 */
.event-chip { display: inline-block; background: var(--color-event); color: #fff; border: 1px solid var(--color-event-dark); font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 4px; white-space: nowrap; }
.event-arrow { color: var(--color-text-light); font-size: 12px; }
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
