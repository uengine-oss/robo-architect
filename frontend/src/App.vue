<script setup>
import { onMounted, onUnmounted, ref, computed, markRaw, provide, watch, nextTick } from 'vue'
import TopBar from '@/app/layout/TopBar.vue'
import NavigatorPanel from '@/features/navigator/ui/NavigatorPanel.vue'
import CanvasWorkspace from '@/features/canvas/ui/CanvasWorkspace.vue'
// 043 — 'Big picture' 뷰 비활성화: import 제거(파일은 보존).
// import BigPicturePanel from '@/features/canvas/ui/BigPicturePanel.vue'
import AggregatePanel from '@/features/canvas/ui/AggregatePanel.vue'
import EventModelingPanel from '@/features/eventModeling/ui/EventModelingPanel.vue'
import RequirementsPanel from '@/features/requirements/ui/RequirementsPanel.vue'
import ChangesRootPanel from '@/features/requirements/ui/ChangesRootPanel.vue'
import ProposalsPanel from '@/features/proposals/ui/ProposalsPanel.vue'
import ClaudeCodeWorkspace from '@/features/claudeCode/ui/ClaudeCodeWorkspace.vue'
import BpmnPanel from '@/features/canvas/ui/BpmnPanel.vue'
// Analysis 탭 — robo-analyzer-frontend 를 Module Federation 으로 끼우는 래퍼.
import AnalysisPanel from '@/features/analysis/ui/AnalysisPanel.vue'
import { useNavigatorStore } from '@/features/navigator/navigator.store'
import { useThemeStore } from '@/app/theme.store'
import { useBpmnStore } from '@/features/canvas/bpmn.store'
// 040 — Proposal 임팩트 미리보기 오케스트레이션(앱 셸). 뷰어 스토어는 proposals 를
// 모르고, App 이 robo:open-preview 를 수신해 탭 전환 + preview 진입 + 포커스를 조율한다.
import { useAggregateViewerStore } from '@/features/canvas/aggregateViewer.store'
import { useEventModelingStore } from '@/features/eventModeling/eventModeling.store'
// 043-fix — Command/Event 미리보기를 Design 캔버스에 투영(begin/endPreview) + 진입 요청 브리지.
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useCanvasPreviewRequestStore } from '@/features/canvas/canvasPreviewRequest.store'
import { enterPreview, exitPreview } from '@/app/previewSession'
import PreviewBanner from '@/app/ui/PreviewBanner.vue'
import { createLogger, newOpId } from '@/app/logging/logger'
// 032: desktop launcher gate — when running inside Electron the launcher
// view is shown until the user picks (Neo4j connection, project root) and
// the session identity is established. Web mode bypasses (session.entered
// starts true) so this gate is transparent to the existing SPA deployment.
import LauncherView from '@/features/desktop-launcher/LauncherView.vue'
import { useSessionStore } from '@/features/desktop-launcher/stores/session-store.js'
// 034 US7 — 설계 미반영 User Story 식별 + 반영 프롬프트.
import DesignReflectPrompt from '@/features/requirements/ui/DesignReflectPrompt.vue'
import RequirementsIngestionModal from '@/features/requirementsIngestion/ui/RequirementsIngestionModal.vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

const navigatorStore = useNavigatorStore()
const themeStore = useThemeStore() // Initialize theme store
const bpmnStore = useBpmnStore()
const session = useSessionStore()

// Tab state management
const activeTab = ref('Stories')

// Claude Code workdir state — hydrated from localStorage so the inspector's
// source viewer (feature 029) can resolve ImplementationFile paths even
// when the user hasn't visited the Claude Code tab this session.
const claudeCodeWorkdir = ref((() => {
  try { return localStorage.getItem('claude_code_workspace_root') || '' } catch { return '' }
})())

