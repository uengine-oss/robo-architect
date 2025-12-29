<script setup>
import { ref } from 'vue'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import RequirementsIngestionModal from '@/features/requirementsIngestion/ui/RequirementsIngestionModal.vue'
import PRDGeneratorModal from '@/features/prdGeneration/ui/PRDGeneratorModal.vue'

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
    <div class="top-bar__logo">
      <div class="top-bar__logo-icon"></div>
      <span>Event Storming Navigator</span>
    </div>
    
    <div class="top-bar__divider"></div>
    
    <!-- Upload Button -->
    <button 
      class="upload-btn"
      @click="showIngestionModal = true"
      title="요구사항 문서 업로드"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
      </svg>
      <span>PRD 생성</span>
    </button>
    
    <div class="top-bar__divider"></div>
    
    <div class="top-bar__info">
      <span>
        <strong>{{ canvasStore.nodes.length }}</strong> nodes on canvas
      </span>
      <span>•</span>
      <span>
        <strong>{{ canvasStore.edges.length }}</strong> connections
      </span>
    </div>
    
    <div style="flex: 1;"></div>

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

    <div class="top-bar__divider"></div>
    
    <button 
      v-if="canvasStore.nodes.length > 0"
      class="canvas-toolbar__btn"
      @click="canvasStore.clearCanvas()"
      title="Clear Canvas"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="3 6 5 6 21 6"></polyline>
        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
      </svg>
    </button>
    
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
.upload-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: linear-gradient(135deg, var(--color-accent) 0%, #1c7ed6 100%);
  border: none;
  border-radius: var(--radius-md);
  color: white;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.upload-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(34, 139, 230, 0.4);
}

.upload-btn:active {
  transform: translateY(0);
}

/* PRD Generator Button */
.prd-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: linear-gradient(135deg, #9333ea 0%, #7c3aed 100%);
  border: none;
  border-radius: var(--radius-md);
  color: white;
  font-size: 0.875rem;
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
  gap: 10px;
}

.term-toggle__label {
  font-size: 0.8rem;
  color: var(--color-text-light);
  font-weight: 500;
}

.term-toggle__switch {
  position: relative;
  width: 44px;
  height: 24px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 12px;
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
  width: 18px;
  height: 18px;
  background: white;
  border-radius: 50%;
  transition: transform 0.25s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.term-toggle__switch.is-active .term-toggle__knob {
  transform: translateX(20px);
}
</style>

