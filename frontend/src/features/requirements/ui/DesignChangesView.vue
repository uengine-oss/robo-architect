<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import { useAggregateViewerStore } from '@/features/canvas/aggregateViewer.store'

const props = defineProps({
  changeId:  { type: String,  required: true },
  status:    { type: String,  required: true },
  autoApply: { type: Boolean, default: false },
})
const emit = defineEmits(['applied', 'undone'])

const store          = useRequirementsStore()
const aggViewerStore = useAggregateViewerStore()
const activeTab      = inject('activeTab', null)   // App.vue 탭 전환

// ── State ─────────────────────────────────────────────────────────────
const applying    = ref(false)
const applyMsg    = ref('')
const totalNodes  = ref(0)
const doneCount   = ref(0)
const expandedId  = ref(null)
const undoDialog  = ref(false)
const undoing     = ref(false)
const nodeMap     = ref({})  // nodeId → item

// ── Layer definitions ─────────────────────────────────────────────────
const LAYERS = [
  { key:'req',    label:'Requirements', sublabel:'Stories · Features',            icon:'📋', color:'#228be6', labels:['UserStory','Feature'] },
  { key:'proc',   label:'Process',      sublabel:'Bounded Contexts',               icon:'🏛', color:'#ae3ec9', labels:['BoundedContext'] },
  { key:'design', label:'Design',       sublabel:'Aggregates · Commands · Events', icon:'📐', color:'#f59f00', labels:['Aggregate','Command','Event','Policy','ReadModel'] },
]
const DESIGN_LABELS = new Set(['Aggregate','Command','Event','Policy','ReadModel'])
const IMPACT_COLORS = { HIGH:'#fa5252', MEDIUM:'#fd7e14', LOW:'#228be6' }
const LABEL_ICONS   = { UserStory:'👤', Feature:'✨', BoundedContext:'🏛', Aggregate:'📦', Command:'⚡', Event:'🔔', Policy:'📜', ReadModel:'🔍' }
const CHANGE_TYPE_COLORS = { ADDED:'#40c057', REMOVED:'#fa5252', MODIFIED:'#fd7e14', RENAMED:'#228be6' }
const CHANGE_TYPE_ICONS  = { ADDED:'＋', REMOVED:'－', MODIFIED:'✎', RENAMED:'⇄' }
const CHANGE_TYPE_LABELS = { ADDED:'추가', REMOVED:'삭제', MODIFIED:'수정', RENAMED:'이름 변경' }

const layeredNodes = computed(() => {
  const m = {}
  for (const l of LAYERS) {
    m[l.key] = Object.values(nodeMap.value)
      .filter(n => l.labels.includes(n.nodeLabel))
      .sort((a, b) => ({'HIGH':0,'MEDIUM':1,'LOW':2}[a.impactLevel]??3) - ({'HIGH':0,'MEDIUM':1,'LOW':2}[b.impactLevel]??3))
  }
  return m
})
const activeLayers = computed(() => LAYERS.filter(l => layeredNodes.value[l.key]?.length))

const hasStructuredDiff = (node) =>
  node.fieldChanges?.length || node.valueObjectChanges?.length ||
  node.enumChanges?.length  || node.invariantChanges?.length

const isCreateType = (node) => node.changeType === 'CREATE'

const createNodeCount = computed(() =>
  Object.values(nodeMap.value).filter(n => n.changeType === 'CREATE' && n.status === 'done').length
)

// ── Data loading ──────────────────────────────────────────────────────
async function loadSaved() {
  try {
    const data = await store.fetchDesignChanges(props.changeId)
    if (data.items?.length) {
      const m = {}
      for (const item of data.items) m[item.nodeId] = { ...item, status: 'done' }
      nodeMap.value = m
    }
  } catch { /* ignore */ }
}

