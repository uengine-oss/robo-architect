<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import RequirementsTree from './RequirementsTree.vue'
import UserStoryDetail from './UserStoryDetail.vue'
import DesignTraceCanvas from './DesignTraceCanvas.vue'
import AddRequirementDialog from './AddRequirementDialog.vue'
import ImpactReportPanel from './ImpactReportPanel.vue'
import RequirementsIngestionModal from '@/features/requirementsIngestion/ui/RequirementsIngestionModal.vue'
import InspectorPanel from '@/features/canvas/ui/InspectorPanel.vue'

/**
 * Requirements tab root panel (026).
 * Self-contained: its own left tree, story detail, embedded design-trace
 * canvas, requirement authoring, and non-blocking impact report.
 */
const store = useRequirementsStore()

const showAddDialog = ref(false)
const showIngestionModal = ref(false)

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
</script>

<template>
  <div class="requirements-panel">
    <div class="req-toolbar">
      <span class="req-toolbar__title">Requirements</span>
      <button class="tb-btn tb-btn--primary" @click="showAddDialog = true">+ 요구사항 추가</button>
      <button class="tb-btn" @click="showIngestionModal = true">문서 업로드</button>
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
          @move="onMove"
          @delete-feature="onDeleteFeature"
          @delete-user-story="onDeleteUserStory"
        />
      </div>

      <div class="req-detail-pane">
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
</style>
