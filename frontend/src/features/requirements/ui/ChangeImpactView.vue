<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

const props = defineProps({
  changeId: { type: String, required: true },
  initialEffects: { type: Array, default: () => [] },
  autoAnalyze: { type: Boolean, default: false },
})
const emit = defineEmits(['analyzed'])

const store = useRequirementsStore()
const effects = ref(props.initialEffects || [])
const loading = ref(false)
const analyzing = ref(false)
const analyzeMsg = ref('')
const expandedNodes = ref(new Set())

// ── Layer definitions ─────────────────────────────────────────────────
const LAYERS = [
  {
    key: 'requirements',
    label: 'Requirements',
    sublabel: 'Stories · Features',
    icon: '📋',
    color: '#228be6',
    labels: ['UserStory', 'Feature'],
  },
  {
    key: 'process',
    label: 'Process',
    sublabel: 'Bounded Contexts',
    icon: '🏛',
    color: '#ae3ec9',
    labels: ['BoundedContext'],
  },
  {
    key: 'design',
    label: 'Design',
    sublabel: 'Aggregates · Commands · Events',
    icon: '📐',
    color: '#f59f00',
    labels: ['Aggregate', 'Command', 'Event', 'Policy', 'ReadModel'],
  },
  {
    key: 'code',
    label: 'Source Code',
    sublabel: 'Classes · Methods',
    icon: '💻',
    color: '#40c057',
    labels: ['SourceCode', 'Class', 'Method', 'Service'],
  },
]

const IMPACT_ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 }
const IMPACT_COLORS = { HIGH: '#fa5252', MEDIUM: '#fd7e14', LOW: '#228be6' }
const IMPACT_BG = { HIGH: 'rgba(250,82,82,0.08)', MEDIUM: 'rgba(253,126,20,0.08)', LOW: 'rgba(34,139,230,0.08)' }

const LABEL_ICONS = {
  UserStory: '👤',
  Feature: '✨',
  BoundedContext: '🏛',
  Aggregate: '📦',
  Command: '⚡',
  Event: '🔔',
  Policy: '📜',
  ReadModel: '🔍',
  SourceCode: '📄',
  Class: '🧩',
  Method: '🔧',
  Service: '⚙️',
}

// Group and sort effects into layers — split MODIFY vs CREATE
const layeredModify = computed(() => {
  const result = {}
  for (const layer of LAYERS) {
    result[layer.key] = (effects.value || [])
      .filter(e => layer.labels.includes(e.nodeLabel) && e.changeType !== 'CREATE')
      .sort((a, b) => (IMPACT_ORDER[a.impactLevel] ?? 3) - (IMPACT_ORDER[b.impactLevel] ?? 3))
  }
  return result
})

const layeredCreate = computed(() => {
  const result = {}
  for (const layer of LAYERS) {
    result[layer.key] = (effects.value || [])
      .filter(e => layer.labels.includes(e.nodeLabel) && e.changeType === 'CREATE')
      .sort((a, b) => (IMPACT_ORDER[a.impactLevel] ?? 3) - (IMPACT_ORDER[b.impactLevel] ?? 3))
  }
  return result
})

// Kept for backward compat (totalCount)
const layeredEffects = computed(() => {
  const result = {}
  for (const layer of LAYERS) {
    result[layer.key] = (effects.value || [])
      .filter(e => layer.labels.includes(e.nodeLabel))
      .sort((a, b) => (IMPACT_ORDER[a.impactLevel] ?? 3) - (IMPACT_ORDER[b.impactLevel] ?? 3))
  }
  return result
})

// Only show layers that have nodes (MODIFY or CREATE)
const activeLayers = computed(() =>
  LAYERS.filter(l => layeredEffects.value[l.key]?.length > 0)
)
// Layer count: MODIFY + CREATE 합산
const layerTotalCount = (layerKey) =>
  (layeredModify.value[layerKey]?.length || 0) + (layeredCreate.value[layerKey]?.length || 0)

const totalCount = computed(() => effects.value?.length || 0)

function resolveCreateTitle(effect) {
  const t = effect.templateData
  if (!t) return `신규 ${effect.nodeLabel}`
  if (effect.nodeLabel === 'UserStory') {
    const role = t.role || ''
    const action = t.action || ''
    return role && action ? `${role}이/가 ${action}` : action || `신규 ${effect.nodeLabel}`
  }
  return t.name || `신규 ${effect.nodeLabel}`
}

function toggleNode(nodeId) {
  if (expandedNodes.value.has(nodeId)) {
    expandedNodes.value.delete(nodeId)
  } else {
    expandedNodes.value.add(nodeId)
  }
}

