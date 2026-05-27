<script setup>
import { computed, ref, watch } from 'vue'
import { useFigmaBindingStore } from '../figmaBinding.store'
import * as api from '../api'
import FullSyncSection from './FullSyncSection.vue'
import HistoryFailureRow from './HistoryFailureRow.vue'
import HistorySyncRunRow from './HistorySyncRunRow.vue'
import PreviousBindingGroup from './PreviousBindingGroup.vue'

// Connect / Replace happen from the Figma plugin (which posts file_key +
// file_name to /api/figma-binding/connect). This modal is read-only +
// disconnect; the plugin is the source of truth for "which file are we
// bound to right now". Same for component scan — the plugin walks
// figma.root.findAll(COMPONENT|COMPONENT_SET), exports PNGs, and pushes.

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const store = useFigmaBindingStore()

const tab = ref('main') // 'main' | 'history'

const history = ref([])
const historyLoading = ref(false)

// ─── Component library clear-only (scan now lives in the Figma plugin) ──
const componentsClearing = ref(false)
const componentsActionError = ref(null)

async function submitClearComponents() {
  if (!confirm('스캔된 컴포넌트 메타데이터를 모두 삭제합니다. 계속할까요?')) return
  componentsClearing.value = true
  componentsActionError.value = null
  try {
    await api.clearComponents()
    await store.loadBinding()
  } catch (e) {
    componentsActionError.value = e.message || '삭제 실패'
  } finally {
    componentsClearing.value = false
  }
}

// ─── DEV: Sample wireframe generator (mixed instance + native) ─────────
const sampleBrief = ref(
  '상품 검색 화면: 상단에 검색창(이메일/상품명 입력), 중간에는 검색된 상품 목록 3건 표시(아이폰 15 Pro 1,550,000원, 맥북 에어 M3 1,790,000원, 에어팟 프로 2 359,000원), 맨 아래에 "장바구니에 추가" 버튼.'
)
const sampleFrameName = ref('상품 검색')
const sampleGenerating = ref(false)
const sampleResult = ref(null)
const sampleError = ref(null)

async function submitGenerateSample() {
  sampleError.value = null
  sampleResult.value = null
  if (!sampleBrief.value.trim()) {
    sampleError.value = '브리프를 입력하세요.'
    return
  }
  sampleGenerating.value = true
  try {
    const stamp = new Date().toISOString().slice(11, 19).replace(/:/g, '')
    const resp = await fetch('/api/figma-binding/components/_dev/test-render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        screen_brief: sampleBrief.value,
        frame_name: `${sampleFrameName.value || '샘플'} ${stamp}`,
        page_name: `${sampleFrameName.value || '샘플'} ${stamp}`,
      }),
    })
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      throw new Error(data.detail?.messageKr || data.detail || `HTTP ${resp.status}`)
    }
    sampleResult.value = await resp.json()
  } catch (e) {
    sampleError.value = e.message || '생성 실패'
  } finally {
    sampleGenerating.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      tab.value = 'main'
      store.loadBinding()
    }
  }
)

function close() {
  emit('update:modelValue', false)
}

async function submitDisconnect() {
  if (!confirm(
    '이 프로젝트의 Figma 다큐먼트 바인딩을 해제합니다.\n' +
    '기존에 생성된 Figma 프레임과 sceneGraph는 삭제되지 않습니다.\n\n계속할까요?'
  )) {
    return
  }
  await store.disconnect()
}

