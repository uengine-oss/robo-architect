<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import { useDataRefresh } from '@/app/lifecycle/dataLifecycle'
import RequirementsTree from './RequirementsTree.vue'
import UserStoryDetail from './UserStoryDetail.vue'
import EpicDetail from './EpicDetail.vue'
import FeatureDetail from './FeatureDetail.vue'
import AddRequirementDialog from './AddRequirementDialog.vue'
import EpicEditForm from './EpicEditForm.vue'
import FeatureEditForm from './FeatureEditForm.vue'
import GeneratedStoriesReview from './GeneratedStoriesReview.vue'
import GeneratedFeaturesReview from './GeneratedFeaturesReview.vue'
import FeatureGenStream from './FeatureGenStream.vue'
import ValidationFindings from './ValidationFindings.vue'
import DeleteConfirmDialog from './DeleteConfirmDialog.vue'
import DeletionHistoryPanel from './DeletionHistoryPanel.vue'
import ChatEditPanel from './ChatEditPanel.vue'
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

// Epic → Feature 자동 생성 (034 — spec.md 단위)
const genFeatureResult = ref(null) // GenerateFeaturesResponse (검토 모달)
const genFeatureScopeName = ref('')
const genFeatureStreaming = ref(null) // { boundedContextId } — 리즈닝 스트림 패널

// DDD 검증 (034 US6)
const validating = ref(false)
const valResult = ref(null) // ValidateResponse
const valScopeName = ref('')

// Node clicked on the design-trace canvas → opens the property inspector.
const inspectedNode = ref(null)

// Resizable left tree pane (035 — draggable split).
const treeWidth = ref(320)
const isResizingTree = ref(false)
function startResizeTree(e) {
  isResizingTree.value = true
  e.preventDefault()
  document.addEventListener('mousemove', onResizeTree)
  document.addEventListener('mouseup', stopResizeTree)
}
function onResizeTree(e) {
  if (!isResizingTree.value) return
  treeWidth.value = Math.max(200, Math.min(window.innerWidth - 360, Math.round(e.clientX)))
  try {
    localStorage.setItem('requirements_tree_width', String(treeWidth.value))
  } catch {}
}
function stopResizeTree() {
  isResizingTree.value = false
  document.removeEventListener('mousemove', onResizeTree)
  document.removeEventListener('mouseup', stopResizeTree)
}

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
    const cw = Number(localStorage.getItem('requirements_chat_width'))
    if (Number.isFinite(cw) && cw >= 320) chatWidth.value = cw
    const tw = Number(localStorage.getItem('requirements_tree_width'))
    if (Number.isFinite(tw) && tw >= 200) treeWidth.value = tw
  } catch {}
})