// Provide activeTab and Claude Code controls to child components
provide('activeTab', activeTab)
// 029 — InspectorPanel needs the workspace root to render source files
// attached to design elements via [:IMPLEMENTED_IN]. Provide the ref so
// the value stays reactive when the user picks a new project home.
provide('claudeCodeWorkdir', claudeCodeWorkdir)
provide('openClaudeCode', (workdir, command = null, opts = {}) => {
  // 멀티 세션(039): proposal worktree는 독립 세션으로 열고, claudeCodeWorkdir(메인
  // 프로젝트 루트 = 새 proposal의 기본 projectRoot)는 건드리지 않는다.
  // 메인 프로젝트 흐름(Changes/Inspector/마법사)만 claudeCodeWorkdir를 갱신한다.
  const nextWorkdir = workdir || ''
  const isProposal = !!opts.proposalId
  if (!isProposal) {
    claudeCodeWorkdir.value = nextWorkdir
  }
  activeTab.value = 'Code'
  // Dispatch a custom event that ClaudeCodeWorkspace listens for.
  // Using CustomEvent bypasses the KeepAlive/dynamic-component ref issue.
  nextTick(() => {
    window.dispatchEvent(new CustomEvent('claude-terminal-open', {
      detail: {
        workdir: nextWorkdir,
        command: command || null,
        label: opts.label || opts.proposalId || null,
        proposalId: opts.proposalId || null,
        kind: isProposal ? 'proposal' : 'main',
        // 재구현: 기존 세션을 종료하고 새 셀로 다시 시작.
        restart: !!opts.restart,
      },
    }))
  })
})

// Map tab names to components
// 043 — 'Big picture' 비활성화(탭 매핑 제거). 'Process'(BPM)·'Processes'(Event Modeling)는
// 상단에선 하나의 'Process' 탭(서브토글)로 보이되 activeTab 값은 둘 유지 → 네비/캔버스/상단바
// 등 activeTab 기준 동작이 그대로 전환된다(TopBar 서브토글이 'Process'⇄'Processes'로 바꿈).
const tabComponents = {
  'Analysis': markRaw(AnalysisPanel),
  'Changes': markRaw(ChangesRootPanel),
  'Proposals': markRaw(ProposalsPanel),
  'Stories': markRaw(RequirementsPanel),
  'Process': markRaw(BpmnPanel),
  'Processes': markRaw(EventModelingPanel),
  'Design': markRaw(CanvasWorkspace),
  'Data': markRaw(AggregatePanel),
  'Code': markRaw(ClaudeCodeWorkspace),
  // 하위 호환 (내부 이벤트가 구 이름을 dispatch하는 경우)
  'Event Modeling': markRaw(EventModelingPanel),
  'Requirements': markRaw(RequirementsPanel),
  'Aggregate': markRaw(AggregatePanel),
}

// Cross-component tab switching (HybridEventStormingPanel → Event Modeling)
function _onSwitchTab(e) {
  const target = e?.detail
  if (typeof target === 'string' && tabComponents[target]) {
    activeTab.value = target
  }
}

// 040 — Proposal 임팩트 '열기' 오케스트레이션.
const aggregateViewer = useAggregateViewerStore()
const eventModeling = useEventModelingStore()
// 043-fix — Design 캔버스 미리보기.
const canvasStore = useCanvasStore()
const canvasPreviewRequest = useCanvasPreviewRequestStore()
const VIEWER_TO_TAB_LOCAL = { data: 'Data', design: 'Design', process: 'Process', processes: 'Processes' }

// nodeLabel → eventModeling selectItem 타입.
function _emTypeFromLabel(label) {
  const map = { ReadModel: 'readmodel', Event: 'event', Command: 'command', UI: 'ui', Journey: 'event', EventModel: 'event' }
  return map[label] || null
}