async function loadHistory() {
  historyLoading.value = true
  try {
    history.value = await api.getHistory(50)
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
  store.loadFailures().catch(() => {})
  store.loadSyncRuns().catch(() => {})
}

const currentFailuresRetryable = computed(() => {
  const fk = store.failures.currentBindingFileKey
  return store.failures.retryable.filter(
    (f) => !fk || !f.bindingFileKey || f.bindingFileKey === fk
  )
})
const currentFailuresInFlight = computed(() => store.failures.inFlight)
const currentFailuresNonRetryable = computed(() =>
  store.failures.nonRetryable.filter((f) => f.nonRetryableReason !== '이전 바인딩')
)
const previousBindingFailures = computed(() =>
  store.failures.nonRetryable.filter((f) => f.nonRetryableReason === '이전 바인딩')
)
const currentSyncRuns = computed(() =>
  store.syncRuns.rows.filter((r) => !r.previousBinding)
)
const previousSyncRuns = computed(() =>
  store.syncRuns.rows.filter((r) => r.previousBinding)
)
const hasAnyHistory = computed(() =>
  currentFailuresRetryable.value.length
  || currentFailuresInFlight.value.length
  || currentFailuresNonRetryable.value.length
  || currentSyncRuns.value.length
  || previousBindingFailures.value.length
  || previousSyncRuns.value.length
)

async function onRetryAll() {
  await store.retryAll()
}

watch(tab, (t) => {
  if (t === 'history') loadHistory()
})
</script>

<template>
  <div v-if="modelValue" class="fb-modal__backdrop" @click.self="close">
    <div class="fb-modal__panel">
      <header class="fb-modal__header">
        <h3>Figma 다큐먼트 연동</h3>
        <button class="fb-modal__close" @click="close" title="닫기">×</button>
      </header>

      <nav class="fb-modal__tabs">
        <button
          class="fb-modal__tab"
          :class="{ 'is-active': tab === 'main' }"
          @click="tab = 'main'"
        >연결 상태</button>
        <button
          class="fb-modal__tab"
          :class="{ 'is-active': tab === 'history' }"
          @click="tab = 'history'"
        >이력</button>
      </nav>

      <div class="fb-modal__body">
        <!-- No binding yet → plugin instructions -->
        <div v-if="tab === 'main' && !store.binding" class="fb-section">
          <p class="fb-hint">
            바인딩된 Figma 다큐먼트가 없습니다. 연동은 <strong>Figma 플러그인</strong>에서
            진행합니다 — 별도의 API 토큰은 필요하지 않습니다.
          </p>
          <ol class="fb-steps">
            <li>Figma에서 연동하려는 파일을 엽니다.</li>
            <li>플러그인 메뉴에서 <strong>Robo Architect</strong>를 실행합니다.</li>
            <li>플러그인의 <strong>"이 파일을 Robo Architect에 연결"</strong> 버튼을 누릅니다.</li>
            <li>연결되면 이 모달을 다시 열어 상태를 확인할 수 있습니다.</li>
          </ol>
          <div v-if="store.lastError" class="fb-error">{{ store.lastError }}</div>
        </div>

        <!-- Main tab: status + components + disconnect -->
        <div v-if="tab === 'main' && store.binding" class="fb-section">
          <div class="fb-row">
            <label>상태</label>
            <span class="fb-status" :class="`fb-status--${store.status}`">
              {{
                store.status === 'active' ? '활성' :
                store.status === 'unreachable' ? '연결 끊김' : '해제됨'
              }}
            </span>
          </div>
          <div class="fb-row">
            <label>파일</label>
            <span>{{ store.fileName }}</span>
          </div>
          <div class="fb-row">
            <label>File Key</label>
            <code>{{ store.fileKey }}</code>
          </div>
          <div class="fb-row" v-if="store.binding.lastSyncAt">
            <label>마지막 동기화</label>
            <span>{{ store.binding.lastSyncAt }}</span>
          </div>
          <div class="fb-row">
            <label>매핑</label>
            <span>
              활성 {{ store.binding.storyboardCounts?.active ?? 0 }}건
              <span v-if="store.binding.storyboardCounts?.archived">
                / 보관 {{ store.binding.storyboardCounts.archived }}건
              </span>
            </span>
          </div>

          <FullSyncSection />

          <!-- DEV: Sample wireframe generator -->
          <div class="fb-components" data-test="sample-wireframe-panel">
            <div class="fb-components__header">
              <strong>샘플 와이어프레임 생성</strong>
              <span class="fb-components__count">
                {{ store.binding.componentCount ?? 0 }}개 컴포넌트 사용 가능
              </span>
            </div>
            <p class="fb-hint">
              아래 브리프로 LLM이 카탈로그에서 컴포넌트를 픽하고, 카탈로그에 없는 부분은
              네이티브 프리미티브(리스트·텍스트·이미지)로 만들어 Figma 새 페이지에 즉시 반영합니다.
            </p>
            <div class="fb-field">
              <label>화면 이름</label>
              <input
                v-model="sampleFrameName"
                type="text"
                data-test="sample-frame-name"
                placeholder="예: 상품 검색"
              />
            </div>
            <div class="fb-field">
              <label>화면 브리프</label>
              <textarea
                v-model="sampleBrief"
                rows="5"
                data-test="sample-brief"
                style="width:100%; padding:7px 10px; background:rgba(255,255,255,0.05); border:1px solid var(--color-border, #2a2e3d); border-radius:4px; color:inherit; font-size:0.8rem; font-family:inherit; resize:vertical;"
              ></textarea>
            </div>
            <div v-if="sampleResult" class="fb-hint" style="color:#0acf83;" data-test="sample-result">
              ✓ 생성 완료 — page <code>{{ sampleResult.figmaPageName }}</code>
              ({{ sampleResult.figmaPageId }}),
              instance {{ sampleResult.instanceCount }} / native {{ sampleResult.nativeCount }} ·
              plugin nodesCreated={{ sampleResult.nodesCreated }}, failed={{ sampleResult.nodesFailed }}
              <span v-if="sampleResult.unresolved?.length" style="color:#f59e0b;">
                — unresolved: {{ sampleResult.unresolved.join(', ') }}
              </span>
              <div v-if="sampleResult.figmaUrl" style="margin-top:6px;">
                →
                <a
                  :href="sampleResult.figmaUrl"
                  target="_blank"
                  rel="noopener"
                  data-test="sample-figma-url"
                  style="color:#0acf83; text-decoration:underline;"
                >Figma에서 열기</a>
              </div>
            </div>
            <div v-if="sampleError" class="fb-error" data-test="sample-error">{{ sampleError }}</div>
            <div class="fb-actions">
              <button
                class="fb-btn fb-btn--primary"
                data-test="sample-generate"
                @click="submitGenerateSample"
                :disabled="sampleGenerating"
              >
                {{ sampleGenerating ? '생성 중...' : '와이어프레임 생성' }}
              </button>
            </div>
          </div>

          <!-- Component catalog: scan is plugin-driven; modal only shows count + clear -->
          <div class="fb-components">
            <div class="fb-components__header">
              <strong>디자인 시스템 컴포넌트</strong>
              <span class="fb-components__count">
                {{ store.binding.componentCount ?? 0 }}개 인식됨
              </span>
            </div>
            <p class="fb-hint">
              컴포넌트 스캔은 <strong>Figma 플러그인</strong>에서 실행합니다 —
              <code>COMPONENT</code> / <code>COMPONENT_SET</code> 노드를 찾아
              PNG 와 함께 백엔드로 전송하면, 백엔드가 시각 LLM 으로 1줄 설명을
              채우고 카탈로그를 갱신합니다. 와이어프레임 생성 시
              <strong>Figma + Components</strong> 모드에서 사용됩니다.
            </p>
            <div v-if="componentsActionError" class="fb-error">
              {{ componentsActionError }}
            </div>
            <div v-if="(store.binding.componentCount ?? 0) > 0" class="fb-actions">
              <button
                class="fb-btn fb-btn--small"
                @click="submitClearComponents"
                :disabled="componentsClearing"
              >
                카탈로그 비우기
              </button>
            </div>
          </div>

          <div class="fb-actions">
            <button class="fb-btn fb-btn--danger" @click="submitDisconnect">
              연결 해제
            </button>
          </div>
        </div>

        <!-- History tab (failure rows + sync run summaries + 이전 바인딩) -->
        <div v-if="tab === 'history'" class="fb-section">
          <div v-if="store.failures.isLoading || store.syncRuns.isLoading" class="fb-hint">
            불러오는 중...
          </div>

          <div v-else-if="!hasAnyHistory" class="fb-hint">
            이력 없음 — '연결 상태' 탭에서 전체 Figma 반영을 시작할 수 있습니다.
          </div>

          <template v-else>
            <div
              v-if="currentFailuresRetryable.length || currentFailuresInFlight.length || currentFailuresNonRetryable.length"
              class="fb-history-group"
            >
              <div class="fb-history-group__header">
                <strong>실패 항목</strong>
                <button
                  v-if="currentFailuresRetryable.length"
                  class="fb-btn fb-btn--small"
                  @click="onRetryAll"
                >전체 다시 시도 ({{ currentFailuresRetryable.length }})</button>
              </div>
              <HistoryFailureRow
                v-for="f in currentFailuresRetryable"
                :key="`r-${f.uiId}`"
                :failure="f"
              />
              <HistoryFailureRow
                v-for="f in currentFailuresInFlight"
                :key="`if-${f.uiId}`"
                :failure="f"
              />
              <HistoryFailureRow
                v-for="f in currentFailuresNonRetryable"
                :key="`nr-${f.uiId}`"
                :failure="f"
              />
            </div>

            <div v-if="currentSyncRuns.length" class="fb-history-group">
              <div class="fb-history-group__header"><strong>최근 실행</strong></div>
              <HistorySyncRunRow
                v-for="r in currentSyncRuns"
                :key="`sr-${r.runId}`"
                :run="r"
              />
            </div>

            <PreviousBindingGroup
              :sync-runs="previousSyncRuns"
              :failures="previousBindingFailures"
            />
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fb-modal__backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}

