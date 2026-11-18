<script setup>
import { computed, ref } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useI18n } from '@/app/i18n'
import { PROPOSALS_VISIBLE } from '@/app/featureVisibility'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const canvasStore = useCanvasStore()
const { t } = useI18n()
const headerText = computed(() => `<< ${terminologyStore.getTerm('UI')} >>`)

// Show template preview indicator
const hasTemplate = computed(() => !!props.data?.template)

// D-5 ⑰ ④ "No wireframe" 배지를 **생성 단추**로 — 인스펙터를 열지 않고 바로 만든다.
// 인스펙터의 HTML 생성과 같은 생성기(/api/ai-design/html-edit, 빈 instruction)를 쓴다.
// 라이브 캔버스의 노드일 때만 단추다(미리보기·다른 읽기 전용 뷰에서는 배지 그대로).
// 프로포절이 만든 UI 가 비어 생기는 문제라서 Proposals 를 따라간다 — Proposals 를 감춘
// 고객 판의 캔버스는 지금 그대로(배지)다.
const generating = ref(false)
const genError = ref('')
const canGenerate = computed(() =>
  PROPOSALS_VISIBLE && !canvasStore.isPreviewing && canvasStore.nodes.some((n) => n.id === props.id),
)

async function generateWireframe() {
  if (generating.value || !props.id) return
  generating.value = true
  genError.value = ''
  try {
    const resp = await fetch(`/api/ai-design/html-edit/${encodeURIComponent(props.id)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_language: localStorage.getItem('app_display_language') || 'ko' }),
    })
    if (!resp.ok) {
      const d = await resp.json().catch(() => ({}))
      throw new Error(d.detail || `HTTP ${resp.status}`)
    }
    const result = await resp.json()
    if (result?.template) canvasStore.patchNodeData(props.id, { template: result.template })
  } catch (e) {
    genError.value = e?.message || String(e)
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <div class="es-node es-node--ui" :class="{ 'has-template': hasTemplate }">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ terminologyStore.getLabel(data) }}</div>

      <!-- Attached To Indicator -->
      <div v-if="data?.attachedToName" class="es-node__attached">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
        <span>{{ data.attachedToName }}</span>
      </div>

      <!-- Template status -->
      <div class="es-node__status" :class="{ 'has-template': hasTemplate }">
        <span v-if="hasTemplate">✓ Wireframe</span>
        <button
          v-else-if="canGenerate"
          type="button"
          class="es-node__gen nodrag"
          :disabled="generating"
          :title="genError || t('canvas.uiNode.generateTitle')"
          @click.stop="generateWireframe"
          @mousedown.stop
        >{{ generating ? t('canvas.uiNode.generating') : (genError ? t('canvas.uiNode.retry') : t('canvas.uiNode.generate')) }}</button>
        <span v-else>No wireframe</span>
      </div>
    </div>

    <!-- Connection handles - Left/Right for optimal routing -->
    <Handle type="target" :position="Position.Left" id="left-target" />
    <Handle type="source" :position="Position.Left" id="left-source" />
    <Handle type="target" :position="Position.Right" id="right-target" />
    <Handle type="source" :position="Position.Right" id="right-source" />
  </div>
</template>

<style scoped>
.es-node--ui {
  background: linear-gradient(180deg, var(--color-ui-light) 0%, #f8f9fa 100%);
  min-width: 120px;
  max-width: 140px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  border: 2px solid #dee2e6;
}

.es-node--ui.has-template {
  border-color: var(--color-readmodel);
}

.es-node--ui:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
}

.es-node__header {
  background: rgba(0, 0, 0, 0.05);
  padding: 4px 10px;
  border-radius: 6px 6px 0 0;
  font-size: 0.6rem;
  font-weight: 500;
  text-align: center;
  color: #495057;
}

.es-node__body {
  padding: 6px 10px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.es-node__name {
  font-size: 0.8rem;
  font-weight: 600;
  color: #212529;
  text-align: center;
  line-height: 1.2;
  word-break: break-word;
}

.es-node__attached {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.6rem;
  color: #868e96;
  padding: 2px 6px;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 10px;
}

.es-node__attached svg {
  flex-shrink: 0;
}

.es-node__attached span {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.es-node__gen {
  font-size: 0.55rem;
  padding: 1px 6px;
  border-radius: 8px;
  border: 1px dashed #adb5bd;
  background: #fff;
  color: #495057;
  cursor: pointer;
}

.es-node__gen:hover:not(:disabled) {
  border-style: solid;
  border-color: var(--color-readmodel);
  color: #212529;
}

.es-node__gen:disabled {
  opacity: 0.7;
  cursor: progress;
}

.es-node__status {
  font-size: 0.55rem;
  color: #adb5bd;
  padding: 2px 6px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 4px;
}

.es-node__status.has-template {
  color: var(--color-readmodel);
  background: rgba(64, 192, 87, 0.1);
}

/* Handle styling */
::deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: #dee2e6;
  border: 2px solid var(--color-ui);
}

.es-node--ui.has-template :deep(.vue-flow__handle) {
  background: var(--color-readmodel);
  border-color: var(--color-readmodel-dark);
}
</style>


