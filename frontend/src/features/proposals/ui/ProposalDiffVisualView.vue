<script setup>
// 038 Change Management의 DesignChangesView(레이어별 구조화 diff) 시각화를 Proposal로 포팅.
// 입력은 이미 계산된 strategicDiff + tacticalDiff. SSE 없이 정적 렌더링한다.
import { computed, ref } from 'vue'

const props = defineProps({
  strategicDiff: { type: Object, default: () => ({}) },
  tacticalDiff:  { type: Array,  default: () => [] },
  journeys:      { type: Array,  default: () => [] },
})

// ── Layer 정의 (038 동일 구조 + Epic/Process 확장) ───────────────────────
const LAYERS = [
  { key:'req',    label:'Requirements', sublabel:'Epics · Features · Stories',       icon:'📋', color:'#228be6', labels:['Epic','Feature','UserStory'] },
  { key:'proc',   label:'Process',      sublabel:'Processes · Bounded Contexts',      icon:'🏛', color:'#ae3ec9', labels:['Process','BoundedContext'] },
  { key:'design', label:'Design',       sublabel:'Aggregates · Commands · Events',    icon:'📐', color:'#f59f00', labels:['Aggregate','Command','Event','Policy','ReadModel','ValueObject'] },
]
const IMPACT_COLORS = { HIGH:'#fa5252', MEDIUM:'#fd7e14', LOW:'#228be6' }
const LABEL_ICONS   = { Epic:'🗂', UserStory:'👤', Feature:'✨', Process:'🔀', BoundedContext:'🏛', Aggregate:'📦', Command:'⚡', Event:'🔔', Policy:'📜', ReadModel:'🔍' }
const CHANGE_TYPE_COLORS = { CREATE:'#40c057', MODIFY:'#fd7e14', DELETE:'#fa5252' }
const CHANGE_TYPE_LABELS = { CREATE:'신규', MODIFY:'수정', DELETE:'삭제' }

const expandedId = ref(null)

// ── 라벨 추론 ────────────────────────────────────────────────────────────
function pascal(s) { return s ? s[0].toUpperCase() + s.slice(1) : s }
function labelForCategory(entry, key) {
  if (entry.entityType) return pascal(entry.entityType)
  const map = { userStories:'UserStory', features:'Feature', epics:'Epic', processes:'Process' }
  if (map[key]) return map[key]
  let base = key
  if (base.endsWith('ies')) base = base.slice(0, -3) + 'y'
  else if (base.endsWith('s')) base = base.slice(0, -1)
  return pascal(base)
}

function parseRoleAction(title) {
  if (title && title.includes(':')) {
    const [head, ...rest] = title.split(':')
    return { role: head.trim(), action: rest.join(':').trim() }
  }
  return { role: '', action: title || '' }
}

// ── TacticalDiff ops → 구조화 표시 ──────────────────────────────────────
function opsToStructured(ops) {
  const scalarChanges = []
  const valueObjectChanges = []
  const enumChanges = []
  const invariantChanges = []
  for (const op of (ops || [])) {
    const type = (op.op || '').replace('scalar_set', 'set')
    if (type === 'set' || type === 'replace') {
      scalarChanges.push({ field: op.field, after: op.value ?? op.to_val })
    } else if (type === 'obj_append') {
      const data = op.obj_data || op.items || {}
      if (op.field === 'enumerations') {
        enumChanges.push({ enumName: data.name || op.obj_name, addedItems: data.items || [] })
      } else {
        valueObjectChanges.push({
          type: 'ADDED', name: data.name || op.obj_name, field: op.field,
          dataType: data.type, fields: data.fields || (data.type ? [{ name: data.name, type: data.type }] : []),
        })
      }
    } else if (type === 'obj_remove') {
      valueObjectChanges.push({ type: 'REMOVED', name: op.obj_name, field: op.field, fields: [] })
    } else if (type === 'enum_add_items') {
      enumChanges.push({ enumName: op.enum_name, addedItems: op.items || [] })
    } else if (type === 'enum_remove_items') {
      enumChanges.push({ enumName: op.enum_name, removedItems: op.items || [] })
    } else if (type === 'list_append') {
      invariantChanges.push(...(op.items || (op.value ? [op.value] : [])))
    }
  }
  return { scalarChanges, valueObjectChanges, enumChanges, invariantChanges }
}

