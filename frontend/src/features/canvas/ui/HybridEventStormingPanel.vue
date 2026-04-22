<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useBpmnStore } from '@/features/canvas/bpmn.store'

const bpmnStore = useBpmnStore()

// Source hybrid BPM session id (set by Phase 1~4 ingestion)
const hsid = computed(() => bpmnStore.hybridSessionId)

// Promotion summary loaded from snapshot
const promoted = ref(null)
const snapshotLoading = ref(false)
const snapshotError = ref('')

// In-flight promotion run state
const isPromoting = ref(false)
const promoteSessionId = ref('')
const progress = ref(0)
const messages = ref([])
const lastError = ref('')
const eventSource = ref(null)

const isPromoted = computed(() => (promoted.value?.user_stories ?? 0) > 0)
const status = computed(() => {
  if (!hsid.value) return 'no_bpm'
  if (snapshotLoading.value) return 'loading'
  if (isPromoting.value) return 'running'
  if (isPromoted.value) return 'done'
  return 'ready'
})

async function loadSnapshot() {
  if (!hsid.value) {
    promoted.value = null
    return
  }
  snapshotLoading.value = true
  snapshotError.value = ''
  try {
    const resp = await fetch(`/api/ingest/hybrid/session/${hsid.value}/snapshot`)
    if (!resp.ok) throw new Error(`snapshot fetch failed: ${resp.status}`)
    const data = await resp.json()
    promoted.value = data.promoted || null
  } catch (e) {
    snapshotError.value = e.message || String(e)
    promoted.value = null
  } finally {
    snapshotLoading.value = false
  }
}

function pushMessage(text, kind = 'info') {
  messages.value.push({ ts: Date.now(), text, kind })
  if (messages.value.length > 80) messages.value.splice(0, messages.value.length - 80)
}

function closeStream() {
  if (eventSource.value) {
    try { eventSource.value.close() } catch {}
    eventSource.value = null
  }
}

async function startPromotion() {
  if (!hsid.value) return
  isPromoting.value = true
  progress.value = 0
  messages.value = []
  lastError.value = ''
  pushMessage('🚀 이벤트 스토밍 모델 생성을 시작합니다...', 'info')

  try {
    // 1) Wipe previous promotion (idempotent re-run friendly)
    await fetch(`/api/ingest/hybrid/${hsid.value}/promote-to-es`, { method: 'DELETE' })

    // 2) Trigger
    const resp = await fetch(`/api/ingest/hybrid/${hsid.value}/promote-to-es`, { method: 'POST' })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || `promote start failed: ${resp.status}`)
    }
    const { ingestion_session_id } = await resp.json()
    promoteSessionId.value = ingestion_session_id
    pushMessage(`📡 SSE 구독: ingestion_session_id=${ingestion_session_id}`, 'info')

    // 3) Subscribe to standard ingestion stream (same route reused)
    const es = new EventSource(`/api/ingest/stream/${ingestion_session_id}`)
    eventSource.value = es

    es.addEventListener('progress', async (e) => {
      let payload = null
      try { payload = JSON.parse(e.data) } catch {}
      if (!payload) return
      if (typeof payload.progress === 'number') progress.value = payload.progress
      if (payload.message) pushMessage(payload.message, payload.phase === 'error' ? 'error' : 'info')
      if (payload.phase === 'error') {
        lastError.value = payload.data?.error || payload.message || 'unknown error'
        closeStream()
        isPromoting.value = false
      } else if (payload.phase === 'complete') {
        closeStream()
        isPromoting.value = false
        progress.value = 100
        pushMessage('✅ 완료 — Event Modeling 탭에서 결과를 확인하세요.', 'success')
        await loadSnapshot()
      }
    })

    es.onerror = () => {
      // SSE may close on completion; only treat as error if still running
      if (isPromoting.value) {
        pushMessage('⚠️ SSE 연결이 끊겼습니다. 결과를 다시 확인합니다.', 'warn')
        closeStream()
        isPromoting.value = false
        loadSnapshot()
      }
    }
  } catch (e) {
    lastError.value = e.message || String(e)
    pushMessage(`❌ ${lastError.value}`, 'error')
    isPromoting.value = false
  }
}

