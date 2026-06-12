<script setup>
/**
 * BPM task "포함 요소 / 설계 궤적" 모달 (spec 039 — US2).
 *
 * BPM task 인스펙터에서 열리며, 그 task에 귀속된 UI·Command·Event·Policy·
 * Aggregate 체인을 읽기 전용으로 보여준다. 데이터는 신규 라우트
 * GET /api/graph/bpm-task/{id}/design-trace 에서 가져오고, 렌더는 requirements
 * 탭의 설계-궤적 컴포넌트(DesignTraceCanvas)를 **무수정** 재사용한다.
 *
 * 캔버스 불변: 이 모달은 오버레이로만 마운트되며 BPM 뷰어/스토어를 건드리지 않는다.
 */
import { ref, watch } from 'vue'
// 042 US4 — Process 탭 맥락에선 Event Modeling 형식(가로 레인)으로 표시.
// requirements 탭의 DesignTraceCanvas(컬럼 그래프)는 그대로 유지.
import EventModelingLane from '@/features/canvas/ui/EventModelingLane.vue'

const props = defineProps({
  taskId: { type: String, default: null },
  taskName: { type: String, default: '' },
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const trace = ref({ nodes: [], relationships: [], empty: false })
const loading = ref(false)
const error = ref(null)

async function load() {
  if (!props.taskId) return
  loading.value = true
  error.value = null
  trace.value = { nodes: [], relationships: [], empty: false }
  try {
    const res = await fetch(`/api/graph/bpm-task/${encodeURIComponent(props.taskId)}/design-trace`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    trace.value = await res.json()
  } catch (e) {
    error.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.visible, props.taskId],
  ([vis]) => {
    if (vis && props.taskId) load()
  },
  { immediate: true },
)

function onClose() {
  emit('close')
}
</script>

<template>
  <div v-if="visible" class="bpm-trace-modal" @click.self="onClose">
    <div class="bpm-trace-modal__panel">
      <header class="bpm-trace-modal__header">
        <div class="bpm-trace-modal__title">
          <span>포함 요소 · 설계 궤적</span>
          <small v-if="taskName">{{ taskName }}</small>
        </div>
        <button class="bpm-trace-modal__close" @click="onClose" aria-label="닫기">✕</button>
      </header>
      <div class="bpm-trace-modal__body">
        <div v-if="error" class="bpm-trace-modal__error">불러오기 실패: {{ error }}</div>
        <EventModelingLane v-else :trace="trace" :loading="loading" />
      </div>
      <footer class="bpm-trace-modal__footer">
        이 task에 귀속된 시스템 흐름(UI→Command→Event→Policy)을 읽기 전용으로 표시합니다.
        캔버스는 변경되지 않습니다.
      </footer>
    </div>
  </div>
</template>

<style scoped>
.bpm-trace-modal {
  position: fixed; inset: 0; z-index: 1000;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0, 0, 0, 0.45);
}
.bpm-trace-modal__panel {
  width: min(1100px, 92vw); height: min(760px, 88vh);
  display: flex; flex-direction: column;
  background: var(--color-bg, #fff); border-radius: 10px; overflow: hidden;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.3);
}
.bpm-trace-modal__header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--color-border, #e9ecef);
}
.bpm-trace-modal__title { display: flex; flex-direction: column; }
.bpm-trace-modal__title span { font-weight: 600; }
.bpm-trace-modal__title small { color: var(--color-text-light, #868e96); font-size: 0.78rem; }
.bpm-trace-modal__close {
  border: none; background: transparent; font-size: 1rem; cursor: pointer;
  color: var(--color-text-light, #868e96); padding: 4px 8px;
}
.bpm-trace-modal__body { flex: 1; min-height: 0; }
.bpm-trace-modal__error {
  display: flex; align-items: center; justify-content: center;
  height: 100%; color: #e03131; font-size: 0.85rem;
}
.bpm-trace-modal__footer {
  padding: 8px 16px; border-top: 1px solid var(--color-border, #e9ecef);
  color: var(--color-text-light, #868e96); font-size: 0.75rem;
}
</style>
