<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import { useDataRefresh } from '@/app/lifecycle/dataLifecycle'
import RequirementsTree from './RequirementsTree.vue'
import UserStoryDetail from './UserStoryDetail.vue'
import EpicDetail from './EpicDetail.vue'
import FeatureDetail from './FeatureDetail.vue'
import DesignTraceCanvas from './DesignTraceCanvas.vue'
import AddRequirementDialog from './AddRequirementDialog.vue'
import EpicEditForm from './EpicEditForm.vue'
import FeatureEditForm from './FeatureEditForm.vue'
import GeneratedStoriesReview from './GeneratedStoriesReview.vue'
import ValidationFindings from './ValidationFindings.vue'
import ImpactReportPanel from './ImpactReportPanel.vue'
import RequirementsIngestionModal from '@/features/requirementsIngestion/ui/RequirementsIngestionModal.vue'
import InspectorPanel from '@/features/canvas/ui/InspectorPanel.vue'

/**
 * Requirements tab root panel (026).
 * Self-contained: its own left tree, story detail, embedded design-trace
 * canvas, requirement authoring, and non-blocking impact report.
 */
const store = useRequirementsStore()

// Reload the requirements tree whenever an ingestion completes or data is cleared.
useDataRefresh(() => {
  store.fetchTree()
  store.fetchClarificationFlags()
  store.fetchClarityScores()
})

const showAddDialog = ref(false)
const showIngestionModal = ref(false)

// Epic/Feature edit dialogs (034 US3)
const editingEpic = ref(null)
const editingFeature = ref(null)

// 하위 US 자동 생성 (034 US5)
const generating = ref(false)
const genResult = ref(null) // GenerateChildStoriesResponse
const genScopeName = ref('')

// DDD 검증 (034 US6)
const validating = ref(false)
const valResult = ref(null) // ValidateResponse
const valScopeName = ref('')

// Node clicked on the design-trace canvas → opens the property inspector.
const inspectedNode = ref(null)

// Resizable inspector pane — same drag behaviour as the Design tab panels.
const inspectorWidth = ref(380)
const isResizingInspector = ref(false)

function startResizeInspector(e) {
  isResizingInspector.value = true
  e.preventDefault()
  document.addEventListener('mousemove', onResizeInspector)
  document.addEventListener('mouseup', stopResizeInspector)
}

function onResizeInspector(e) {
  if (!isResizingInspector.value) return
  const next = Math.round(window.innerWidth - e.clientX)
  inspectorWidth.value = Math.max(280, Math.min(window.innerWidth - 200, next))
  try {
    localStorage.setItem('requirements_inspector_width', String(inspectorWidth.value))
  } catch {}
}

function stopResizeInspector() {
  isResizingInspector.value = false
  document.removeEventListener('mousemove', onResizeInspector)
  document.removeEventListener('mouseup', stopResizeInspector)
}

onMounted(() => {
  store.fetchTree()
  store.fetchClarificationFlags()
  store.fetchClarityScores()
  try {
    const v = Number(localStorage.getItem('requirements_inspector_width'))
    if (Number.isFinite(v) && v >= 280) inspectorWidth.value = v
  } catch {}
})

onUnmounted(() => {
  stopResizeInspector()
})

function onSelect(usId) {
  store.selectUserStory(usId)
  inspectedNode.value = null
}

function onSelectEpic(id) {
  store.selectEpic(id)
  inspectedNode.value = null
}

function onSelectFeature(id) {
  store.selectFeature(id)
  inspectedNode.value = null
}

function onCanvasNodeClick(node) {
  inspectedNode.value = node
}

function closeInspector() {
  inspectedNode.value = null
}

async function onMove({ userStoryId, targetFeatureId }) {
  try {
    await store.moveUserStory(userStoryId, targetFeatureId)
  } catch (e) {
    window.alert(`이동 실패: ${e}`)
  }
}

async function onDeleteFeature(feature) {
  if (!window.confirm(`Feature '${feature.name}'를 삭제할까요?`)) return
  const withChildren = window.confirm(
    '하위 User Story도 함께 삭제할까요?\n확인 = 함께 삭제 / 취소 = 미분류로 이동',
  )
  try {
    await store.deleteFeature(feature.id, withChildren ? 'delete' : 'unassign')
  } catch (e) {
    window.alert(`삭제 실패: ${e}`)
  }
}

async function onDeleteUserStory(us) {
  if (!window.confirm(`User Story '${us.role}: ${us.action}'를 삭제할까요?`)) return
  try {
    await store.deleteUserStory(us.id)
  } catch (e) {
    window.alert(`삭제 실패: ${e}`)
  }
}

async function onClearData() {
  if (!window.confirm('모든 요구사항 데이터를 삭제합니다. 계속할까요?')) return
  try {
    await store.clearAllData()
  } catch (e) {
    window.alert(`데이터 삭제 실패: ${e}`)
  }
}

function onIngestionComplete() {
  store.fetchTree()
}

