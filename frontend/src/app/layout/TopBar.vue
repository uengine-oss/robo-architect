<script setup>
import { ref } from 'vue'
import { useCanvasStore } from '@/features/canvas/canvas.store'
// 043 — 'Big picture' 뷰 비활성화: store import 제거.
import { useAggregateViewerStore } from '@/features/canvas/aggregateViewer.store'
import { useBpmnStore } from '@/features/canvas/bpmn.store'
import { useEventModelingStore } from '@/features/eventModeling/eventModeling.store'
import PRDGeneratorModal from '@/features/prdGeneration/ui/PRDGeneratorModal.vue'
import FigmaButton from '@/features/figmaBinding/ui/FigmaButton.vue'
import FigmaBindingModal from '@/features/figmaBinding/ui/FigmaBindingModal.vue'
import SettingsPanel from './SettingsPanel.vue'

const props = defineProps({
  activeTab: {
    type: String,
    default: 'Design'
  }
})

const emit = defineEmits(['update:activeTab'])

// 'Big picture' 탭은 UI에서 숨김 (컴포넌트·기능은 App.vue tabComponents 에 유지).
// 'Process' 탭 — spec 034 WIP 커밋(de030de) 이 "당분간 숨김" 으로 빼뒀던 것 복원.
// BPMN(Process) 캔버스는 Hybrid 인제션 → ES 승격 흐름의 핵심 진입점이라
// 메뉴에서 빼면 사용자가 진입할 길이 사라짐.
// 043 — 'Process'(BPM)·'Processes'(Event Modeling)를 하나의 'Process' 탭(서브토글)로 통합,
// 'Big picture' 제거. 'Changes' 탭은 UI에서 숨김(App.vue tabComponents 에 유지).
const tabs = ['Proposals', 'Analysis', 'Stories', 'Process', 'Design', 'Data', 'Code']

const canvasStore = useCanvasStore()
// 043 — 'Big picture' 뷰 비활성화: store 사용 제거.
const aggregateViewerStore = useAggregateViewerStore()
const bpmnStore = useBpmnStore()
const eventModelingStore = useEventModelingStore()
const showPRDModal = ref(false)
const showFigmaBindingModal = ref(false)
const showSettingsPanel = ref(false)

// ClaudeCodeWorkspace 가 workspace root 를 저장하는 키와 동일.
// Code 탭 첫 진입(=프로젝트 홈 미생성) 시 PRD 생성 모달을 띄워 홈 생성을 유도하는 데 사용.
const CODE_WORKSPACE_ROOT_KEY = 'claude_code_workspace_root'

function hasProjectHome() {
  try {
    return !!localStorage.getItem(CODE_WORKSPACE_ROOT_KEY)
  } catch {
    return false
  }
}

function selectTab(tab) {
  if (tab === 'Code' && !hasProjectHome()) {
    showPRDModal.value = true
    return
  }
  emit('update:activeTab', tab)
}

</script>