// ── Design apply SSE ──────────────────────────────────────────────────
function startApply() {
  applying.value = true
  applyMsg.value = '설계 반영 준비 중...'
  nodeMap.value  = {}
  doneCount.value = 0

  store.applyDesign(props.changeId, {
    onProgress(data) {
      const { phase } = data
      if (phase === 'applying') {
        totalNodes.value = data.total || 0
        applyMsg.value = data.message || ''
      } else if (phase === 'item_start') {
        nodeMap.value = { ...nodeMap.value, [data.nodeId]: {
          nodeId: data.nodeId, nodeLabel: data.nodeLabel,
          nodeTitle: data.nodeTitle || data.nodeId,
          field: data.field, before: data.before || '',
          after: null, impactLevel: data.impactLevel || 'MEDIUM',
          changeType: data.changeType || 'MODIFY',
          status: 'processing',
        }}
        applyMsg.value = data.message || ''
      } else if (phase === 'item_struct_start') {
        applyMsg.value = data.message || ''
      } else if (phase === 'item_done') {
        const item = data.item || {}
        nodeMap.value = { ...nodeMap.value, [item.nodeId]: { ...(nodeMap.value[item.nodeId]||{}), ...item, changeType: item.changeType || 'MODIFY', status:'done' }}
        doneCount.value++
      } else if (phase === 'item_skipped') {
        if (data.nodeId && nodeMap.value[data.nodeId]) {
          nodeMap.value = { ...nodeMap.value, [data.nodeId]: { ...nodeMap.value[data.nodeId], status:'skipped' }}
        }
      } else if (phase === 'applying_done') {
        applyMsg.value = `반영 완료: ${data.applied}/${data.total}개 업데이트`
      }
    },
    onDone() { applying.value = false; emit('applied') },
    onError(e) { applying.value = false; applyMsg.value = `오류: ${e.message}` },
  })
}

// ── Undo ─────────────────────────────────────────────────────────────
async function confirmUndo() {
  undoing.value = true
  try {
    await store.undoDesign(props.changeId)
    undoDialog.value = false
    nodeMap.value = {}
    emit('undone')
  } catch (e) {
    alert(`되돌리기 실패: ${e.message}`)
  } finally {
    undoing.value = false
  }
}

// ── Navigation ────────────────────────────────────────────────────────
function navigateTo(node) {
  if (!activeTab) return
  if (node.nodeLabel === 'Aggregate') {
    // Aggregate: Data 탭으로 전환 후 해당 Aggregate 포커스
    aggViewerStore.focusAggregate(node.nodeId)
    activeTab.value = 'Data'
  } else if (DESIGN_LABELS.has(node.nodeLabel)) {
    // Command/Event/Policy: Design(캔버스) 탭
    activeTab.value = 'Design'
  } else {
    // UserStory/Feature/BoundedContext: Design 탭
    activeTab.value = 'Design'
  }
}

onMounted(async () => {
  await loadSaved()
  if (props.autoApply && props.status === 'PLAN_APPROVED' && !Object.keys(nodeMap.value).length) {
    startApply()
  }
})
</script>