async function _onOpenPreview(e) {
  const d = e?.detail
  if (!d || !d.viewer) return
  const tab = VIEWER_TO_TAB_LOCAL[d.viewer]
  if (!tab) return

  // 미리보기 세션 진입(앱 셸 상태) — 뷰어 스토어 fetch 가 preview 소스로 분기된다.
  enterPreview({
    proposalId: d.proposalId,
    viewer: d.viewer,
    baseUrl: `/api/proposals/${d.proposalId}/preview`,
    label: d.label || d.proposalId,
    title: d.title || '',
    targetNodeId: d.targetNodeId || null,
    bcId: d.bcId || null,
    notice: d.notice || null,
  })

  activeTab.value = tab
  await nextTick()

  if (d.viewer === 'data') {
    // 라이브 상태 스냅샷 후 비우고(격리), preview 소스에서 오버레이 포커스 적재.
    // Data 뷰어는 Aggregate 단위로 포커스한다. Command/Event/VO 대상이면 targetNodeId 는
    // 자식 id 라 fetchAggregate 가 트리에서 못 찾으므로, 백엔드가 해소한 소유 Aggregate id 로
    // 포커스한다(없으면 targetNodeId fallback — Aggregate 대상은 둘이 동일).
    aggregateViewer.beginPreview()
    aggregateViewer.focusAggregate(d.aggregateId || d.targetNodeId, d.bcId)
  } else if (d.viewer === 'processes') {
    // 라이브 이벤트모델을 읽기 전용으로 로드 후 대상 노드 포커스(US3-2).
    try { await eventModeling.fetchEventModeling() } catch { /* best-effort */ }
    try {
      const t = _emTypeFromLabel(d.nodeLabel)
      if (t && d.targetNodeId) await eventModeling.selectItem(d.targetNodeId, t)
    } catch { /* best-effort focus */ }
  } else if (d.viewer === 'design' && d.bcId && d.targetNodeId) {
    // 043-fix — Command/Event 는 소속 BC 그래프를 Design 캔버스에 투영(오버레이)해 대상
    // 노드 포커스 + 인스펙터를 연다. CanvasWorkspace 가 이 요청을 소비(fetch→begin/대체→포커스).
    canvasPreviewRequest.request({
      proposalId: d.proposalId,
      bcId: d.bcId,
      targetNodeId: d.targetNodeId,
      nodeLabel: d.nodeLabel || '',
      title: d.title || '',
    })
  }
  // 그 외 design/process(UI/Screen 등): 라이브 뷰어를 읽기 전용 맥락으로 연다(인텐트가 신규
  // 생성하는 일이 드물어 오버레이 없음 — research D5). 탭 전환 + 배너 + mutation 가드로 충분.
}

function _onOpenPreviewFailed(e) {
  const d = e?.detail
  if (!d) return
  window.alert(`열기 불가: ${d.reason || '미리보기로 표현할 수 없는 항목입니다.'}`)
}

// 배너 '닫기' → 미리보기 종료 시 뷰어 라이브 상태 복원(US2 잔존물 0).
function _onPreviewExit(e) {
  const viewer = e?.detail?.viewer
  if (viewer === 'data') aggregateViewer.endPreview()
  // 043-fix — Design 캔버스도 스냅샷 복원(잔존물 0).
  else if (viewer === 'design') canvasStore.endPreview()
}

// 040 — Chat 편집(modelModifier)이 제안 diff 에 반영된 뒤 갱신 트리를 뷰어에 적용.
function _onPreviewUpdated(e) {
  const tree = e?.detail?.tree
  if (tree) aggregateViewer.applyPreviewTree(tree)
}

const currentComponent = computed(() => tabComponents[activeTab.value])

// 034 US7 — Event Modeling / Design 탭 진입 시 설계 미반영 User Story를 감지해
// "설계에 반영하시겠습니까?" 프롬프트를 띄운다. (생성 오케스트레이션은 후속.)
const requirementsStore = useRequirementsStore()
const designPending = ref(null) // PendingUS[] | null
const suppressDesignPrompt = ref(false) // 이번 세션 동안 묻지 않기
// 034 US7 — 설계 갭 메우기를 기존 인제스천 진행 UI로 표시.
const designIngestModalOpen = ref(false)
const designIngestSessionId = ref('')
watch(activeTab, async (tab) => {
  if (tab !== 'Processes' && tab !== 'Event Modeling' && tab !== 'Design') return
  if (suppressDesignPrompt.value || designPending.value || designIngestModalOpen.value) return
  try {
    const res = await requirementsStore.fetchPendingDesign()
    if (res?.pending?.length) designPending.value = res.pending
  } catch {
    /* advisory only — never block tab navigation */
  }
})
async function onDesignReflectConfirm() {
  const ids = (designPending.value || []).map((p) => p.userStoryId)
  designPending.value = null
  if (!ids.length) return
  try {
    // 기존 인제스천 설계 단계(events→aggregate→command→readmodel)를 이 US들에 실행.
    const { session_id } = await requirementsStore.requestDesignForUserStories(ids)
    // 기존 인제스천 진행 다이얼로그 + SSE 루프를 그대로 재사용해 진행 표시.
    designIngestSessionId.value = session_id
    designIngestModalOpen.value = true
  } catch (e) {
    window.alert(`설계 반영 시작 실패: ${e?.message || e}`)
  }
}
function onDesignReflectDismiss() {
  designPending.value = null
}
function onDesignReflectDontAsk() {
  suppressDesignPrompt.value = true
  designPending.value = null
}