onUnmounted(() => {
  stopResizeInspector()
  stopResizeChat()
  stopResizeTree()
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

// ── Conversational (chat) edit — right-docked split panel (035) ────────
// One Chat panel docked on the right, the same for Epic/Feature/User Story.
// Its target follows the currently selected tree item.
const chatOpen = ref(false)
const chatWidth = ref(420)
const isResizingChat = ref(false)

const chatTarget = computed(() => {
  const n = store.selectedNode
  if (n.type === 'epic' && store.selectedEpic) {
    const e = store.selectedEpic
    return {
      scope: 'epic', itemId: e.id, itemName: e.displayName || e.name,
      current: { name: e.displayName || e.name || '', description: e.description || '' },
    }
  }
  if (n.type === 'feature' && store.selectedFeature) {
    const f = store.selectedFeature
    return {
      scope: 'feature', itemId: f.id, itemName: f.name,
      current: {
        name: f.name || '', description: f.description || '',
        edgeCases: f.edgeCases || [], assumptions: f.assumptions || [],
      },
    }
  }
  if (store.selectedUserStory) {
    const us = store.selectedUserStory
    return {
      scope: 'user-story', itemId: us.id,
      itemName: `${us.role || ''}: ${us.action || ''}`,
      current: {
        role: us.role || '', action: us.action || '', benefit: us.benefit || '',
        priority: us.priority || 'medium', status: us.status || 'draft',
        acceptanceCriteria: (us.acceptanceCriteria || []).map((c) => c.name || c).filter(Boolean),
      },
    }
  }
  return null
})

function openChat() {
  chatOpen.value = true
}
function onChatEditApplied() {
  store.fetchTree()
}

function startResizeChat(e) {
  isResizingChat.value = true
  e.preventDefault()
  document.addEventListener('mousemove', onResizeChat)
  document.addEventListener('mouseup', stopResizeChat)
}
function onResizeChat(e) {
  if (!isResizingChat.value) return
  const next = Math.round(window.innerWidth - e.clientX)
  chatWidth.value = Math.max(320, Math.min(window.innerWidth - 240, next))
  try {
    localStorage.setItem('requirements_chat_width', String(chatWidth.value))
  } catch {}
}
function stopResizeChat() {
  isResizingChat.value = false
  document.removeEventListener('mousemove', onResizeChat)
  document.removeEventListener('mouseup', stopResizeChat)
}

// ── Recoverable delete (034) — confirm dialog + undo snackbar ───────────
const deleteTarget = ref(null) // { scope, id, name, hasChildren }
const undoToast = ref(null) // { batchId, label }
let undoTimer = null
const showDeletionHistory = ref(false)

function onDeleteFeature(feature) {
  deleteTarget.value = {
    scope: 'feature',
    id: feature.id,
    name: feature.name,
    hasChildren: (feature.userStories || []).length > 0,
  }
}
function onDeleteUserStory(us) {
  deleteTarget.value = {
    scope: 'user_story',
    id: us.id,
    name: `${us.role}: ${us.action}`,
    hasChildren: false,
  }
}
function onDeleteEpic(epic) {
  deleteTarget.value = {
    scope: 'epic',
    id: epic.id,
    name: epic.displayName || epic.name,
    hasChildren: (epic.features || []).length > 0,
  }
}

async function onConfirmDelete({ removeDesign, disposition }) {
  const t = deleteTarget.value
  deleteTarget.value = null
  try {
    let data
    if (t.scope === 'epic') data = await store.deleteEpic(t.id, removeDesign)
    else if (t.scope === 'feature') data = await store.deleteFeature(t.id, disposition, removeDesign)
    else data = await store.deleteUserStory(t.id, removeDesign)
    if (data?.restoreBatchId) showUndo(data.restoreBatchId, t.name)
  } catch (e) {
    window.alert(`삭제 실패: ${e}`)
  }
}

function showUndo(batchId, label) {
  undoToast.value = { batchId, label }
  if (undoTimer) clearTimeout(undoTimer)
  undoTimer = setTimeout(() => (undoToast.value = null), 8000)
}
async function onUndo() {
  const t = undoToast.value
  undoToast.value = null
  if (undoTimer) clearTimeout(undoTimer)
  try {
    await store.restoreDeletion(t.batchId)
  } catch (e) {
    window.alert(`복구 실패: ${e}`)
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

// ── Epic → Feature 자동 생성 (034 — 각 Feature = spec.md) ──────────────
function onGenerateFeatures() {
  const e = store.selectedEpic
  if (!store.selectedNode || store.selectedNode.type !== 'epic' || !e) return
  genFeatureScopeName.value = e.displayName || e.name || ''
  // 리즈닝 스트림 패널을 띄운다(블로킹 오버레이 대신). 완료 시 검토 모달로.
  genFeatureStreaming.value = { boundedContextId: e.id }
}

function onFeatureStreamDone({ boundedContextId, features }) {
  genFeatureStreaming.value = null
  if (features && features.length) {
    genFeatureResult.value = { boundedContextId, features }
  } else {
    window.alert('생성된 Feature가 없습니다. 다시 시도하거나 수동으로 추가하세요.')
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
      <button
        class="tb-btn"
        :class="{ 'tb-btn--active': chatOpen }"
        title="선택한 항목을 채팅으로 수정"
        @click="chatOpen = !chatOpen"
      >💬 Chat</button>
      <button class="tb-btn" @click="showDeletionHistory = true" title="삭제한 요구사항 복구">↩︎ 삭제 이력</button>
      <button class="tb-btn tb-btn--danger" @click="onClearData">데이터 삭제</button>
      <span v-if="store.loading" class="req-toolbar__status">불러오는 중...</span>
      <span v-else-if="store.error" class="req-toolbar__status error">{{ store.error }}</span>
    </div>

    <div class="req-body">
      <div class="req-tree-pane" :style="{ width: treeWidth + 'px' }">
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

      <!-- draggable split between tree and detail (035) -->
      <div
        class="req-tree-resizer"
        @mousedown="startResizeTree"
        title="드래그하여 트리 너비 조절"
      ></div>

      <!-- Epic detail (034 US2) -->
      <div v-if="store.selectedNode.type === 'epic'" class="req-detail-pane">
        <EpicDetail
          v-if="store.selectedEpic"
          :epic="store.selectedEpic"
          @edit="onEditEpic"
          @select-feature="onSelectFeature"
          @generate-features="onGenerateFeatures"
          @validate="onValidate('epic')"
          @clarify="onClarifyScope({ scopeType: 'bounded_context', scopeId: store.selectedEpic.id })"
          @delete="onDeleteEpic(store.selectedEpic)"
          @ai-edit="openChat"
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
          @clarify="onClarifyScope({ scopeType: 'feature', scopeId: store.selectedFeature.id })"
          @delete="onDeleteFeature(store.selectedFeature)"
          @ai-edit="openChat"
        />
      </div>

      <!-- User Story detail (default) — design-trace is a tab inside, not a
           cramped bottom split (035). -->
      <div v-else class="req-detail-pane">
        <UserStoryDetail
          :user-story="store.selectedUserStory"
          :trace="store.designTrace"
          :trace-loading="store.designTraceLoading"
          @delete="onDeleteUserStory"
          @ai-edit="openChat"
          @canvas-node-click="onCanvasNodeClick"
        />
      </div>

      <!-- Chat resizer / docked Chat panel (035) — right split, same for
           Epic/Feature/User Story; target follows the selected item. -->
      <div
        v-if="chatOpen"
        class="req-chat-resizer"
        @mousedown="startResizeChat"
        title="드래그하여 Chat 너비 조절"
      ></div>
      <div v-if="chatOpen" class="req-chat-pane" :style="{ width: chatWidth + 'px' }">
        <button class="req-chat-close" title="Chat 닫기" @click="chatOpen = false">×</button>
        <ChatEditPanel
          v-if="chatTarget"
          :key="chatTarget.scope + ':' + chatTarget.itemId"
          v-bind="chatTarget"
          @applied="onChatEditApplied"
        />
        <div v-else class="req-chat-empty">
          왼쪽 트리에서 Epic · Feature · User Story를 선택하면<br />여기에서 채팅으로 수정할 수 있습니다.
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
        <button class="req-inspector-close" title="속성 편집기 닫기" @click="closeInspector">×</button>
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

    <!-- 자동 생성 진행 (US5 하위 US / Epic→Feature) -->
    <div v-if="generating" class="gen-overlay">
      <div class="gen-box">✨ AI가 생성하는 중입니다…</div>
    </div>
    <GeneratedStoriesReview
      v-if="genResult"
      :result="genResult"
      :scope-name="genScopeName"
      @close="genResult = null"
      @confirmed="genResult = null"
    />
    <FeatureGenStream
      v-if="genFeatureStreaming"
      :bounded-context-id="genFeatureStreaming.boundedContextId"
      :scope-name="genFeatureScopeName"
      @done="onFeatureStreamDone"
      @close="genFeatureStreaming = null"
    />
    <GeneratedFeaturesReview
      v-if="genFeatureResult"
      :result="genFeatureResult"
      :scope-name="genFeatureScopeName"
      @close="genFeatureResult = null"
      @confirmed="genFeatureResult = null"
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

    <!-- 삭제 확인 (034 — recoverable) -->
    <DeleteConfirmDialog
      :target="deleteTarget"
      @confirm="onConfirmDelete"
      @cancel="deleteTarget = null"
    />

    <!-- 삭제 이력 / 복구 -->
    <DeletionHistoryPanel v-if="showDeletionHistory" @close="showDeletionHistory = false" />

    <!-- 실행취소 스낵바 -->
    <div v-if="undoToast" class="undo-snackbar">
      <span>🗑 <strong>{{ undoToast.label }}</strong> 삭제됨</span>
      <button class="undo-btn" @click="onUndo">되돌리기</button>
    </div>
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
.undo-snackbar {
  position: absolute; bottom: 18px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 14px; z-index: 2100;
  background: #2b2b2b; color: #fff; padding: 10px 16px; border-radius: 8px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35); font-size: 0.82rem;
}
.undo-btn {
  border: none; background: transparent; color: #74c0fc; cursor: pointer;
  font-weight: 700; font-size: 0.82rem;
}
.undo-btn:hover { text-decoration: underline; }
.tb-btn {
  padding: 4px 10px; border: 1px solid var(--color-border); border-radius: 5px;
  background: var(--color-bg-tertiary); color: var(--color-text);
  font-size: 0.74rem; cursor: pointer;
}
.tb-btn--primary { background: var(--color-accent); color: #fff; border-color: transparent; }
.tb-btn--danger { color: #e03131; }
.tb-btn--active { background: var(--color-accent); color: #fff; border-color: transparent; }
.tb-btn:hover { filter: brightness(1.1); }
.req-toolbar__status { font-size: 0.72rem; color: var(--color-text-light); }
.req-toolbar__status.error { color: #e03131; }
.req-body { flex: 1; display: flex; overflow: hidden; }
.req-tree-pane {
  flex-shrink: 0; border-right: 1px solid var(--color-border);
  overflow: hidden; display: flex; flex-direction: column;
}
.req-tree-resizer {
  width: 4px; cursor: col-resize; background: transparent; flex-shrink: 0; transition: background 0.2s ease;
}
.req-tree-resizer:hover { background: rgba(34, 139, 230, 0.3); }
.req-detail-pane { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
.req-detail-pane__top { flex: 0 0 45%; overflow-y: auto; border-bottom: 1px solid var(--color-border); }
.req-detail-pane__canvas { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
/* Right-docked Chat split (035) */
.req-chat-pane {
  position: relative; flex-shrink: 0; border-left: 1px solid var(--color-border);
  overflow: hidden; display: flex; flex-direction: column; background: var(--color-bg-secondary);
}
.req-chat-resizer {
  width: 4px; cursor: col-resize; background: transparent; flex-shrink: 0; transition: background 0.2s ease;
}
.req-chat-resizer:hover { background: rgba(34, 139, 230, 0.3); }
.req-chat-close {
  position: absolute; top: 8px; right: 10px; z-index: 5;
  border: none; background: transparent; color: var(--color-text-light);
  font-size: 1.1rem; cursor: pointer; line-height: 1;
}
.req-chat-close:hover { color: var(--color-text); }
.req-chat-empty {
  flex: 1; display: flex; align-items: center; justify-content: center; text-align: center;
  padding: 20px; font-size: 0.82rem; color: var(--color-text-light); line-height: 1.6;
}
.canvas-label {
  font-size: 0.7rem; font-weight: 700; color: var(--color-text-light);
  padding: 4px 10px; background: var(--color-bg-tertiary);
}
.canvas-hint { font-weight: 400; opacity: 0.7; }
.req-inspector-pane {
  position: relative; flex-shrink: 0; border-left: 1px solid var(--color-border);
  overflow: hidden; display: flex; flex-direction: column;
}
.req-inspector-close {
  position: absolute; top: 10px; right: 12px; z-index: 6;
  border: none; background: transparent; color: var(--color-text-light);
  font-size: 1.2rem; line-height: 1; cursor: pointer;
}
.req-inspector-close:hover { color: var(--color-text); }
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