// ── strategic + tactical → 통합 노드 목록 ───────────────────────────────
const nodes = computed(() => {
  const out = []
  const sd = props.strategicDiff || {}
  for (const [key, entries] of Object.entries(sd)) {
    if (key === 'version' || !Array.isArray(entries)) continue
    for (const e of entries) {
      const label = labelForCategory(e, key)
      const title = e.entityTitle || e.storyTitle || e.featureTitle || ''
      const node = {
        nodeId: e.entityId || `${label}:${title}`,
        nodeLabel: label,
        nodeTitle: title,
        changeType: (e.op || 'MODIFY').toUpperCase(),
        impactLevel: e.impactLevel || 'MEDIUM',
        acceptanceCriteria: e.acceptanceCriteria || [],
      }
      if (label === 'UserStory') {
        const { role, action } = parseRoleAction(title)
        node.role = e.role || role
        node.action = e.action || action
        node.benefit = e.benefit || ''
      }
      // MODIFY 필드 변경 표시
      if (e.fields) {
        node.scalarChanges = Object.entries(e.fields).map(([f, v]) => ({
          field: f, after: (v && typeof v === 'object') ? (v.after ?? v.value) : v,
        }))
      }
      out.push(node)
    }
  }
  for (const item of (props.tacticalDiff || [])) {
    const ops = item.semanticDiff?.ops || []
    const struct = opsToStructured(ops)
    // fields(actor/category/inputSchema/version/payload) → 스칼라 필드로 합류
    const fieldChanges = Object.entries(item.fields || {}).map(([f, v]) => ({
      field: f, after: (v && typeof v === 'object') ? (v.after ?? v.value) : v,
    }))
    out.push({
      nodeId: item.nodeId || `${item.nodeLabel}:${item.nodeTitle}`,
      nodeLabel: item.nodeLabel || 'Aggregate',
      nodeTitle: item.nodeTitle || '',
      changeType: (item.changeType || 'MODIFY').toUpperCase(),
      impactLevel: item.impactLevel || 'MEDIUM',
      ...struct,
      scalarChanges: [...(struct.scalarChanges || []), ...fieldChanges],
      properties: Array.isArray(item.properties) ? item.properties : [],
      gwt: Array.isArray(item.gwt) ? item.gwt : [],
      userStoryRefs: item.userStoryRefs || item.userStoryIds || [],
      invariantObjects: Array.isArray(item.invariants) ? item.invariants : [],
      ui: item.ui || null,
      policyLinks: (item.triggerEventId || item.invokeCommandId)
        ? { trigger: item.triggerEventId, invoke: item.invokeCommandId } : null,
    })
  }
  return out
})

const layeredNodes = computed(() => {
  const m = {}
  const order = { HIGH:0, MEDIUM:1, LOW:2 }
  for (const l of LAYERS) {
    m[l.key] = nodes.value.filter(n => l.labels.includes(n.nodeLabel))
      .sort((a, b) => (order[a.impactLevel] ?? 3) - (order[b.impactLevel] ?? 3))
  }
  // 어느 레이어에도 안 들어간 노드는 design에 합류(제네릭)
  const known = new Set(LAYERS.flatMap(l => l.labels))
  m.design = [...m.design, ...nodes.value.filter(n => !known.has(n.nodeLabel))]
  return m
})
const activeLayers = computed(() => LAYERS.filter(l => layeredNodes.value[l.key]?.length))
const hasDetail = (n) =>
  n.role || n.acceptanceCriteria?.length || n.scalarChanges?.length ||
  n.valueObjectChanges?.length || n.enumChanges?.length || n.invariantChanges?.length ||
  n.properties?.length || n.gwt?.length || n.userStoryRefs?.length ||
  n.invariantObjects?.length || n.ui

// ── Journeys (사용자 화면 흐름) ──────────────────────────────────────────
const journeyList = computed(() =>
  (props.journeys || []).filter(j => j && (j.name || j.title)))
function stepLabel(st) { return st.name || st.title || st.ref || 'step' }
</script>