<template>
  <div class="dcv-root">
    <!-- ── 툴바 ─────────────────────────────────────────────────── -->
    <div class="dcv-toolbar">
      <span class="dcv-toolbar__title">
        설계 변경 내용
        <span v-if="totalNodes > 0" class="dcv-badge-prog">{{ doneCount }}/{{ totalNodes }}</span>
      </span>
      <button v-if="status === 'DESIGN_APPLIED'" class="tb-btn dcv-undo-btn"
              @click="undoDialog = true">↩ 설계 되돌리기</button>
      <button v-if="status === 'PLAN_APPROVED'" class="tb-btn tb-btn--primary dcv-apply-btn"
              :disabled="applying" @click="startApply">
        <span v-if="applying" class="dcv-spin" />
        {{ applying ? '반영 중...' : '설계 변경 적용' }}
      </button>
    </div>

    <!-- ── 진행 배너 ─────────────────────────────────────────── -->
    <div v-if="applying && applyMsg" class="dcv-banner">
      <span class="dcv-spin" /> {{ applyMsg }}
    </div>

    <!-- ── 계층 트리 ──────────────────────────────────────────── -->
    <div v-if="activeLayers.length" class="dcv-tree">
      <template v-for="(layer, li) in activeLayers" :key="layer.key">
        <div v-if="li > 0" class="dcv-arrow-down">
          <div class="dcv-arrow-down__line" /><div class="dcv-arrow-down__head" />
        </div>

        <div class="dcv-layer" :style="{'--lc': layer.color}">
          <div class="dcv-layer__head">
            <span>{{ layer.icon }}</span>
            <div class="dcv-layer__meta">
              <span class="dcv-layer__name">{{ layer.label }}</span>
              <span class="dcv-layer__sub">{{ layer.sublabel }}</span>
            </div>
            <span class="dcv-layer__badge">{{ layeredNodes[layer.key].length }}</span>
          </div>

          <div class="dcv-nodes">
            <div v-for="node in layeredNodes[layer.key]" :key="node.nodeId"
                 class="dcv-node" :class="`dcv-node--${node.status}`"
                 :style="{'--ic': IMPACT_COLORS[node.impactLevel]}">

              <!-- 노드 헤더 행 -->
              <div class="dcv-node__row">
                <span class="dcv-node__state-icon">
                  <span v-if="node.status==='processing'" class="dcv-spin dcv-spin--sm"/>
                  <span v-else-if="node.status==='done' && isCreateType(node)" class="dcv-check dcv-check--create">✦</span>
                  <span v-else-if="node.status==='done'" class="dcv-check">✓</span>
                  <span v-else-if="node.status==='skipped'" class="dcv-skip">—</span>
                  <span v-else class="dcv-pend">○</span>
                </span>
                <span class="dcv-node__type-icon">{{ LABEL_ICONS[node.nodeLabel]||'🔷' }}</span>
                <div class="dcv-node__info">
                  <span class="dcv-node__title">{{ node.nodeTitle }}</span>
                  <span v-if="isCreateType(node)" class="dcv-node__sub dcv-node__sub--create">
                    {{ node.nodeLabel }} · 신규 생성
                    <span v-if="node.createdNodeId" class="dcv-created-id">→ {{ node.createdNodeId }}</span>
                  </span>
                  <span v-else class="dcv-node__sub">{{ node.nodeLabel }} · {{ node.field }}</span>
                </div>
                <span v-if="isCreateType(node)" class="dcv-create-badge">🆕 신규</span>
                <span class="dcv-impact-badge">{{ node.impactLevel }}</span>
                <!-- 드릴다운 링크 (MODIFY only) -->
                <button v-if="node.status==='done' && !isCreateType(node)" class="dcv-link-btn"
                        :title="node.nodeLabel==='Aggregate' ? 'Data 탭에서 Aggregate 보기' : 'Design 탭에서 보기'"
                        @click.stop="navigateTo(node)">
                  {{ node.nodeLabel === 'Aggregate' ? '📊' : '🎨' }} 보기
                </button>
                <!-- 펼침 토글 -->
                <button v-if="node.status==='done'" class="dcv-expand-btn"
                        @click="expandedId = expandedId === node.nodeId ? null : node.nodeId">
                  {{ expandedId === node.nodeId ? '▲' : '▼' }}
                </button>
              </div>

              <!-- ── 펼침 콘텐츠 ──────────────────────────── -->
              <div v-if="expandedId === node.nodeId && node.status === 'done'" class="dcv-detail">

                <!-- CREATE 유형: templateData 요약 -->
                <template v-if="isCreateType(node)">
                  <div class="dcv-create-summary">
                    <div class="dcv-cs-title">신규 생성된 노드 정보</div>
                    <template v-if="node.templateData">
                      <div v-if="node.templateData.role" class="dcv-cs-row"><span class="dcv-cs-label">역할</span>{{ node.templateData.role }}</div>
                      <div v-if="node.templateData.action" class="dcv-cs-row"><span class="dcv-cs-label">행위</span>{{ node.templateData.action }}</div>
                      <div v-if="node.templateData.benefit" class="dcv-cs-row"><span class="dcv-cs-label">가치</span>{{ node.templateData.benefit }}</div>
                      <div v-if="node.templateData.name" class="dcv-cs-row"><span class="dcv-cs-label">이름</span>{{ node.templateData.name }}</div>
                      <div v-if="node.templateData.description" class="dcv-cs-row"><span class="dcv-cs-label">설명</span>{{ node.templateData.description }}</div>
                      <div v-if="node.templateData.parentBCName" class="dcv-cs-row"><span class="dcv-cs-label">상위 BC</span>{{ node.templateData.parentBCName }}</div>
                      <div v-if="node.templateData.parentFeatureName" class="dcv-cs-row"><span class="dcv-cs-label">상위 Feature</span>{{ node.templateData.parentFeatureName }}</div>
                      <div v-if="node.createdNodeId" class="dcv-cs-row dcv-cs-row--id">
                        <span class="dcv-cs-label">생성된 ID</span>
                        <span class="dcv-mono">{{ node.createdNodeId }}</span>
                      </div>
                    </template>
                    <div v-else class="dcv-cs-empty">템플릿 정보 없음</div>
                  </div>
                </template>


                <!-- Design 레이어: 구조화 diff 테이블 먼저 -->
                <template v-if="DESIGN_LABELS.has(node.nodeLabel) && hasStructuredDiff(node)">

                  <!-- Field Changes -->
                  <div v-if="node.fieldChanges?.length" class="dcv-section">
                    <div class="dcv-section__title">📋 필드 변경</div>
                    <table class="dcv-table">
                      <thead>
                        <tr><th>구분</th><th>필드명</th><th>타입</th><th>변경 전</th><th>변경 후</th><th>이유</th></tr>
                      </thead>
                      <tbody>
                        <tr v-for="(fc, i) in node.fieldChanges" :key="i"
                            :style="{'--ct': CHANGE_TYPE_COLORS[fc.type]}">
                          <td><span class="dcv-type-badge">{{ CHANGE_TYPE_ICONS[fc.type] }} {{ CHANGE_TYPE_LABELS[fc.type] }}</span></td>
                          <td class="dcv-mono">{{ fc.name }}</td>
                          <td class="dcv-type">{{ fc.dataType || '—' }}</td>
                          <td class="dcv-before-cell">{{ fc.before || '—' }}</td>
                          <td class="dcv-after-cell">{{ fc.after || '—' }}</td>
                          <td class="dcv-reason">{{ fc.description || '—' }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <!-- Value Object Changes -->
                  <div v-if="node.valueObjectChanges?.length" class="dcv-section">
                    <div class="dcv-section__title">🧩 Value Object 변경</div>
                    <div class="dcv-vo-list">
                      <div v-for="(vc, i) in node.valueObjectChanges" :key="i" class="dcv-vo-card"
                           :style="{'--ct': CHANGE_TYPE_COLORS[vc.type]}">
                        <div class="dcv-vo-card__head">
                          <span class="dcv-type-badge">{{ CHANGE_TYPE_ICONS[vc.type] }} {{ CHANGE_TYPE_LABELS[vc.type] }}</span>
                          <span class="dcv-mono">{{ vc.name }}</span>
                          <span v-if="vc.displayName" class="dcv-display-name">{{ vc.displayName }}</span>
                        </div>
                        <div v-if="vc.description" class="dcv-vo-card__desc">{{ vc.description }}</div>
                        <div v-if="vc.fields?.length" class="dcv-vo-fields">
                          <span v-for="f in vc.fields" :key="f.name" class="dcv-vo-field">
                            {{ f.name }}: <em>{{ f.type }}</em>
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Enum Changes -->
                  <div v-if="node.enumChanges?.length" class="dcv-section">
                    <div class="dcv-section__title">🔢 Enumeration 변경</div>
                    <div class="dcv-enum-list">
                      <div v-for="(ec, i) in node.enumChanges" :key="i" class="dcv-enum-row">
                        <span class="dcv-mono">{{ ec.enumName }}</span>
                        <span v-for="item in (ec.addedItems||[])" :key="item" class="dcv-enum-added">＋{{ item }}</span>
                        <span v-for="item in (ec.removedItems||[])" :key="item" class="dcv-enum-removed">－{{ item }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- Invariant Changes -->
                  <div v-if="node.invariantChanges?.length" class="dcv-section">
                    <div class="dcv-section__title">📏 불변식 추가</div>
                    <ul class="dcv-invariant-list">
                      <li v-for="(inv, i) in node.invariantChanges" :key="i">{{ inv }}</li>
                    </ul>
                  </div>

                  <!-- Description diff (접힘 가능) -->
                  <div class="dcv-section dcv-section--desc">
                    <div class="dcv-section__title">📝 설명 변경 (before / after)</div>
                    <div class="dcv-text-diff">
                      <div class="dcv-td-col dcv-td-before">
                        <div class="dcv-td-label">변경 전</div>
                        <div class="dcv-td-content">{{ node.before || '(없음)' }}</div>
                      </div>
                      <div class="dcv-td-mid">→</div>
                      <div class="dcv-td-col dcv-td-after">
                        <div class="dcv-td-label">변경 후</div>
                        <div class="dcv-td-content">{{ node.after }}</div>
                      </div>
                    </div>
                  </div>

                </template>

                <!-- Requirements/Process: 텍스트 diff만 (MODIFY only) -->
                <template v-else-if="!isCreateType(node)">
                  <div class="dcv-text-diff">
                    <div class="dcv-td-col dcv-td-before">
                      <div class="dcv-td-label">변경 전</div>
                      <div class="dcv-td-content">{{ node.before || '(없음)' }}</div>
                    </div>
                    <div class="dcv-td-mid">→</div>
                    <div class="dcv-td-col dcv-td-after">
                      <div class="dcv-td-label">변경 후</div>
                      <div class="dcv-td-content">{{ node.after }}</div>
                    </div>
                  </div>
                </template>

              </div><!-- /dcv-detail -->

              <!-- processing 중: CREATE이면 생성 중, MODIFY이면 before 미리 보기 -->
              <div v-else-if="node.status==='processing'" class="dcv-processing-preview">
                <template v-if="isCreateType(node)">
                  <span class="dcv-pd-generating"><span class="dcv-spin dcv-spin--xs" /> 노드 생성 중...</span>
                </template>
                <template v-else-if="node.before">
                  <span class="dcv-pd-label">현재 내용 (변경 전):</span>
                  <span class="dcv-pd-text">{{ node.before.slice(0, 120) }}{{ node.before.length > 120 ? '…' : '' }}</span>
                  <span class="dcv-pd-generating"><span class="dcv-spin dcv-spin--xs" /> AI 작성 중...</span>
                </template>
              </div>

            </div><!-- /dcv-node -->
          </div>
        </div><!-- /dcv-layer -->
      </template>
    </div>

    <!-- ── 빈 상태 ──────────────────────────────────────────── -->
    <div v-else-if="!applying" class="dcv-empty">
      <template v-if="status === 'PLAN_APPROVED'">
        아직 설계 변경이 적용되지 않았습니다.
        <button class="tb-btn" style="margin-top:10px" @click="startApply">설계 변경 적용 시작</button>
      </template>
      <template v-else>설계 변경 내역이 없습니다.</template>
    </div>

    <!-- ── Undo 확인 다이얼로그 ──────────────────────────────── -->
    <div v-if="undoDialog" class="cp-overlay" @click.self="undoDialog=false">
      <div class="cp-dialog cp-dialog--sm">
        <div class="cp-dialog__header">
          ↩ 설계 변경 되돌리기
          <button class="cp-dialog__close" @click="undoDialog=false">✕</button>
        </div>
        <div class="cp-dialog__body">
          <p>{{ Object.values(nodeMap).filter(n=>n.status==='done').length }}개 노드의 변경 내용이 모두 <strong>원래 값으로 복원</strong>됩니다.</p>
          <p v-if="createNodeCount > 0" style="color:#fa5252;font-size:0.68rem;margin-top:6px;padding:6px 8px;background:rgba(250,82,82,.06);border:1px solid rgba(250,82,82,.25);border-radius:4px">
            ⚠ 신규 생성된 <strong>{{ createNodeCount }}개 노드</strong>가 삭제됩니다 (UserStory/Feature/BoundedContext).
          </p>
          <p style="color:#fa5252;font-size:0.68rem;margin-top:4px">⚠ 이 작업은 실제 Neo4j 노드를 수정합니다. 되돌린 후 다시 적용해야 합니다.</p>
        </div>
        <div class="cp-dialog__footer">
          <button class="tb-btn" @click="undoDialog=false">취소</button>
          <button class="tb-btn tb-btn--danger" :disabled="undoing" @click="confirmUndo">
            <span v-if="undoing" class="dcv-spin dcv-spin--sm" />
            {{ undoing ? '되돌리는 중...' : '설계 변경 취소' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dcv-root { display: flex; flex-direction: column; gap: 10px; }

/* ── Toolbar ── */
.dcv-toolbar { display: flex; align-items: center; gap: 8px; }
.dcv-toolbar__title { font-size: 0.72rem; font-weight: 700; color: var(--color-text); flex: 1; display: flex; align-items: center; gap: 6px; }
.dcv-badge-prog { font-size: 0.6rem; font-weight: 700; padding: 1px 6px; border-radius: 10px; background: var(--color-accent); color: #fff; }
.dcv-apply-btn  { font-size: 0.68rem; padding: 3px 10px; display: flex; align-items: center; gap: 5px; }
.dcv-undo-btn   { font-size: 0.68rem; padding: 3px 10px; color: #fa5252; border-color: rgba(250,82,82,.4); }
.dcv-undo-btn:hover { background: rgba(250,82,82,.08); }

/* ── Banner ── */
.dcv-banner { display: flex; align-items: center; gap: 8px; font-size: 0.7rem; color: var(--color-text-light); background: var(--color-bg-tertiary); border: 1px solid var(--color-border); border-radius: 4px; padding: 6px 10px; }

/* ── Spinner ── */
.dcv-spin    { display: inline-block; width: 10px; height: 10px; border: 2px solid var(--color-border); border-top-color: var(--color-accent); border-radius: 50%; animation: sp 0.7s linear infinite; flex-shrink: 0; }
.dcv-spin--sm { width: 8px; height: 8px; }
.dcv-spin--xs { width: 6px; height: 6px; border-width: 1.5px; }
@keyframes sp { to { transform: rotate(360deg); } }

/* ── Connector ── */
.dcv-arrow-down { display: flex; flex-direction: column; align-items: center; padding: 2px 0; }
.dcv-arrow-down__line { width: 2px; height: 14px; background: var(--color-border); }
.dcv-arrow-down__head { width:0; height:0; border-left:5px solid transparent; border-right:5px solid transparent; border-top:7px solid var(--color-border); }

/* ── Layer ── */
.dcv-layer { border: 1px solid color-mix(in srgb, var(--lc,var(--color-border)) 40%, var(--color-border)); border-radius: 8px; overflow: hidden; }
.dcv-layer__head { display: flex; align-items: center; gap: 8px; padding: 7px 10px; background: color-mix(in srgb, var(--lc,var(--color-accent)) 10%, transparent); border-bottom: 1px solid color-mix(in srgb, var(--lc,var(--color-border)) 25%, transparent); font-size: 0.85rem; }
.dcv-layer__meta { flex: 1; display: flex; flex-direction: column; gap: 1px; }
.dcv-layer__name { font-size: 0.72rem; font-weight: 700; color: var(--lc,var(--color-text)); }
.dcv-layer__sub  { font-size: 0.6rem; color: var(--color-text-light); }
.dcv-layer__badge { font-size: 0.65rem; font-weight: 700; color: var(--lc); background: color-mix(in srgb, var(--lc) 15%, transparent); padding: 1px 6px; border-radius: 10px; }

/* ── Node ── */
.dcv-nodes { display: flex; flex-direction: column; }
.dcv-node { border-bottom: 1px solid var(--color-border); padding: 7px 10px; }
.dcv-node:last-child { border-bottom: none; }
.dcv-node--processing { background: color-mix(in srgb, var(--color-accent) 4%, transparent); }

.dcv-node__row { display: flex; align-items: center; gap: 7px; }
.dcv-node__state-icon { width: 14px; text-align: center; flex-shrink: 0; }
.dcv-check { color: #40c057; font-size: 0.8rem; font-weight: 700; }
.dcv-skip  { color: var(--color-text-light); }
.dcv-pend  { color: var(--color-border); }
.dcv-node__type-icon { font-size: 0.8rem; flex-shrink: 0; }
.dcv-node__info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.dcv-node__title { font-size: 0.73rem; font-weight: 500; color: var(--color-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dcv-node__sub   { font-size: 0.6rem; color: var(--color-text-light); }
.dcv-impact-badge { flex-shrink: 0; font-size: 0.58rem; font-weight: 700; color: var(--ic); background: color-mix(in srgb, var(--ic) 12%, transparent); border: 1px solid color-mix(in srgb, var(--ic) 30%, transparent); padding: 1px 5px; border-radius: 3px; }
.dcv-link-btn    { font-size: 0.62rem; padding: 2px 6px; background: var(--color-bg-tertiary); border: 1px solid var(--color-border); border-radius: 3px; cursor: pointer; color: var(--color-text-light); white-space: nowrap; flex-shrink: 0; }
.dcv-link-btn:hover { color: var(--color-accent); border-color: var(--color-accent); }
.dcv-expand-btn  { font-size: 0.55rem; color: var(--color-text-light); background: none; border: none; cursor: pointer; flex-shrink: 0; padding: 2px 4px; }

/* ── Detail ── */
.dcv-detail { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--color-border); display: flex; flex-direction: column; gap: 10px; }

.dcv-section { display: flex; flex-direction: column; gap: 6px; }
.dcv-section__title { font-size: 0.65rem; font-weight: 700; color: var(--color-text-light); text-transform: uppercase; letter-spacing: 0.05em; }

/* ── Field table ── */
.dcv-table { width: 100%; border-collapse: collapse; font-size: 0.67rem; }
.dcv-table th { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-light); padding: 4px 6px; border-bottom: 1px solid var(--color-border); text-align: left; white-space: nowrap; }
.dcv-table td { padding: 4px 6px; border-bottom: 1px solid color-mix(in srgb, var(--color-border) 50%, transparent); vertical-align: top; }
.dcv-table tr:last-child td { border-bottom: none; }
.dcv-type-badge { font-size: 0.6rem; font-weight: 700; color: var(--ct,#aaa); background: color-mix(in srgb, var(--ct,#aaa) 12%, transparent); border: 1px solid color-mix(in srgb, var(--ct,#aaa) 30%, transparent); padding: 1px 4px; border-radius: 3px; white-space: nowrap; }
.dcv-mono { font-family: monospace; font-size: 0.7rem; font-weight: 600; color: var(--color-text); }
.dcv-type { color: var(--color-text-light); font-style: italic; }
.dcv-before-cell { color: rgba(250,82,82,.9); text-decoration: line-through; }
.dcv-after-cell  { color: #40c057; }
.dcv-reason { color: var(--color-text-light); font-size: 0.62rem; }

/* ── Value Object cards ── */
.dcv-vo-list { display: flex; flex-direction: column; gap: 4px; }
.dcv-vo-card { border: 1px solid color-mix(in srgb, var(--ct,var(--color-border)) 35%, var(--color-border)); border-radius: 4px; padding: 6px 8px; }
.dcv-vo-card__head { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.dcv-display-name { font-size: 0.62rem; color: var(--color-text-light); }
.dcv-vo-card__desc { font-size: 0.65rem; color: var(--color-text-light); margin-bottom: 4px; }
.dcv-vo-fields { display: flex; flex-wrap: wrap; gap: 4px; }
.dcv-vo-field { font-size: 0.63rem; background: var(--color-bg-tertiary); border: 1px solid var(--color-border); border-radius: 3px; padding: 1px 5px; color: var(--color-text); }
.dcv-vo-field em { color: var(--color-text-light); font-style: normal; }

/* ── Enum ── */
.dcv-enum-list { display: flex; flex-direction: column; gap: 4px; }
.dcv-enum-row  { display: flex; align-items: center; gap: 6px; font-size: 0.68rem; }
.dcv-enum-added   { color: #40c057; font-weight: 700; font-size: 0.65rem; }
.dcv-enum-removed { color: #fa5252; text-decoration: line-through; font-size: 0.65rem; }

/* ── Invariants ── */
.dcv-invariant-list { margin: 0; padding: 0 0 0 14px; font-size: 0.68rem; color: var(--color-text); line-height: 1.6; }

/* ── Text diff ── */
.dcv-text-diff { display: flex; gap: 0; }
.dcv-td-col   { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.dcv-td-label { font-size: 0.6rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; padding: 0 2px; }
.dcv-td-before .dcv-td-label { color: #fa5252; }
.dcv-td-after  .dcv-td-label { color: #40c057; }
.dcv-td-content { font-size: 0.67rem; background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 4px; padding: 6px 8px; white-space: pre-wrap; line-height: 1.5; max-height: 130px; overflow-y: auto; color: var(--color-text); }
.dcv-td-before .dcv-td-content { border-color: rgba(250,82,82,.2); background: rgba(250,82,82,.04); }
.dcv-td-after  .dcv-td-content { border-color: rgba(64,192,87,.2);  background: rgba(64,192,87,.04); }
.dcv-td-mid { display: flex; align-items: center; padding: 18px 8px 0; color: var(--color-text-light); font-size: 1rem; flex-shrink: 0; }

.dcv-section--desc .dcv-text-diff { margin-top: 0; }

/* ── Processing preview ── */
.dcv-processing-preview { margin-top: 6px; padding: 6px 8px; background: var(--color-bg-tertiary); border-radius: 4px; font-size: 0.67rem; color: var(--color-text-light); display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.dcv-pd-label { font-weight: 600; white-space: nowrap; }
.dcv-pd-text  { flex: 1; }
.dcv-pd-generating { display: flex; align-items: center; gap: 4px; white-space: nowrap; font-style: italic; }

/* ── CREATE 유형 노드 ── */
.dcv-check--create { color: #40c057; }
.dcv-node__sub--create { color: #40c057; }
.dcv-created-id { font-family: monospace; font-size: 0.6rem; opacity: 0.75; }
.dcv-create-badge {
  flex-shrink: 0;
  font-size: 0.58rem;
  font-weight: 700;
  color: #40c057;
  background: rgba(64, 192, 87, 0.12);
  border: 1px solid rgba(64, 192, 87, 0.35);
  padding: 1px 5px;
  border-radius: 3px;
}
.dcv-create-summary {
  background: rgba(64, 192, 87, 0.05);
  border: 1px solid rgba(64, 192, 87, 0.2);
  border-radius: 4px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.dcv-cs-title {
  font-size: 0.63rem;
  font-weight: 700;
  color: #40c057;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 2px;
}
.dcv-cs-row {
  display: flex;
  gap: 8px;
  font-size: 0.67rem;
  color: var(--color-text);
}
.dcv-cs-row--id {
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed var(--color-border);
  color: #228be6;
}
.dcv-cs-label {
  flex-shrink: 0;
  font-weight: 700;
  color: var(--color-text-light);
  min-width: 60px;
  font-size: 0.63rem;
}
.dcv-cs-empty { font-size: 0.67rem; color: var(--color-text-light); font-style: italic; }
.dcv-mono { font-family: monospace; font-size: 0.63rem; }

/* ── Empty ── */
.dcv-empty { padding: 24px; text-align: center; font-size: 0.72rem; color: var(--color-text-light); line-height: 1.8; }

/* ── Dialog (shared styles) ── */
.cp-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.cp-dialog  { background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 8px; width: 440px; max-width: 95vw; }
.cp-dialog--sm { width: 380px; }
.cp-dialog__header { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--color-border); font-size: 0.8rem; font-weight: 600; color: var(--color-text); }
.cp-dialog__close  { margin-left: auto; background: none; border: none; color: var(--color-text-light); cursor: pointer; font-size: 0.9rem; }
.cp-dialog__body   { padding: 16px; display: flex; flex-direction: column; gap: 4px; }
.cp-dialog__body p { font-size: 0.75rem; color: var(--color-text); margin: 0; }
.cp-dialog__footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--color-border); }
.tb-btn--danger { color: #fa5252; border-color: rgba(250,82,82,.4); }
.tb-btn--danger:hover { background: rgba(250,82,82,.08); }
</style>