// ── Data loading ──────────────────────────────────────────────────────
async function loadImpact() {
  loading.value = true
  try {
    const data = await store.fetchImpact(props.changeId)
    effects.value = data.effects || []
    expandedNodes.value.clear()
  } finally {
    loading.value = false
  }
}

async function reanalyze() {
  analyzing.value = true
  analyzeMsg.value = 'AI가 영향도를 분석 중...'
  try {
    const res = await fetch(
      `/api/requirement-changes/${encodeURIComponent(props.changeId)}/analyze-impact`,
      { method: 'POST' }
    )
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop()
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const d = JSON.parse(line.slice(6))
          analyzeMsg.value = d.message || d.phase
          if (d.phase === 'done') await loadImpact()
        }
      }
    }
  } finally {
    analyzing.value = false
    analyzeMsg.value = ''
    emit('analyzed')
  }
}

onMounted(async () => {
  await loadImpact()
  if (props.autoAnalyze && !effects.value.length) {
    reanalyze()
  }
})
</script>

<template>
  <div class="civ-root">
    <!-- 툴바 -->
    <div class="civ-toolbar">
      <span class="civ-toolbar__title">
        영향도 트리
        <span v-if="totalCount" class="civ-total-badge">{{ totalCount }}</span>
      </span>
      <button class="tb-btn civ-btn" :disabled="analyzing || loading" @click="reanalyze">
        <span v-if="analyzing" class="civ-spinner" />
        {{ analyzing ? analyzeMsg : '재분석' }}
      </button>
    </div>

    <!-- 로딩 -->
    <div v-if="loading" class="civ-loading">
      <span class="civ-spinner" /> 불러오는 중...
    </div>

    <!-- 분석 진행 중 -->
    <div v-else-if="analyzing" class="civ-analyzing">
      <span class="civ-spinner" />
      {{ analyzeMsg }}
    </div>

    <!-- 계층 트리 -->
    <div v-else-if="activeLayers.length" class="civ-tree">
      <!-- Change 루트 노드 -->
      <div class="civ-root-node">
        <span class="civ-root-node__icon">🔄</span>
        <span class="civ-root-node__id">{{ changeId }}</span>
        <span class="civ-root-node__label">요구사항 변경</span>
      </div>

      <!-- 레이어 반복 -->
      <template v-for="(layer, idx) in activeLayers" :key="layer.key">
        <!-- 커넥터 화살표 -->
        <div class="civ-connector">
          <div class="civ-connector__line" />
          <div class="civ-connector__arrow" />
        </div>

        <!-- 레이어 블록 -->
        <div class="civ-layer" :style="{ '--layer-color': layer.color }">
          <div class="civ-layer__header">
            <span class="civ-layer__icon">{{ layer.icon }}</span>
            <div class="civ-layer__labels">
              <span class="civ-layer__name">{{ layer.label }}</span>
              <span class="civ-layer__sub">{{ layer.sublabel }}</span>
            </div>
            <span class="civ-layer__count">{{ layerTotalCount(layer.key) }}</span>
          </div>

          <div class="civ-layer__nodes">
            <!-- MODIFY: 기존 노드 수정 -->
            <div
              v-for="e in layeredModify[layer.key]"
              :key="e.nodeId"
              class="civ-node"
              :class="[`civ-node--${e.impactLevel?.toLowerCase()}`, { 'civ-node--expanded': expandedNodes.has(e.nodeId) }]"
              :style="{ '--impact-color': IMPACT_COLORS[e.impactLevel], '--impact-bg': IMPACT_BG[e.impactLevel] }"
              @click="toggleNode(e.nodeId)"
            >
              <div class="civ-node__row">
                <span class="civ-node__icon">{{ LABEL_ICONS[e.nodeLabel] || '🔷' }}</span>
                <div class="civ-node__info">
                  <span class="civ-node__title">{{ e.nodeTitle || e.nodeId }}</span>
                  <span class="civ-node__id">{{ e.nodeId }}</span>
                </div>
                <span class="civ-node__impact">{{ e.impactLevel }}</span>
                <span class="civ-node__chevron">{{ expandedNodes.has(e.nodeId) ? '▲' : '▼' }}</span>
              </div>
              <div v-if="expandedNodes.has(e.nodeId)" class="civ-node__reason">
                {{ e.reason }}
              </div>
            </div>

            <!-- CREATE 구분선 -->
            <div v-if="layeredCreate[layer.key]?.length > 0 && layeredModify[layer.key]?.length > 0"
                 class="civ-create-divider">
              신규 추가 제안
            </div>

            <!-- CREATE: 신규 노드 생성 -->
            <div
              v-for="e in layeredCreate[layer.key]"
              :key="e.nodeId"
              class="civ-node civ-node--create"
              :class="{ 'civ-node--expanded': expandedNodes.has(e.nodeId) }"
              @click="toggleNode(e.nodeId)"
            >
              <div class="civ-node__row">
                <span class="civ-node__icon">{{ LABEL_ICONS[e.nodeLabel] || '🔷' }}</span>
                <div class="civ-node__info">
                  <span class="civ-node__title">{{ resolveCreateTitle(e) }}</span>
                  <span class="civ-node__id civ-node__id--new">신규 생성 예정</span>
                </div>
                <span class="civ-badge-new">🆕 신규</span>
                <span v-if="e.appliedNodeId" class="civ-badge-applied" :title="e.appliedNodeId">생성 완료</span>
                <span class="civ-node__impact" style="color:#40c057;border-color:rgba(64,192,87,.3);background:rgba(64,192,87,.1)">{{ e.impactLevel }}</span>
                <span class="civ-node__chevron">{{ expandedNodes.has(e.nodeId) ? '▲' : '▼' }}</span>
              </div>
              <!-- 펼침: templateData 필드 표시 -->
              <div v-if="expandedNodes.has(e.nodeId)" class="civ-node__reason civ-node__create-detail">
                <div class="civ-create-reason"><strong>추가 이유:</strong> {{ e.reason }}</div>
                <template v-if="e.templateData">
                  <div v-if="e.templateData.role" class="civ-create-field"><span class="civ-cf-label">역할</span> {{ e.templateData.role }}</div>
                  <div v-if="e.templateData.action" class="civ-create-field"><span class="civ-cf-label">행위</span> {{ e.templateData.action }}</div>
                  <div v-if="e.templateData.benefit" class="civ-create-field"><span class="civ-cf-label">가치</span> {{ e.templateData.benefit }}</div>
                  <div v-if="e.templateData.name" class="civ-create-field"><span class="civ-cf-label">이름</span> {{ e.templateData.name }}</div>
                  <div v-if="e.templateData.description" class="civ-create-field"><span class="civ-cf-label">설명</span> {{ e.templateData.description }}</div>
                  <div v-if="e.templateData.parentBCName" class="civ-create-field"><span class="civ-cf-label">상위 BC</span> {{ e.templateData.parentBCName }}</div>
                  <div v-if="e.templateData.parentFeatureName" class="civ-create-field"><span class="civ-cf-label">상위 Feature</span> {{ e.templateData.parentFeatureName }}</div>
                  <div v-if="e.appliedNodeId" class="civ-create-field civ-create-field--applied">
                    <span class="civ-cf-label">생성된 ID</span>
                    <span class="civ-mono">{{ e.appliedNodeId }}</span>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 빈 상태 -->
    <div v-else class="civ-empty">
      <div class="civ-empty__icon">🔍</div>
      <div class="civ-empty__msg">분석 결과가 없습니다</div>
      <div class="civ-empty__hint">아직 분석되지 않았거나 영향받는 노드가 없습니다.</div>
      <button class="tb-btn civ-btn" style="margin-top:10px" @click="reanalyze">분석 시작</button>
    </div>
  </div>