function switchToEventModeling() {
  // Best-effort: nudge App.vue's activeTab via a custom event
  window.dispatchEvent(new CustomEvent('robo:switch-tab', { detail: 'Event Modeling' }))
}

onMounted(() => { loadSnapshot() })
watch(hsid, () => { loadSnapshot() })
onBeforeUnmount(() => { closeStream() })
</script>

<template>
  <div class="hybrid-es-panel">
    <header class="hybrid-es-panel__header">
      <h2>이벤트 스토밍 (Event Storming)</h2>
      <p class="subtitle">
        Phase 1~4 에서 만든 BPM 을 기반으로 UserStory / Event / BoundedContext / Aggregate / Command / Policy / ReadModel 을 자동 도출합니다.
      </p>
    </header>

    <!-- No BPM session -->
    <section v-if="status === 'no_bpm'" class="state state--empty">
      <div class="state__icon">🧩</div>
      <h3>BPM 이 아직 없습니다</h3>
      <p>BPMN 탭에서 문서 업로드를 통해 BPM 을 먼저 생성하세요.</p>
    </section>

    <!-- Snapshot loading -->
    <section v-else-if="status === 'loading'" class="state state--loading">
      <div class="state__icon">⏳</div>
      <p>BPM 상태를 확인하는 중...</p>
    </section>

    <!-- Ready to generate -->
    <section v-else-if="status === 'ready'" class="state state--ready">
      <div class="state__icon">✨</div>
      <h3>모델 생성 준비 완료</h3>
      <p>현재 BPM 으로부터 이벤트 스토밍 모델을 자동 도출합니다.</p>
      <p class="hint">
        실행 시:
        <strong>Task × source_function</strong> 단위로 UserStory 도출 → Event/BoundedContext/Aggregate/Command/Policy/ReadModel 차례로 생성 →
        BpmTask ↔ UserStory 역추적 엣지 부착 → BC 간 자동 흐름은 Cross-BC Policy 로 추출됩니다.
      </p>
      <button class="btn-primary" :disabled="!hsid" @click="startPromotion">
        🌩  모델 생성 시작
      </button>
      <p v-if="snapshotError" class="error-text">{{ snapshotError }}</p>
    </section>

    <!-- In progress -->
    <section v-else-if="status === 'running'" class="state state--running">
      <div class="progress-header">
        <h3>모델 생성 중...</h3>
        <span class="progress-pct">{{ progress }}%</span>
      </div>
      <div class="progress-bar">
        <div class="progress-bar__fill" :style="{ width: progress + '%' }"></div>
      </div>
      <ul class="log">
        <li v-for="(m, i) in messages.slice().reverse()" :key="i" :class="['log__item', `log__item--${m.kind}`]">
          {{ m.text }}
        </li>
      </ul>
      <p v-if="lastError" class="error-text">❌ {{ lastError }}</p>
    </section>

    <!-- Done -->
    <section v-else-if="status === 'done'" class="state state--done">
      <div class="state__icon">✅</div>
      <h3>이벤트 스토밍 모델 생성 완료</h3>
      <div class="counts-grid">
        <div class="count-card"><span class="count-card__label">UserStory</span><span class="count-card__val">{{ promoted?.user_stories ?? 0 }}</span></div>
        <div class="count-card"><span class="count-card__label">Event</span><span class="count-card__val">{{ promoted?.events ?? 0 }}</span></div>
        <div class="count-card"><span class="count-card__label">BoundedContext</span><span class="count-card__val">{{ promoted?.bounded_contexts ?? 0 }}</span></div>
        <div class="count-card"><span class="count-card__label">Aggregate</span><span class="count-card__val">{{ promoted?.aggregates ?? 0 }}</span></div>
        <div class="count-card"><span class="count-card__label">Command</span><span class="count-card__val">{{ promoted?.commands ?? 0 }}</span></div>
        <div class="count-card"><span class="count-card__label">ReadModel</span><span class="count-card__val">{{ promoted?.readmodels ?? 0 }}</span></div>
        <div class="count-card"><span class="count-card__label">Policy</span><span class="count-card__val">{{ promoted?.policies ?? 0 }}</span></div>
        <div class="count-card count-card--accent"><span class="count-card__label">Cross-BC Policy</span><span class="count-card__val">{{ promoted?.policies_cross_bc ?? 0 }}</span></div>
      </div>
      <div class="action-row">
        <button class="btn-primary" @click="switchToEventModeling">
          📊 Event Modeling 탭에서 시각화 보기
        </button>
        <button class="btn-secondary" @click="startPromotion">
          🔄 재생성 (LLM 다시 호출)
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.hybrid-es-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 32px 40px;
  height: 100%;
  overflow-y: auto;
  background: var(--color-bg, #f8f9fb);
}