<template>
  <div class="pdv-root">
    <div v-if="!activeLayers.length" class="pdv-empty">아직 분해된 변경(diff)이 없습니다.</div>

    <div v-else class="pdv-tree">
      <template v-for="(layer, li) in activeLayers" :key="layer.key">
        <div v-if="li > 0" class="pdv-arrow">
          <div class="pdv-arrow__line" /><div class="pdv-arrow__head" />
        </div>

        <div class="pdv-layer" :style="{'--lc': layer.color}">
          <div class="pdv-layer__head">
            <span>{{ layer.icon }}</span>
            <div class="pdv-layer__meta">
              <span class="pdv-layer__name">{{ layer.label }}</span>
              <span class="pdv-layer__sub">{{ layer.sublabel }}</span>
            </div>
            <span class="pdv-layer__badge">{{ layeredNodes[layer.key].length }}</span>
          </div>

          <div class="pdv-nodes">
            <div v-for="node in layeredNodes[layer.key]" :key="node.nodeId"
                 class="pdv-node" :style="{'--ic': IMPACT_COLORS[node.impactLevel]}">
              <div class="pdv-node__row">
                <span class="pdv-node__type-icon">{{ LABEL_ICONS[node.nodeLabel] || '🔷' }}</span>
                <div class="pdv-node__info">
                  <span class="pdv-node__title">{{ node.nodeTitle || node.nodeId }}</span>
                  <span class="pdv-node__sub">{{ node.nodeLabel }}</span>
                </div>
                <span class="pdv-ct-badge" :style="{'--ct': CHANGE_TYPE_COLORS[node.changeType]}">
                  {{ CHANGE_TYPE_LABELS[node.changeType] || node.changeType }}
                </span>
                <span class="pdv-impact-badge">{{ node.impactLevel }}</span>
                <button v-if="hasDetail(node)" class="pdv-expand-btn"
                        @click="expandedId = expandedId === node.nodeId ? null : node.nodeId">
                  {{ expandedId === node.nodeId ? '▲' : '▼' }}
                </button>
              </div>

              <div v-if="expandedId === node.nodeId" class="pdv-detail">
                <!-- UserStory: role/action/benefit -->
                <div v-if="node.role || node.action || node.benefit" class="pdv-summary">
                  <div v-if="node.role" class="pdv-row"><span class="pdv-label">As a</span>{{ node.role }}</div>
                  <div v-if="node.action" class="pdv-row"><span class="pdv-label">I want to</span>{{ node.action }}</div>
                  <div v-if="node.benefit" class="pdv-row"><span class="pdv-label">So that</span>{{ node.benefit }}</div>
                </div>

                <!-- Acceptance Criteria -->
                <div v-if="node.acceptanceCriteria?.length" class="pdv-section">
                  <div class="pdv-section__title">✅ Acceptance Criteria</div>
                  <ul class="pdv-ac-list"><li v-for="(ac, i) in node.acceptanceCriteria" :key="i">{{ ac }}</li></ul>
                </div>

                <!-- 스칼라 필드 변경 -->
                <div v-if="node.scalarChanges?.length" class="pdv-section">
                  <div class="pdv-section__title">📋 필드</div>
                  <div v-for="(sc, i) in node.scalarChanges" :key="i" class="pdv-row">
                    <span class="pdv-mono">{{ sc.field }}</span>
                    <span class="pdv-after">{{ sc.after }}</span>
                  </div>
                </div>

                <!-- Value Object / Properties -->
                <div v-if="node.valueObjectChanges?.length" class="pdv-section">
                  <div class="pdv-section__title">🧩 Value Object · Properties</div>
                  <div v-for="(vc, i) in node.valueObjectChanges" :key="i" class="pdv-vo-card"
                       :style="{'--ct': CHANGE_TYPE_COLORS[vc.type === 'ADDED' ? 'CREATE' : 'DELETE']}">
                    <div class="pdv-vo-head">
                      <span class="pdv-ct-badge" :style="{'--ct': CHANGE_TYPE_COLORS[vc.type === 'ADDED' ? 'CREATE' : 'DELETE']}">
                        {{ vc.type === 'ADDED' ? '＋추가' : '－삭제' }}
                      </span>
                      <span class="pdv-mono">{{ vc.name }}</span>
                      <span v-if="vc.dataType" class="pdv-type">: {{ vc.dataType }}</span>
                    </div>
                    <div v-if="vc.fields?.length" class="pdv-vo-fields">
                      <span v-for="f in vc.fields" :key="f.name" class="pdv-vo-field">{{ f.name }}: <em>{{ f.type }}</em></span>
                    </div>
                  </div>
                </div>

                <!-- Enumeration -->
                <div v-if="node.enumChanges?.length" class="pdv-section">
                  <div class="pdv-section__title">🔢 Enumeration</div>
                  <div v-for="(ec, i) in node.enumChanges" :key="i" class="pdv-enum-row">
                    <span class="pdv-mono">{{ ec.enumName }}</span>
                    <span v-for="it in (ec.addedItems||[])" :key="it" class="pdv-enum-added">＋{{ it }}</span>
                    <span v-for="it in (ec.removedItems||[])" :key="it" class="pdv-enum-removed">－{{ it }}</span>
                  </div>
                </div>

                <!-- Invariants (ops 기반) -->
                <div v-if="node.invariantChanges?.length" class="pdv-section">
                  <div class="pdv-section__title">📏 불변식</div>
                  <ul class="pdv-inv-list"><li v-for="(inv, i) in node.invariantChanges" :key="i">{{ inv }}</li></ul>
                </div>

                <!-- Properties (HAS_PROPERTY) -->
                <div v-if="node.properties?.length" class="pdv-section">
                  <div class="pdv-section__title">🏷 속성 (Properties)</div>
                  <div class="pdv-prop-grid">
                    <div v-for="(p, i) in node.properties" :key="i" class="pdv-prop">
                      <span class="pdv-mono">{{ p.name }}</span>
                      <span class="pdv-type">: {{ p.type || 'String' }}</span>
                      <span v-if="p.isKey" class="pdv-tag pdv-tag--pk">PK</span>
                      <span v-if="p.isForeignKey" class="pdv-tag pdv-tag--fk">FK</span>
                      <span v-if="p.isRequired" class="pdv-tag pdv-tag--req">필수</span>
                    </div>
                  </div>
                </div>

                <!-- GWT (Given/When/Then) -->
                <div v-if="node.gwt?.length" class="pdv-section">
                  <div class="pdv-section__title">🧪 인수 시나리오 (GWT)</div>
                  <div v-for="(sc, i) in node.gwt" :key="i" class="pdv-gwt-card">
                    <div v-if="sc.scenario || sc.scenarioDescription" class="pdv-gwt-scenario">
                      {{ sc.scenario || sc.scenarioDescription }}
                    </div>
                    <div v-if="sc.given" class="pdv-gwt-row"><span class="pdv-gwt-k pdv-gwt-k--g">GIVEN</span>{{ sc.given.name || sc.given.description }}</div>
                    <div v-if="sc.when"  class="pdv-gwt-row"><span class="pdv-gwt-k pdv-gwt-k--w">WHEN</span>{{ sc.when.name || sc.when.description }}</div>
                    <div v-if="sc.then"  class="pdv-gwt-row"><span class="pdv-gwt-k pdv-gwt-k--t">THEN</span>{{ sc.then.name || sc.then.description }}</div>
                  </div>
                </div>

                <!-- Invariants (구조화 객체: 선언 + 검증 Command) -->
                <div v-if="node.invariantObjects?.length" class="pdv-section">
                  <div class="pdv-section__title">📏 불변식</div>
                  <div v-for="(inv, i) in node.invariantObjects" :key="i" class="pdv-row">
                    <span class="pdv-bullet">•</span>{{ inv.declaration }}
                    <span v-if="(inv.verifyingCommandRefs||[]).length" class="pdv-verify">↪ {{ (inv.verifyingCommandRefs||[]).join(', ') }}</span>
                  </div>
                </div>

                <!-- UI 화면 -->
                <div v-if="node.ui" class="pdv-section">
                  <div class="pdv-section__title">🖥 화면 (UI)</div>
                  <div class="pdv-row"><span class="pdv-mono">{{ node.ui.name || node.ui.title }}</span>
                    <span v-if="node.ui.description" class="pdv-type">— {{ node.ui.description }}</span></div>
                </div>

                <!-- 추적성: 구현 UserStory -->
                <div v-if="node.userStoryRefs?.length" class="pdv-section">
                  <div class="pdv-section__title">🔗 구현 User Story</div>
                  <div class="pdv-chips">
                    <span v-for="(u, i) in node.userStoryRefs" :key="i" class="pdv-chip">{{ u }}</span>
                  </div>
                </div>

                <!-- Policy 연결 -->
                <div v-if="node.policyLinks" class="pdv-section">
                  <div class="pdv-section__title">📜 반응 정책</div>
                  <div class="pdv-row">
                    <span v-if="node.policyLinks.trigger" class="pdv-chip">⟳ {{ node.policyLinks.trigger }}</span>
                    <span v-if="node.policyLinks.invoke" class="pdv-chip">→ {{ node.policyLinks.invoke }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 사용자 여정 (화면 흐름) -->
    <div v-if="journeyList.length" class="pdv-journeys">
      <div class="pdv-journeys__head"><span>🧭</span><span>사용자 여정</span><span class="pdv-layer__badge">{{ journeyList.length }}</span></div>
      <div v-for="(j, ji) in journeyList" :key="ji" class="pdv-journey">
        <div class="pdv-journey__name">{{ j.name || j.title }}</div>
        <div class="pdv-flow">
          <template v-for="(st, si) in (j.steps || [])" :key="si">
            <span v-if="si > 0" class="pdv-flow__arrow">→</span>
            <span class="pdv-flow__step" :class="{ 'pdv-flow__step--gw': st.kind === 'gateway' }">{{ stepLabel(st) }}</span>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pdv-root { display: flex; flex-direction: column; gap: 10px; }
.pdv-empty { padding: 24px; text-align: center; font-size: 0.78rem; color: var(--color-text-light); }
.pdv-tree { display: flex; flex-direction: column; }
.pdv-arrow { display: flex; flex-direction: column; align-items: center; padding: 2px 0; }
.pdv-arrow__line { width: 2px; height: 14px; background: var(--color-border); }
.pdv-arrow__head { width:0; height:0; border-left:5px solid transparent; border-right:5px solid transparent; border-top:7px solid var(--color-border); }

.pdv-layer { border: 1px solid color-mix(in srgb, var(--lc, var(--color-border)) 40%, var(--color-border)); border-radius: 8px; overflow: hidden; }
.pdv-layer__head { display: flex; align-items: center; gap: 8px; padding: 7px 10px; background: color-mix(in srgb, var(--lc, var(--color-accent)) 10%, transparent); border-bottom: 1px solid color-mix(in srgb, var(--lc, var(--color-border)) 25%, transparent); }
.pdv-layer__meta { flex: 1; display: flex; flex-direction: column; gap: 1px; }
.pdv-layer__name { font-size: 0.74rem; font-weight: 700; color: var(--lc, var(--color-text)); }
.pdv-layer__sub  { font-size: 0.6rem; color: var(--color-text-light); }
.pdv-layer__badge { font-size: 0.65rem; font-weight: 700; color: var(--lc); background: color-mix(in srgb, var(--lc) 15%, transparent); padding: 1px 6px; border-radius: 10px; }

.pdv-nodes { display: flex; flex-direction: column; }
.pdv-node { border-bottom: 1px solid var(--color-border); padding: 7px 10px; }
.pdv-node:last-child { border-bottom: none; }
.pdv-node__row { display: flex; align-items: center; gap: 7px; }
.pdv-node__type-icon { font-size: 0.85rem; flex-shrink: 0; }
.pdv-node__info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.pdv-node__title { font-size: 0.74rem; font-weight: 500; color: var(--color-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pdv-node__sub { font-size: 0.6rem; color: var(--color-text-light); }
.pdv-ct-badge { flex-shrink: 0; font-size: 0.58rem; font-weight: 700; color: var(--ct, #888); background: color-mix(in srgb, var(--ct, #888) 12%, transparent); border: 1px solid color-mix(in srgb, var(--ct, #888) 30%, transparent); padding: 1px 5px; border-radius: 3px; white-space: nowrap; }
.pdv-impact-badge { flex-shrink: 0; font-size: 0.58rem; font-weight: 700; color: var(--ic); background: color-mix(in srgb, var(--ic) 12%, transparent); border: 1px solid color-mix(in srgb, var(--ic) 30%, transparent); padding: 1px 5px; border-radius: 3px; }
.pdv-expand-btn { font-size: 0.55rem; color: var(--color-text-light); background: none; border: none; cursor: pointer; flex-shrink: 0; padding: 2px 4px; }

.pdv-detail { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--color-border); display: flex; flex-direction: column; gap: 10px; }
.pdv-summary { background: rgba(64,192,87,.05); border: 1px solid rgba(64,192,87,.2); border-radius: 4px; padding: 8px 10px; display: flex; flex-direction: column; gap: 4px; }
.pdv-row { display: flex; gap: 8px; font-size: 0.68rem; color: var(--color-text); align-items: baseline; }
.pdv-label { flex-shrink: 0; font-weight: 700; color: var(--color-text-light); min-width: 64px; font-size: 0.62rem; }
.pdv-section { display: flex; flex-direction: column; gap: 6px; }
.pdv-section__title { font-size: 0.63rem; font-weight: 700; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.04em; }
.pdv-ac-list, .pdv-inv-list { margin: 0; padding: 0 0 0 16px; font-size: 0.68rem; color: var(--color-text); line-height: 1.6; }
.pdv-mono { font-family: monospace; font-size: 0.68rem; font-weight: 600; color: var(--color-text); }
.pdv-after { color: #40c057; font-size: 0.68rem; }
.pdv-type { color: var(--color-text-light); font-style: italic; font-size: 0.66rem; }
.pdv-vo-card { border: 1px solid color-mix(in srgb, var(--ct, var(--color-border)) 35%, var(--color-border)); border-radius: 4px; padding: 6px 8px; }
.pdv-vo-head { display: flex; align-items: center; gap: 6px; }
.pdv-vo-fields { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.pdv-vo-field { font-size: 0.63rem; background: var(--color-bg-tertiary); border: 1px solid var(--color-border); border-radius: 3px; padding: 1px 5px; color: var(--color-text); }
.pdv-vo-field em { color: var(--color-text-light); font-style: normal; }
.pdv-enum-row { display: flex; align-items: center; gap: 6px; font-size: 0.68rem; flex-wrap: wrap; }
.pdv-enum-added { color: #40c057; font-weight: 700; font-size: 0.65rem; }
.pdv-enum-removed { color: #fa5252; text-decoration: line-through; font-size: 0.65rem; }

/* Properties */
.pdv-prop-grid { display: flex; flex-direction: column; gap: 3px; }
.pdv-prop { display: flex; align-items: center; gap: 5px; font-size: 0.68rem; }
.pdv-tag { font-size: 0.54rem; font-weight: 700; padding: 0 4px; border-radius: 3px; line-height: 1.5; }
.pdv-tag--pk { color: #f59f00; background: rgba(245,159,0,.14); border: 1px solid rgba(245,159,0,.35); }
.pdv-tag--fk { color: #4263eb; background: rgba(66,99,235,.12); border: 1px solid rgba(66,99,235,.32); }
.pdv-tag--req { color: #fa5252; background: rgba(250,82,82,.1); border: 1px solid rgba(250,82,82,.3); }

/* GWT */
.pdv-gwt-card { border: 1px solid var(--color-border); border-radius: 4px; padding: 6px 8px; display: flex; flex-direction: column; gap: 3px; }
.pdv-gwt-scenario { font-size: 0.66rem; font-weight: 600; color: var(--color-text); }
.pdv-gwt-row { display: flex; gap: 7px; font-size: 0.66rem; color: var(--color-text); align-items: baseline; }
.pdv-gwt-k { flex-shrink: 0; font-size: 0.55rem; font-weight: 800; width: 44px; }
.pdv-gwt-k--g { color: #1098ad; }
.pdv-gwt-k--w { color: #f59f00; }
.pdv-gwt-k--t { color: #40c057; }

/* Invariant objects / traceability */
.pdv-bullet { color: var(--color-text-light); flex-shrink: 0; }
.pdv-verify { font-size: 0.6rem; color: var(--color-text-light); margin-left: 6px; }
.pdv-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.pdv-chip { font-size: 0.6rem; font-family: monospace; background: var(--color-bg-tertiary); border: 1px solid var(--color-border); border-radius: 10px; padding: 1px 7px; color: var(--color-text); }

/* Journeys */
.pdv-journeys { border: 1px solid color-mix(in srgb, #1098ad 40%, var(--color-border)); border-radius: 8px; overflow: hidden; margin-top: 6px; }
.pdv-journeys__head { display: flex; align-items: center; gap: 8px; padding: 7px 10px; background: rgba(16,152,173,.1); font-size: 0.74rem; font-weight: 700; color: #1098ad; border-bottom: 1px solid rgba(16,152,173,.25); }
.pdv-journey { padding: 8px 10px; border-bottom: 1px solid var(--color-border); }
.pdv-journey:last-child { border-bottom: none; }
.pdv-journey__name { font-size: 0.7rem; font-weight: 600; color: var(--color-text); margin-bottom: 6px; }
.pdv-flow { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.pdv-flow__arrow { color: var(--color-text-light); font-size: 0.7rem; }
.pdv-flow__step { font-size: 0.64rem; background: var(--color-bg-tertiary); border: 1px solid var(--color-border); border-radius: 4px; padding: 3px 8px; color: var(--color-text); white-space: nowrap; }
.pdv-flow__step--gw { border-style: dashed; color: var(--color-text-light); }
</style>
