<script setup>
import { ref, defineProps, defineEmits } from 'vue'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import RequirementsIngestionModal from '@/features/requirementsIngestion/ui/RequirementsIngestionModal.vue'
import PRDGeneratorModal from '@/features/prdGeneration/ui/PRDGeneratorModal.vue'

const props = defineProps({
  activeTab: {
    type: String,
    default: 'Design'
  }
})

const emit = defineEmits(['update:activeTab'])

const tabs = ['Big picture', 'Design', 'Aggregate']

function selectTab(tab) {
  emit('update:activeTab', tab)
}

const canvasStore = useCanvasStore()
const terminologyStore = useTerminologyStore()
const showIngestionModal = ref(false)
const showPRDModal = ref(false)

function handleIngestionComplete() {
  // Modal will trigger navigator refresh
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
            :class="{ 'is-active': activeTab === tab }"
            @click="selectTab(tab)"
          >
            {{ tab }}
          </button>
        </nav>
      </div>
    </div>
    
    <div class="top-bar__center">
      <!-- Design Panel Status -->
      <div v-if="activeTab === 'Design'" class="top-bar__status">
        <span><strong>{{ canvasStore.nodes.length }}</strong> nodes</span>
        <span class="top-bar__status-dot">•</span>
        <span><strong>{{ canvasStore.edges.length }}</strong> connections</span>
      </div>
      
      <!-- Big picture Panel Status -->
      <div v-else-if="activeTab === 'Big picture'" class="top-bar__status top-bar__status--placeholder">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <line x1="3" y1="9" x2="21" y2="9"/>
          <line x1="9" y1="21" x2="9" y2="9"/>
        </svg>
        <span>Big picture 뷰 준비 중</span>
      </div>
      
      <!-- Aggregate Panel Status -->
      <div v-else-if="activeTab === 'Aggregate'" class="top-bar__status top-bar__status--placeholder">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
        </svg>
        <span>Aggregate 설계 뷰 준비 중</span>
      </div>
    </div>

    <div class="top-bar__right">
      <!-- Upload Button -->
      <button 
        class="upload-btn"
        @click="showIngestionModal = true"
        title="요구사항 문서 업로드"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="17 8 12 3 7 8"></polyline>
          <line x1="12" y1="3" x2="12" y2="15"></line>
        </svg>
        <span>문서 업로드</span>
      </button>

      <!-- PRD Generator Button -->
      <button 
        class="prd-btn"
        :class="{ 'is-disabled': canvasStore.nodes.length === 0 }"
        @click="showPRDModal = true"
        :disabled="canvasStore.nodes.length === 0"
        title="캔버스 모델에서 PRD 생성"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
        <span>PRD 생성</span>
      </button>

      <!-- Developer Mode Toggle -->
      <div class="term-toggle">
        <span class="term-toggle__label">Developer Terms</span>
        <button 
          class="term-toggle__switch"
          :class="{ 'is-active': terminologyStore.developerMode }"
          @click="terminologyStore.toggleDeveloperMode()"
          :title="terminologyStore.developerMode ? 'Switch to Event Storming terms' : 'Switch to Developer terms'"
        >
          <span class="term-toggle__knob"></span>
        </button>
      </div>
    </div>
    
    <!-- Ingestion Modal -->
    <RequirementsIngestionModal 
      v-model="showIngestionModal"
      @complete="handleIngestionComplete"
    />

    <!-- PRD Generator Modal -->
    <PRDGeneratorModal 
      :visible="showPRDModal"
      @close="showPRDModal = false"
    />
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

.upload-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: linear-gradient(135deg, var(--color-accent) 0%, #1c7ed6 100%);
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 0.7rem;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.upload-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(34, 139, 230, 0.3);
}

.upload-btn:active {
  transform: translateY(0);
}

/* PRD Generator Button */
.prd-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: linear-gradient(135deg, #9333ea 0%, #7c3aed 100%);
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 0.7rem;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s, opacity 0.15s;
}

.prd-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(147, 51, 234, 0.4);
}

.prd-btn:active:not(:disabled) {
  transform: translateY(0);
}

.prd-btn:disabled,
.prd-btn.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Developer Mode Toggle */
.term-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
}

.term-toggle__label {
  font-size: 0.7rem;
  color: var(--color-text-light);
  font-weight: 500;
}

.term-toggle__switch {
  position: relative;
  width: 36px;
  height: 18px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 9px;
  cursor: pointer;
  transition: all 0.25s ease;
  padding: 0;
}

.term-toggle__switch:hover {
  border-color: var(--color-accent);
}

.term-toggle__switch.is-active {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border-color: #059669;
}

.term-toggle__knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  background: white;
  border-radius: 50%;
  transition: transform 0.25s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.term-toggle__switch.is-active .term-toggle__knob {
  transform: translateX(18px);
}
</style>