</template>

<style scoped>
.civ-root {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ── 툴바 ── */
.civ-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.civ-toolbar__title {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--color-text);
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}
.civ-total-badge {
  background: var(--color-accent);
  color: #fff;
  font-size: 0.6rem;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 10px;
}
.civ-btn { font-size: 0.68rem; padding: 3px 10px; display: flex; align-items: center; gap: 5px; }

/* ── 스피너 ── */
.civ-spinner {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: civ-spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes civ-spin { to { transform: rotate(360deg); } }

.civ-loading, .civ-analyzing {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.72rem;
  color: var(--color-text-light);
  padding: 20px 0;
}

/* ── 루트 Change 노드 ── */
.civ-root-node {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--color-bg-secondary);
  border: 1.5px solid var(--color-accent);
  border-radius: 8px;
  padding: 8px 12px;
  box-shadow: 0 0 0 3px rgba(34,139,230,0.08);
}
.civ-root-node__icon { font-size: 0.9rem; }
.civ-root-node__id {
  font-family: monospace;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-accent);
}
.civ-root-node__label {
  font-size: 0.68rem;
  color: var(--color-text-light);
}

/* ── 커넥터 ── */
.civ-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2px 0;
}
.civ-connector__line {
  width: 2px;
  height: 16px;
  background: var(--color-border);
}
.civ-connector__arrow {
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 7px solid var(--color-border);
}