// Navigator panel resize state
const navigatorWidth = ref(320)
const isResizingNavigator = ref(false)
const isNavigatorCollapsed = ref(false)
const savedNavigatorWidth = ref(320) // Store width when collapsing

function startResizeNavigator(e) {
  isResizingNavigator.value = true
  e.preventDefault()
  document.addEventListener('mousemove', onResizeNavigator)
  document.addEventListener('mouseup', stopResizeNavigator)
}

function onResizeNavigator(e) {
  if (!isResizingNavigator.value) return
  const next = Math.round(e.clientX)
  navigatorWidth.value = Math.max(200, Math.min(500, next))
  try {
    localStorage.setItem('navigator_panel_width', String(navigatorWidth.value))
  } catch {}
}

function stopResizeNavigator() {
  isResizingNavigator.value = false
  document.removeEventListener('mousemove', onResizeNavigator)
  document.removeEventListener('mouseup', stopResizeNavigator)
}

function toggleNavigator() {
  if (isNavigatorCollapsed.value) {
    // Expand: restore saved width
    navigatorWidth.value = savedNavigatorWidth.value
    isNavigatorCollapsed.value = false
  } else {
    // Collapse: save current width and set to 0
    savedNavigatorWidth.value = navigatorWidth.value
    navigatorWidth.value = 0
    isNavigatorCollapsed.value = true
  }
  try {
    localStorage.setItem('navigator_collapsed', String(isNavigatorCollapsed.value))
    localStorage.setItem('navigator_panel_width', String(savedNavigatorWidth.value))
  } catch {}
}

const log = createLogger({ scope: 'App' })
const appInstanceId = newOpId('app')

function getNavigatorSnapshot() {
  return {
    contextsCount: navigatorStore.contexts?.length ?? 0,
    unassignedUserStoriesCount: navigatorStore.userStories?.length ?? 0,
    contextTreesCount: navigatorStore.contextTrees ? Object.keys(navigatorStore.contextTrees).length : 0,
    navigatorLoading: !!navigatorStore.loading,
    navigatorError: navigatorStore.error ?? null
  }
}


onMounted(() => {
  // Load saved navigator width and collapsed state
  try {
    const v = Number(localStorage.getItem('navigator_panel_width'))
    if (Number.isFinite(v) && v >= 200) {
      savedNavigatorWidth.value = v
      navigatorWidth.value = v
    }
    const collapsed = localStorage.getItem('navigator_collapsed')
    if (collapsed === 'true') {
      isNavigatorCollapsed.value = true
      navigatorWidth.value = 0
    }
  } catch {}

  // Rehydrate hybrid session at the app level so BPMN canvas is ready the
  // moment the BPMN tab mounts (regardless of which tab the user refreshes on).
  if (bpmnStore.hybridSessionId) {
    bpmnStore.rehydrateHybrid().catch(() => { /* best-effort */ })
  }

  // Listen for cross-component tab switch requests
  window.addEventListener('robo:switch-tab', _onSwitchTab)
  // 040 — Proposal 임팩트 미리보기 열기/실패/종료
  window.addEventListener('robo:open-preview', _onOpenPreview)
  window.addEventListener('robo:open-preview-failed', _onOpenPreviewFailed)
  window.addEventListener('robo:preview-exit', _onPreviewExit)
  window.addEventListener('robo:preview-updated', _onPreviewUpdated)

  log.info('app_mounted', 'App mounted; core layout components are ready.', {
    appInstanceId,
    envMode: (() => {
      try { return import.meta?.env?.MODE } catch { return undefined }
    })(),
    initial: {
      navigator: getNavigatorSnapshot()
    }
  })
})