// ── Clarification (spec 030) ───────────────────────────────────────────
// Scope-level (Project / BoundedContext / Feature) clarification: kick a
// session and surface its flags as tree badges. Per-UserStory clarification
// lives inside UserStoryDetail's "명확화" tab — no overlay needed here.
async function onClarifyScope({ scopeType, scopeId }) {
  try {
    await store.startClarification(scopeType, scopeId)
  } catch (e) {
    window.alert(`요구사항 명확화 시작 실패: ${e?.message || e}`)
  }
}

// ── Epic/Feature edit (034 US3) ────────────────────────────────────────
function onEditEpic(epic) {
  editingFeature.value = null
  editingEpic.value = epic
}
function onEditFeature(feature) {
  editingEpic.value = null
  editingFeature.value = feature
}

// ── 하위 User Story 자동 생성 (034 US5) ────────────────────────────────
async function onGenerateStories(scopeType) {
  const node = store.selectedNode
  if (!node || (node.type !== 'epic' && node.type !== 'feature')) return
  genScopeName.value =
    node.type === 'epic'
      ? store.selectedEpic?.displayName || store.selectedEpic?.name || ''
      : store.selectedFeature?.name || ''
  // claude-ide 엔진 선택 시 로컬 도구 설치를 먼저 점검 (US5)
  if (store.generationEngine === 'claude-ide') {
    try {
      const t = await store.checkLocalTooling()
      if (t.missing && t.missing.length) {
        window.alert(t.installHint || '로컬 Claude/speckit이 설치되어 있지 않습니다.')
        return
      }
      // 설치되어 있으면 진행. (Claude IDE 헤드리스 생성은 준비 중 —
      // 현재는 in-process 엔진으로 후보를 생성합니다.)
    } catch {
      /* 점검 실패 시 in-process로 폴백 */
    }
  }
  generating.value = true
  try {
    genResult.value = await store.generateChildStories(node.type, node.id)
  } catch (e) {
    window.alert(`자동 생성 실패: ${e?.message || e}`)
  } finally {
    generating.value = false
  }
}

// ── DDD 적합성 검증 (034 US6) ──────────────────────────────────────────
async function onValidate(targetType) {
  if (targetType === 'feature' && store.selectedFeature) {
    const f = store.selectedFeature
    valScopeName.value = f.name
    await runValidate({
      targetType: 'feature',
      name: f.name,
      description: f.description || '',
      boundedContextId: f.boundedContextId || undefined,
      featureId: f.id,
    })
  } else if (targetType === 'epic' && store.selectedEpic) {
    const e = store.selectedEpic
    valScopeName.value = e.displayName || e.name
    await runValidate({
      targetType: 'epic',
      name: e.displayName || e.name,
      description: e.description || '',
      boundedContextId: e.id,
    })
  }
}

async function runValidate(payload) {
  validating.value = true
  try {
    valResult.value = await store.validateRequirement(payload)
  } catch (e) {
    window.alert(`검증 실패: ${e?.message || e}`)
  } finally {
    validating.value = false
  }
}
</script>