/* ── 레이어 블록 ── */
.civ-layer {
  border: 1px solid var(--layer-color, var(--color-border));
  border-radius: 8px;
  overflow: hidden;
  background: var(--color-bg);
}
.civ-layer__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: color-mix(in srgb, var(--layer-color, var(--color-accent)) 10%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--layer-color, var(--color-border)) 30%, transparent);
}
.civ-layer__icon { font-size: 0.85rem; }
.civ-layer__labels { flex: 1; display: flex; flex-direction: column; gap: 1px; }
.civ-layer__name {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--layer-color, var(--color-text));
}
.civ-layer__sub {
  font-size: 0.6rem;
  color: var(--color-text-light);
}
.civ-layer__count {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--layer-color, var(--color-text-light));
  background: color-mix(in srgb, var(--layer-color, var(--color-accent)) 15%, transparent);
  padding: 1px 6px;
  border-radius: 10px;
}

.civ-layer__nodes {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ── 노드 카드 ── */
.civ-node {
  padding: 7px 10px;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  transition: background 0.12s;
  background: var(--impact-bg, transparent);
}
.civ-node:last-child { border-bottom: none; }
.civ-node:hover { background: color-mix(in srgb, var(--impact-color, var(--color-accent)) 8%, var(--color-bg-tertiary)); }

.civ-node__row {
  display: flex;
  align-items: center;
  gap: 7px;
}
.civ-node__icon { font-size: 0.8rem; flex-shrink: 0; }
.civ-node__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.civ-node__title {
  font-size: 0.73rem;
  font-weight: 500;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.civ-node__id {
  font-family: monospace;
  font-size: 0.6rem;
  color: var(--color-text-light);
}
.civ-node__impact {
  flex-shrink: 0;
  font-size: 0.58rem;
  font-weight: 700;
  color: var(--impact-color);
  background: color-mix(in srgb, var(--impact-color) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--impact-color) 30%, transparent);
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.04em;
}
.civ-node__chevron {
  font-size: 0.55rem;
  color: var(--color-text-light);
  flex-shrink: 0;
}

.civ-node__reason {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--color-border);
  font-size: 0.68rem;
  color: var(--color-text-light);
  line-height: 1.5;
}

/* ── CREATE 유형 노드 ── */
.civ-node--create {
  border-left: 3px solid #40c057;
  background: rgba(64, 192, 87, 0.04);
}
.civ-node--create:hover { background: rgba(64, 192, 87, 0.09); }

.civ-create-divider {
  font-size: 0.6rem;
  font-weight: 700;
  color: #40c057;
  padding: 4px 10px;
  background: rgba(64, 192, 87, 0.06);
  border-top: 1px dashed rgba(64, 192, 87, 0.3);
  border-bottom: 1px dashed rgba(64, 192, 87, 0.3);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.civ-badge-new {
  flex-shrink: 0;
  font-size: 0.58rem;
  font-weight: 700;
  color: #40c057;
  background: rgba(64, 192, 87, 0.12);
  border: 1px solid rgba(64, 192, 87, 0.35);
  padding: 1px 5px;
  border-radius: 3px;
}

.civ-badge-applied {
  flex-shrink: 0;
  font-size: 0.58rem;
  font-weight: 700;
  color: #228be6;
  background: rgba(34, 139, 230, 0.1);
  border: 1px solid rgba(34, 139, 230, 0.3);
  padding: 1px 5px;
  border-radius: 3px;
}

.civ-node__id--new {
  color: #40c057;
  font-style: italic;
}

.civ-node__create-detail {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.civ-create-reason { margin-bottom: 4px; }

.civ-create-field {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 0.67rem;
}

.civ-create-field--applied {
  color: #228be6;
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed var(--color-border);
}

.civ-cf-label {
  flex-shrink: 0;
  font-weight: 700;
  color: var(--color-text);
  min-width: 55px;
  font-size: 0.63rem;
}

.civ-mono {
  font-family: monospace;
  font-size: 0.63rem;
}

/* ── 빈 상태 ── */
.civ-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 16px;
  text-align: center;
}
.civ-empty__icon { font-size: 2rem; margin-bottom: 8px; }
.civ-empty__msg { font-size: 0.8rem; font-weight: 600; color: var(--color-text); margin-bottom: 4px; }
.civ-empty__hint { font-size: 0.68rem; color: var(--color-text-light); }
</style>