<template>
  <header class="top-bar">
    <div class="top-bar__left">
      <div class="top-bar__logo">
        <div class="top-bar__logo-icon">RA</div>
        <span>Robo Architect</span>
      </div>
      
      <!-- Tab Menu -->
      <div class="top-bar__view-mode">
        <span class="view-mode-label">View mode</span>
        <nav class="top-bar__tabs">
          <button
            v-for="tab in tabs"
            :key="tab"
            class="top-bar__tab"
            :class="{ 'is-active': activeTab === tab || (tab === 'Process' && (activeTab === 'Processes' || activeTab === 'Event Modeling')) }"
            @click="selectTab(tab)"
          >
            {{ tab }}
          </button>
        </nav>
        <!-- 043 — Process 영역의 BPM⇄Event Modeling 서브토글. activeTab을 'Process'(BPM)⇄
             'Processes'(Event Modeling)로 바꿔 네비/캔버스/상단바가 함께 전환된다. -->
        <div v-if="activeTab === 'Process' || activeTab === 'Processes' || activeTab === 'Event Modeling'" class="top-bar__subtoggle">
          <button
            class="top-bar__seg"
            :class="{ 'is-active': activeTab === 'Process' }"
            @click="selectTab('Process')"
            title="사람-대면 업무 흐름(BPM)"
          >BPM</button>
          <button
            class="top-bar__seg"
            :class="{ 'is-active': activeTab === 'Processes' || activeTab === 'Event Modeling' }"
            @click="selectTab('Processes')"
            title="UI + 시스템 내부 흐름(Event Modeling)"
          >Event Modeling</button>
        </div>
      </div>
    </div>
    
    <div class="top-bar__center">
      <!-- Process Panel Status -->
      <div v-if="activeTab === 'Process'" class="top-bar__status">
        <span><strong>{{ bpmnStore.renderedFlows.length }}</strong> flows</span>
        <span class="top-bar__status-dot">•</span>
        <span><strong>{{ bpmnStore.processFlows.length }}</strong> available</span>
      </div>

      <!-- Processes Panel Status -->
      <div v-else-if="activeTab === 'Processes'" class="top-bar__status">
        <span><strong>{{ eventModelingStore.allActors.length }}</strong> Actors</span>
        <span class="top-bar__status-dot">•</span>
        <span><strong>{{ eventModelingStore.totalCommands }}</strong> Commands</span>
        <span class="top-bar__status-dot">•</span>
        <span><strong>{{ eventModelingStore.totalEvents }}</strong> Events</span>
      </div>

      <!-- Design Panel Status -->
      <div v-else-if="activeTab === 'Design'" class="top-bar__status">
        <span><strong>{{ canvasStore.nodes.length }}</strong> nodes</span>
        <span class="top-bar__status-dot">•</span>
        <span><strong>{{ canvasStore.edges.length }}</strong> connections</span>
      </div>
      
      <!-- 043 — 'Big picture' Panel Status 제거(뷰 비활성화) -->

      <!-- Data Panel Status -->
      <div v-else-if="activeTab === 'Data'" class="top-bar__status">
        <span><strong>{{ aggregateViewerStore.filteredBoundedContexts.length }}</strong> BC</span>
        <span class="top-bar__status-dot">•</span>
        <span><strong>{{ aggregateViewerStore.filteredBoundedContexts.reduce((sum, bc) => sum + (bc.aggregates?.length || 0), 0) }}</strong> Aggregates</span>
      </div>
    </div>

    <div class="top-bar__right">
      <!-- Figma Binding Button (feature 016) -->
      <FigmaButton v-model="showFigmaBindingModal" />

      <!-- Settings Button -->
        <button 
        class="settings-btn"
        @click="showSettingsPanel = true"
        title="Settings"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
        </button>
    </div>
    
    <!-- Settings Panel -->
    <SettingsPanel
      :visible="showSettingsPanel"
      @close="showSettingsPanel = false"
    />

    <!-- PRD Generator Modal (Code 메뉴 첫클릭 시 자동 노출) -->
    <PRDGeneratorModal
      :visible="showPRDModal"
      @close="showPRDModal = false"
    />

    <!-- Figma Binding Modal (feature 016) -->
    <FigmaBindingModal v-model="showFigmaBindingModal" />
  </header>
</template>

<style scoped>
/* Layout sections */
.top-bar__left {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 24px;
}

/* View Mode Container */
.top-bar__view-mode {
  display: flex;
  align-items: center;
  gap: 10px;
}

.view-mode-label {
  font-size: 0.5rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-light);
  background: linear-gradient(90deg, var(--color-command) 0%, var(--color-event) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  padding: 1px 4px;
  border: 1px solid var(--color-border);
  border-radius: 2px;
  white-space: nowrap;
  position: relative;
  overflow: hidden;
}

.view-mode-label::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, rgba(92, 124, 250, 0.08) 0%, rgba(253, 126, 20, 0.08) 100%);
  z-index: -1;
}

/* Tab Menu */
.top-bar__tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--color-bg-tertiary);
  padding: 3px;
  border-radius: 8px;
}

.top-bar__tab {
  position: relative;
  padding: 6px 14px;
  background: transparent;
  border: none;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.top-bar__tab:hover:not(.is-active) {
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.05);
}

.top-bar__tab.is-active {
  background: var(--color-accent);
  color: white;
  font-weight: 700;
  box-shadow: 0 2px 8px rgba(34, 139, 230, 0.3);
}

/* 043 — Process 영역 BPM⇄Event Modeling 서브토글 */
.top-bar__subtoggle {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 8px;
  padding: 2px;
  border-radius: 7px;
  background: var(--color-bg-tertiary);
}
.top-bar__seg {
  padding: 4px 10px;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: var(--color-text-light);
  font-size: 0.72rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}
.top-bar__seg:hover:not(.is-active) { color: var(--color-text); background: rgba(255,255,255,0.05); }
.top-bar__seg.is-active { background: var(--color-accent); color: #fff; font-weight: 700; }

.top-bar__center {
  flex: 1;
  display: flex;
  justify-content: center;
  min-width: 0;
}

.top-bar__status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.65rem;
  color: var(--color-text-light);
  background: var(--color-bg-tertiary);
  padding: 3px 10px;
  border-radius: 10px;
  white-space: nowrap;
}

.top-bar__status strong {
  color: var(--color-text);
  font-weight: 600;
}

.top-bar__status-dot {
  opacity: 0.4;
}

.top-bar__status--placeholder {
  gap: 6px;
  color: var(--color-text-light);
  opacity: 0.7;
}

.top-bar__status--placeholder svg {
  opacity: 0.6;
}

.top-bar__right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* Settings Button */
.settings-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.2s ease;
  padding: 0;
}

.settings-btn:hover {
  background: var(--color-bg-secondary);
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.settings-btn:active {
  transform: scale(0.95);
}

</style>