<template>
  <div class="requirements-panel">
    <div class="req-toolbar">
      <span class="req-toolbar__title">Requirements</span>
      <button class="tb-btn tb-btn--primary" @click="showAddDialog = true">+ 요구사항 추가</button>
      <button class="tb-btn" @click="showIngestionModal = true">문서 업로드</button>
      <button
        class="tb-btn"
        @click="onClarifyScope({ scopeType: 'project', scopeId: '*' })"
      >🔍 요구사항 명확화 (전체)</button>
      <button class="tb-btn tb-btn--danger" @click="onClearData">데이터 삭제</button>
      <span v-if="store.loading" class="req-toolbar__status">불러오는 중...</span>
      <span v-else-if="store.error" class="req-toolbar__status error">{{ store.error }}</span>
    </div>

    <div class="req-body">
      <div class="req-tree-pane">
        <RequirementsTree
          :tree="store.tree"
          :selected-id="store.selectedUserStoryId"
          @select="onSelect"
          @select-epic="onSelectEpic"
          @select-feature="onSelectFeature"
          @move="onMove"
          @delete-feature="onDeleteFeature"
          @delete-user-story="onDeleteUserStory"
          @clarify-scope="onClarifyScope"
          @edit-epic="onEditEpic"
          @edit-feature="onEditFeature"
        />
      </div>

      <!-- Epic detail (034 US2) -->
      <div v-if="store.selectedNode.type === 'epic'" class="req-detail-pane">
        <EpicDetail
          v-if="store.selectedEpic"
          :epic="store.selectedEpic"
          @edit="onEditEpic"
          @select-feature="onSelectFeature"
          @generate-stories="onGenerateStories('epic')"
          @validate="onValidate('epic')"
        />
      </div>

      <!-- Feature detail (034 US2) -->
      <div v-else-if="store.selectedNode.type === 'feature'" class="req-detail-pane">
        <FeatureDetail
          v-if="store.selectedFeature"
          :feature="store.selectedFeature"
          @edit="onEditFeature"
          @select-user-story="onSelect"
          @generate-stories="onGenerateStories('feature')"
          @validate="onValidate('feature')"
        />
      </div>

      <!-- User Story detail + design-trace canvas (default) -->
      <div v-else class="req-detail-pane">
        <div class="req-detail-pane__top">
          <UserStoryDetail :user-story="store.selectedUserStory" />
        </div>
        <div class="req-detail-pane__canvas">
          <div class="canvas-label">
            설계 괘적
            <span class="canvas-hint">— 노드를 클릭하면 우측에 속성 편집기가 열립니다</span>
          </div>
          <DesignTraceCanvas
            :trace="store.designTrace"
            :loading="store.designTraceLoading"
            @node-click="onCanvasNodeClick"
          />
        </div>
      </div>

      <!-- Resizer — drag to resize the inspector pane (hover only) -->
      <div
        v-if="inspectedNode"
        class="req-inspector-resizer"
        @mousedown="startResizeInspector"
        title="드래그하여 패널 너비 조절"
      ></div>

      <!-- Property inspector — opens when a canvas node is clicked -->
      <div
        v-if="inspectedNode"
        class="req-inspector-pane"
        :style="{ width: inspectorWidth + 'px' }"
      >
        <InspectorPanel
          :key="inspectedNode.id"
          :node-id="inspectedNode.id"
          initial-tab="properties"
          @close="closeInspector"
          @updated="() => {}"
          @request-chat="() => {}"
        />
      </div>
    </div>

    <ImpactReportPanel :report="store.impactReport" @dismiss="store.dismissImpactReport" />

    <AddRequirementDialog v-model="showAddDialog" @added="store.fetchTree()" />
    <RequirementsIngestionModal v-model="showIngestionModal" @complete="onIngestionComplete" />

    <EpicEditForm
      v-if="editingEpic"
      :epic="editingEpic"
      @close="editingEpic = null"
      @saved="editingEpic = null"
    />
    <FeatureEditForm
      v-if="editingFeature"
      :feature="editingFeature"
      @close="editingFeature = null"
      @saved="editingFeature = null"
    />

    <!-- 하위 US 자동 생성 (034 US5) -->
    <div v-if="generating" class="gen-overlay">
      <div class="gen-box">✨ AI가 하위 User Story를 생성하는 중입니다…</div>
    </div>
    <GeneratedStoriesReview
      v-if="genResult"
      :result="genResult"
      :scope-name="genScopeName"
      @close="genResult = null"
      @confirmed="genResult = null"
    />

    <!-- DDD 적합성 검증 (034 US6) -->
    <div v-if="validating" class="gen-overlay">
      <div class="gen-box">🔎 DDD 적합성을 검증하는 중입니다…</div>
    </div>
    <ValidationFindings
      v-if="valResult"
      :result="valResult"
      :scope-name="valScopeName"
      @close="valResult = null"
    />
  </div>
</template>

<style scoped>
.requirements-panel {
  position: relative; display: flex; flex-direction: column;
  width: 100%; height: 100%; overflow: hidden;
}
.req-toolbar {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  border-bottom: 1px solid var(--color-border); flex-shrink: 0;
}
.req-toolbar__title { font-weight: 700; font-size: 0.85rem; margin-right: 8px; }
.tb-btn {
  padding: 4px 10px; border: 1px solid var(--color-border); border-radius: 5px;
  background: var(--color-bg-tertiary); color: var(--color-text);
  font-size: 0.74rem; cursor: pointer;
}
.tb-btn--primary { background: var(--color-accent); color: #fff; border-color: transparent; }
.tb-btn--danger { color: #e03131; }
.tb-btn:hover { filter: brightness(1.1); }
.req-toolbar__status { font-size: 0.72rem; color: var(--color-text-light); }
.req-toolbar__status.error { color: #e03131; }
.req-body { flex: 1; display: flex; overflow: hidden; }
.req-tree-pane {
  width: 320px; flex-shrink: 0; border-right: 1px solid var(--color-border);
  overflow: hidden; display: flex; flex-direction: column;
}
.req-detail-pane { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.req-detail-pane__top { flex: 0 0 45%; overflow-y: auto; border-bottom: 1px solid var(--color-border); }
.req-detail-pane__canvas { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.canvas-label {
  font-size: 0.7rem; font-weight: 700; color: var(--color-text-light);
  padding: 4px 10px; background: var(--color-bg-tertiary);
}
.canvas-hint { font-weight: 400; opacity: 0.7; }
.req-inspector-pane {
  flex-shrink: 0; border-left: 1px solid var(--color-border);
  overflow: hidden; display: flex; flex-direction: column;
}
.req-inspector-resizer {
  width: 4px; cursor: col-resize; background: transparent;
  flex-shrink: 0; transition: background 0.2s ease;
}
.req-inspector-resizer:hover {
  background: rgba(34, 139, 230, 0.3);
}
.gen-overlay {
  position: fixed; inset: 0; z-index: 1100; background: rgba(0, 0, 0, 0.45);
  display: flex; align-items: center; justify-content: center;
}
.gen-box {
  background: var(--color-bg-secondary); color: var(--color-text);
  padding: 18px 26px; border-radius: 10px; font-size: 0.9rem;
  border: 1px solid var(--color-border);
}
</style>