.hybrid-es-panel__header h2 {
  font-size: 22px;
  font-weight: 600;
  margin: 0 0 6px;
  color: var(--color-text, #1a1d24);
}
.hybrid-es-panel__header .subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-muted, #6b7280);
  line-height: 1.5;
}

.state {
  background: var(--color-surface, #fff);
  border-radius: 10px;
  padding: 32px;
  border: 1px solid var(--color-border, #e5e7eb);
}
.state__icon {
  font-size: 36px;
  margin-bottom: 12px;
}
.state h3 {
  margin: 0 0 8px;
  font-size: 17px;
  color: var(--color-text, #1a1d24);
}
.state p {
  margin: 4px 0;
  font-size: 13px;
  color: var(--color-text-muted, #6b7280);
  line-height: 1.5;
}
.state .hint {
  margin-top: 14px;
  font-size: 12px;
  background: rgba(80, 120, 240, 0.06);
  padding: 12px 14px;
  border-radius: 6px;
  border-left: 3px solid #5078f0;
}

.btn-primary {
  margin-top: 18px;
  padding: 10px 20px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover { background: #4338ca; }
.btn-primary:disabled { background: #9ca3af; cursor: not-allowed; }

.btn-secondary {
  margin-top: 18px;
  padding: 10px 20px;
  background: transparent;
  color: var(--color-text, #1a1d24);
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 6px;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
}
.btn-secondary:hover { background: var(--color-bg, #f3f4f6); }

.action-row {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.progress-pct {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: #4f46e5;
}
.progress-bar {
  height: 8px;
  background: rgba(0, 0, 0, 0.08);
  border-radius: 4px;
  overflow: hidden;
}
.progress-bar__fill {
  height: 100%;
  background: linear-gradient(90deg, #4f46e5, #7c3aed);
  transition: width 0.2s;
}

.log {
  list-style: none;
  padding: 0;
  margin: 18px 0 0;
  max-height: 320px;
  overflow-y: auto;
  font-family: ui-monospace, "SFMono-Regular", monospace;
  font-size: 12px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 6px;
  padding: 10px 14px;
}
.log__item {
  padding: 3px 0;
  color: var(--color-text, #1a1d24);
  border-bottom: 1px dashed rgba(0, 0, 0, 0.04);
}
.log__item:last-child { border-bottom: none; }
.log__item--error { color: #c53030; }
.log__item--warn { color: #b7791f; }
.log__item--success { color: #2f855a; font-weight: 500; }

.counts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-top: 18px;
}
.count-card {
  background: rgba(80, 120, 240, 0.06);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.count-card--accent {
  background: rgba(245, 158, 11, 0.10);
  border: 1px solid rgba(245, 158, 11, 0.25);
}
.count-card__label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #6b7280);
}
.count-card__val {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text, #1a1d24);
}

.error-text {
  color: #c53030 !important;
  margin-top: 8px;
  font-size: 13px;
}
</style>