.fb-modal__panel {
  width: 560px;
  max-width: 90vw;
  max-height: 80vh;
  background: var(--color-bg-secondary, #1a1d29);
  border: 1px solid var(--color-border, #2a2e3d);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  color: var(--color-text, #e6e8ee);
  font-size: 0.85rem;
}

.fb-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border, #2a2e3d);
}

.fb-modal__header h3 { font-size: 0.95rem; font-weight: 600; margin: 0; }

.fb-modal__close {
  background: transparent;
  border: none;
  color: var(--color-text-light, #aaa);
  font-size: 1.2rem;
  cursor: pointer;
}

.fb-modal__tabs {
  display: flex;
  gap: 2px;
  padding: 0 12px;
  border-bottom: 1px solid var(--color-border, #2a2e3d);
}

.fb-modal__tab {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 8px 12px;
  color: var(--color-text-light, #aaa);
  cursor: pointer;
  font-size: 0.78rem;
}

.fb-modal__tab.is-active {
  color: #0acf83;
  border-bottom-color: #0acf83;
}

.fb-modal__tab[disabled] {
  opacity: 0.4;
  cursor: not-allowed;
}

.fb-modal__body {
  padding: 16px;
  overflow-y: auto;
}

.fb-section { display: flex; flex-direction: column; gap: 10px; }

.fb-row {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 8px;
  align-items: baseline;
}

.fb-row label {
  color: var(--color-text-light, #888);
  font-size: 0.75rem;
}

.fb-row code {
  font-family: ui-monospace, monospace;
  font-size: 0.75rem;
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 6px;
  border-radius: 3px;
}

.fb-status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.7rem;
}
.fb-status--active { background: rgba(10, 207, 131, 0.2); color: #0acf83; }
.fb-status--unreachable { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
.fb-status--disconnected { background: rgba(255, 255, 255, 0.1); color: #aaa; }

.fb-field { display: flex; flex-direction: column; gap: 4px; }
.fb-field label { font-size: 0.75rem; color: var(--color-text-light, #aaa); }
.fb-field input {
  padding: 7px 10px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--color-border, #2a2e3d);
  border-radius: 4px;
  color: inherit;
  font-size: 0.8rem;
}
.fb-field input:focus { outline: none; border-color: #0acf83; }

.fb-actions { display: flex; gap: 8px; margin-top: 8px; }

.fb-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
}
.fb-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.fb-btn--small { padding: 3px 10px; font-size: 0.74rem; background: transparent; border: 1px solid #0acf83; color: #0acf83; }
.fb-btn--small:hover:not(:disabled) { background: rgba(10,207,131,0.08); }
.fb-history-group { display: flex; flex-direction: column; gap: 0; margin-bottom: 12px; }
.fb-history-group__header { display: flex; justify-content: space-between; align-items: center; padding: 4px 0 6px; font-size: 0.78rem; }
.fb-btn--primary { background: #0acf83; color: #fff; }
.fb-btn--primary:hover:not(:disabled) { background: #08b774; }
.fb-btn--danger {
  background: transparent;
  border: 1px solid #ef4444;
  color: #ef4444;
}
.fb-btn--danger:hover { background: rgba(239, 68, 68, 0.1); }

.fb-hint {
  font-size: 0.75rem;
  color: var(--color-text-light, #888);
  background: rgba(255, 255, 255, 0.03);
  padding: 8px 10px;
  border-radius: 4px;
}

.fb-error {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  padding: 8px 10px;
  border-radius: 4px;
  font-size: 0.78rem;
}

.fb-steps {
  margin: 0;
  padding: 8px 24px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--color-text, #ddd);
}
.fb-steps li { line-height: 1.4; }

.fb-components {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--color-border, #2a2e3d);
  border-radius: 6px;
  margin-top: 8px;
}
.fb-components__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.82rem;
}
.fb-components__count {
  font-family: ui-monospace, monospace;
  font-size: 0.78rem;
  color: #0acf83;
}
</style>