onUnmounted(() => {
  stopResizeNavigator()
  window.removeEventListener('robo:switch-tab', _onSwitchTab)
  window.removeEventListener('robo:open-preview', _onOpenPreview)
  window.removeEventListener('robo:open-preview-failed', _onOpenPreviewFailed)
  window.removeEventListener('robo:preview-exit', _onPreviewExit)
  window.removeEventListener('robo:preview-updated', _onPreviewUpdated)
})
</script>

<template>
  <!-- 032: launcher gate. In Electron mode, block the rest of the app until
       the user has completed the launcher hand-off (connection + project
       root + identity). In web mode session.entered is true from the start,
       so the entire branch is unreachable and the existing SPA renders as-is. -->
  <LauncherView v-if="session.isDesktop && !session.entered" />
  <div v-else class="app-container">
    <TopBar
      :active-tab="activeTab"
      @update:active-tab="activeTab = $event"
    />
    <!-- 040 — Proposal 임팩트 미리보기 식별 배너(활성 시에만 표시, FR-007) -->
    <PreviewBanner />
    <div class="main-content">
      <template v-if="activeTab !== 'Code' && activeTab !== 'Stories' && activeTab !== 'Changes' && activeTab !== 'Requirements'">
        <div class="navigator-wrapper" :style="{ width: isNavigatorCollapsed ? '0' : navigatorWidth + 'px' }">
          <NavigatorPanel
            v-show="!isNavigatorCollapsed"
            :style="{ width: navigatorWidth + 'px' }"
          />

          <!-- Navigator Toggle Button (always visible) -->
          <button
            class="navigator-toggle"
            :class="{ 'is-collapsed': isNavigatorCollapsed }"
            @click="toggleNavigator"
            :title="isNavigatorCollapsed ? '네비게이터 펼치기' : '네비게이터 접기'"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline v-if="isNavigatorCollapsed" points="9 18 15 12 9 6"></polyline>
              <polyline v-else points="15 18 9 12 15 6"></polyline>
            </svg>
          </button>
        </div>

        <!-- Navigator Resizer (hover only) -->
        <div
          v-if="!isNavigatorCollapsed"
          class="navigator-resizer"
          @mousedown="startResizeNavigator"
          title="드래그하여 패널 너비 조절"
        ></div>
      </template>

      <!-- Tab Panel Container -->
      <div class="tab-panel-container">
        <KeepAlive>
          <component
            :is="currentComponent"
            :key="activeTab"
            v-bind="activeTab === 'Code' ? { workdir: claudeCodeWorkdir } : {}"
          />
        </KeepAlive>
      </div>
    </div>

    <!-- 034 US7 — 설계 미반영 User Story 반영 프롬프트 -->
    <DesignReflectPrompt
      v-if="designPending"
      :pending="designPending"
      @confirm="onDesignReflectConfirm"
      @dismiss="onDesignReflectDismiss"
      @dont-ask="onDesignReflectDontAsk"
    />
    <!-- 설계 갭 메우기 진행 — 기존 인제스천 진행 다이얼로그/SSE 재사용 -->
    <RequirementsIngestionModal
      v-model="designIngestModalOpen"
      :attach-session-id="designIngestSessionId"
      @complete="designIngestSessionId = ''"
    />
  </div>
</template>

<style scoped>
.navigator-toggle {
  width: 20px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
  z-index: 10;
  position: absolute;
  top: 0;
  right: 0;
  padding: 0;
}

.navigator-toggle:hover {
  background: transparent;
  color: var(--color-text);
}

.navigator-toggle.is-collapsed:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
  border-color: var(--color-accent);
}

.navigator-toggle.is-collapsed {
  right: auto;
  left: 0;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 0 6px 6px 0;
}

.navigator-resizer {
  width: 4px;
  cursor: col-resize;
  background: transparent;
  position: relative;
  flex-shrink: 0;
  transition: background 0.2s ease;
}

.navigator-resizer:hover {
  background: rgba(34, 139, 230, 0.3);
}

.main-content {
  position: relative;
}

.navigator-wrapper {
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: stretch;
}

.tab-panel-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}
</style>

