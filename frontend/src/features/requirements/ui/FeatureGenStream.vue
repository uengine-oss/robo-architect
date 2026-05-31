<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Epic→Feature 생성 — deep agent 리즈닝 라이브 스트림 (034).
 * /epic/{id}/generate-features/stream SSE를 구독해 리즈닝 단계를 우측에 흘리고,
 * complete 시 생성된 features를 emit('done', {boundedContextId, features}) 한다.
 */
const props = defineProps({
  boundedContextId: { type: String, required: true },
  scopeName: { type: String, default: '' },
})
const emit = defineEmits(['done', 'close'])

const lines = ref([])
const done = ref(false)
let es = null

onMounted(() => {
  es = new EventSource(`/api/requirements/epic/${props.boundedContextId}/generate-features/stream`)
  es.addEventListener('progress', (e) => {
    let data
    try {
      data = JSON.parse(e.data)
    } catch {
      return
    }
    if (data.message) lines.value.push({ phase: data.phase, message: data.message })
    if (data.phase === 'complete') {
      done.value = true
      close()
      emit('done', { boundedContextId: props.boundedContextId, features: data.features || [] })
    }
  })
  es.onerror = () => {
    if (!done.value) lines.value.push({ phase: 'error', message: '연결 오류 — 다시 시도하세요.' })
    close()
  }
})

function close() {
  if (es) {
    try { es.close() } catch {}
    es = null
  }
}
onUnmounted(close)
</script>

<template>
  <div class="fgs-backdrop">
    <div class="fgs">
      <div class="fgs__head">
        <span class="fgs__spark">✨</span>
        <h3>Feature 자동 생성 — {{ scopeName }}</h3>
        <button class="fgs__close" @click="close(); emit('close')">×</button>
      </div>
      <div class="fgs__sub">딥 에이전트(speckit-specify)가 Epic을 Feature(spec.md)로 분해하는 중…</div>
      <div class="fgs__log">
        <div v-for="(l, i) in lines" :key="i" class="fgs__line" :class="l.phase">
          {{ l.message }}
        </div>
        <div v-if="!done" class="fgs__cursor">▌</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fgs-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 1100; display: flex; align-items: center; justify-content: flex-end; }
.fgs { width: 440px; height: 100%; background: var(--color-bg-secondary); border-left: 1px solid var(--color-border); display: flex; flex-direction: column; }
.fgs__head { display: flex; align-items: center; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--color-border); }
.fgs__spark { font-size: 1.1rem; }
.fgs__head h3 { margin: 0; font-size: 0.9rem; flex: 1; overflow: hidden; text-overflow: ellipsis; }
.fgs__close { border: none; background: transparent; font-size: 1.2rem; cursor: pointer; color: var(--color-text-light); }
.fgs__sub { padding: 8px 14px; font-size: 0.74rem; color: var(--color-text-light); border-bottom: 1px solid var(--color-border); }
.fgs__log { flex: 1; overflow-y: auto; padding: 10px 14px; font-size: 0.78rem; font-family: var(--font-mono, monospace); line-height: 1.5; }
.fgs__line { margin: 3px 0; white-space: pre-wrap; word-break: break-word; }
.fgs__line.reasoning { color: var(--color-text); }
.fgs__line.start { color: var(--color-accent); }
.fgs__line.complete { color: #40c057; font-weight: 600; }
.fgs__line.error { color: #e03131; }
.fgs__cursor { color: var(--color-accent); animation: blink 1s steps(2) infinite; }
@keyframes blink { 0%,50% { opacity: 1; } 50.01%,100% { opacity: 0; } }
</style>
