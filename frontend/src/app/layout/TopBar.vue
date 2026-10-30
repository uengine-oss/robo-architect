<script setup>
import { computed, ref } from 'vue'
import { useCanvasStore } from '@/features/canvas/canvas.store'
// 043 — 'Big picture' 뷰 비활성화: store import 제거.
import { useAggregateViewerStore } from '@/features/canvas/aggregateViewer.store'
import { useBpmnStore } from '@/features/canvas/bpmn.store'
import { useEventModelingStore } from '@/features/eventModeling/eventModeling.store'
import PRDGeneratorModal from '@/features/prdGeneration/ui/PRDGeneratorModal.vue'
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
// 'Analysis'(분석기 임베드) → 'Legacy' 로 라벨 변경 + 맨 앞으로 이동(Proposals 앞).
const VIEW_TITLE = { Legacy: '레거시', Proposals: '프로포절', Stories: '요구사항', Requirements: '요구사항', Process: '프로세스', Processes: '프로세스', 'Event Modeling': '프로세스', Design: '설계', Data: '데이터', Aggregate: '데이터', Code: '코드' }
const viewTitle = computed(() => VIEW_TITLE[props.activeTab] || props.activeTab)
// 상단 줄은 그 화면의 도구가 있을 때만(프로세스 전환·개수·PRD) — Ontological Studio 처럼 위를 비운다.
const hasBar = computed(() => ['Process', 'Processes', 'Event Modeling', 'Design', 'Data', 'Aggregate', 'Code'].includes(props.activeTab))

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

// 레일에서 Code 를 골랐는데 프로젝트 홈이 없으면 App 이 이 이벤트로 PRD 모달을 부탁한다
if (typeof window !== 'undefined') {
  window.addEventListener('robo:open-prd', () => { showPRDModal.value = true })
  // 왼쪽 레일의 설정 · Figma 단추
  window.addEventListener('robo:open-settings', () => { showSettingsPanel.value = true })
  window.addEventListener('robo:open-figma', () => { showFigmaBindingModal.value = true })
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
  <div class="top-bar-host">
  <header v-if="hasBar" class="top-bar">
    <div class="top-bar__left">
      <!-- 브랜드와 화면 전환은 왼쪽 레일(SideRail.vue)로 옮겼다 — Ontological Studio 와 같은 배치.
           여기는 지금 화면의 제목 · 서브토글 · 수치 · 동작만. -->
      <div class="top-bar__view-mode">
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
      <!-- Process(BPM) Panel Status — A2A BPM(hybrid) 기준. 011 process-flows 카운트 제거.
           BPM이 없으면 상태 표시 안 함(빈 BPM 탭과 일관). -->
      <div
        v-if="activeTab === 'Process' && (bpmnStore.hybridActive || bpmnStore.hybridProcessTrees.length)"
        class="top-bar__status"
      >
        <span><strong>{{ bpmnStore.hybridProcessTrees.length }}</strong> processes</span>
        <span class="top-bar__status-dot">•</span>
        <span><strong>{{ bpmnStore.hybridTasks.length }}</strong> tasks</span>
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
      <!-- PRD zip 다운로드 — Code 탭에서만 노출. 배포 웹에선 임베디드 터미널 대신
           이 zip을 받아 로컬(데스크톱 / local claude)에서 구현하는 것이 정식 동선이라,
           Code 탭 상단에 상시 진입점을 둔다. zip 은 그래프에서 매번 새로 빌드되는
           stateless 산출물이라 언제든 다시 받을 수 있다. -->
      <button
        v-if="activeTab === 'Code'"
        class="prd-zip-btn"
        @click="showPRDModal = true"
        title="PRD zip 다운로드 — PRD 생성 모달 열기"
      >PRD zip 다운로드</button>

    </div>
    
  </header>

    <!-- Settings Panel — 단추는 왼쪽 레일(SideRail.vue)에 있다: robo:open-settings -->
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
  </div>
</template>

<style scoped>
.top-bar-host { display: contents; }
.top-bar__title { margin: 0; font-size: 15px; font-weight: 650; color: var(--color-text-bright); letter-spacing: -.01em; }
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

/* PRD zip download (Code 탭 전용) */
.prd-zip-btn {
  height: 32px;
  display: inline-flex;
  align-items: center;
  padding: 0 12px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.prd-zip-btn:hover {
  background: var(--color-bg-secondary);
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.prd-zip-btn:active {
  transform: scale(0.97);
}

</style>

