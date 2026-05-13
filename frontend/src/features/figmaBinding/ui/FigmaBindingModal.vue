<script setup>
import { computed, ref, watch } from 'vue'
import { useFigmaBindingStore } from '../figmaBinding.store'
import { getStoredFigmaCreds } from '../api'
import * as api from '../api'
import FullSyncSection from './FullSyncSection.vue'
import HistoryFailureRow from './HistoryFailureRow.vue'
import HistorySyncRunRow from './HistorySyncRunRow.vue'
import PreviousBindingGroup from './PreviousBindingGroup.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
})
const emit = defineEmits(['update:modelValue'])

const store = useFigmaBindingStore()

const tab = ref('main') // 'main' | 'connect' | 'replace' | 'history'

// Form state
const fileKeyInput = ref('')
const tokenInput = ref('')
const replaceFileKeyInput = ref('')
const replaceTokenInput = ref('')

// History items lazily loaded
const history = ref([])
const historyLoading = ref(false)

// ─── 024: Component library ────────────────────────────────────────────
const componentsScanning = ref(false)
const componentsScanResult = ref(null) // { added, updated, removed, vlmDescribed, vlmFailures, componentCount }
const componentsScanError = ref(null)
const componentsClearing = ref(false)

async function submitScanComponents() {
  componentsScanError.value = null
  componentsScanResult.value = null
  const creds = getStoredFigmaCreds()
  const token = creds.token || tokenInput.value || replaceTokenInput.value
  if (!token) {
    componentsScanError.value = 'Figma 토큰이 필요합니다. 연결 정보를 확인하세요.'
    return
  }
  componentsScanning.value = true
  try {
    const data = await api.scanComponents(token)
    componentsScanResult.value = data
    await store.loadBinding()
  } catch (e) {
    componentsScanError.value = e.message || '컴포넌트 스캔 실패'
  } finally {
    componentsScanning.value = false
  }
}

async function submitClearComponents() {
  if (!confirm('스캔된 컴포넌트 메타데이터를 모두 삭제합니다. 계속할까요?')) return
  componentsClearing.value = true
  componentsScanError.value = null
  try {
    await api.clearComponents()
    componentsScanResult.value = null
    await store.loadBinding()
  } catch (e) {
    componentsScanError.value = e.message || '삭제 실패'
  } finally {
    componentsClearing.value = false
  }
}

// ─── 024-DEV: Sample wireframe generator (mixed instance + native) ─────
const sampleBrief = ref(
  '상품 검색 화면: 상단에 검색창(이메일/상품명 입력), 중간에는 검색된 상품 목록 3건 표시(아이폰 15 Pro 1,550,000원, 맥북 에어 M3 1,790,000원, 에어팟 프로 2 359,000원), 맨 아래에 "장바구니에 추가" 버튼.'
)
const sampleFrameName = ref('상품 검색')
const sampleGenerating = ref(false)
const sampleResult = ref(null) // { ok, instanceCount, nativeCount, figmaPageName, ... }
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
      // Pre-fill the connect form from 009's existing token storage
      const creds = getStoredFigmaCreds()
      if (!fileKeyInput.value) fileKeyInput.value = creds.fileKey || ''
      if (!tokenInput.value) tokenInput.value = creds.token || ''
      if (!replaceTokenInput.value) replaceTokenInput.value = creds.token || ''
      // Reset to default tab depending on current state
      tab.value = store.binding ? 'main' : 'connect'
      store.loadBinding()
    }
  }
)

const canSubmitConnect = computed(
  () => !!fileKeyInput.value.trim() && !!tokenInput.value.trim() && !store.isLoading
)
const canSubmitReplace = computed(
  () =>
    !!replaceFileKeyInput.value.trim() &&
    !!replaceTokenInput.value.trim() &&
    !store.isLoading
)

function close() {
  emit('update:modelValue', false)
}

function extractFileKey(input) {
  // Accept either a raw file key or a full Figma URL.
  // Figma URLs look like: https://www.figma.com/file/<KEY>/<title> OR /design/<KEY>/...
  const m = input.match(/figma\.com\/(?:file|design)\/([A-Za-z0-9]+)/)
  return m ? m[1] : input.trim()
}

async function submitConnect() {
  if (!canSubmitConnect.value) return
  const ok = await store.connect(extractFileKey(fileKeyInput.value), tokenInput.value)
  if (ok) {
    tab.value = 'main'
  }
}

async function submitReplace() {
  if (!canSubmitReplace.value) return
  const ok = await store.replace(
    extractFileKey(replaceFileKeyInput.value),
    replaceTokenInput.value
  )
  if (ok) {
    replaceFileKeyInput.value = ''
    tab.value = 'main'
  }
}

async function submitDisconnect() {
  if (!confirm(
    '이 프로젝트의 Figma 다큐먼트 바인딩을 해제합니다.\n' +
    '기존에 생성된 Figma 프레임과 sceneGraph는 삭제되지 않습니다.\n\n계속할까요?'
  )) {
    return
  }
  const ok = await store.disconnect()
  if (ok) tab.value = 'connect'
}

async function loadHistory() {
  historyLoading.value = true
  try {
    history.value = await api.getHistory(50)
  } catch (e) {
    history.value = []
  } finally {
    historyLoading.value = false
  }
  // 020: Also load failures + sync-runs for the rebuilt History tab.
  store.loadFailures().catch(() => {})
  store.loadSyncRuns().catch(() => {})
}

// 020: Computeds that split rows into "current binding" vs "이전 바인딩".
const currentFailuresRetryable = computed(() => {
  const fk = store.failures.currentBindingFileKey
  return store.failures.retryable.filter(
    (f) => !fk || !f.bindingFileKey || f.bindingFileKey === fk
  )
})
const currentFailuresInFlight = computed(() => store.failures.inFlight)
const currentFailuresNonRetryable = computed(() => {
  return store.failures.nonRetryable.filter(
    (f) => f.nonRetryableReason !== '이전 바인딩'
  )
})
const previousBindingFailures = computed(() => {
  return store.failures.nonRetryable.filter(
    (f) => f.nonRetryableReason === '이전 바인딩'
  )
})
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
          :disabled="!store.binding"
          @click="tab = 'main'"
        >연결 상태</button>
        <button
          class="fb-modal__tab"
          :class="{ 'is-active': tab === 'connect' }"
          @click="tab = 'connect'"
        >연결</button>
        <button
          class="fb-modal__tab"
          :class="{ 'is-active': tab === 'replace' }"
          :disabled="!store.binding"
          @click="tab = 'replace'"
        >교체</button>
        <button
          class="fb-modal__tab"
          :class="{ 'is-active': tab === 'history' }"
          @click="tab = 'history'"
        >이력</button>
      </nav>

      <div class="fb-modal__body">
        <!-- Main tab: status + disconnect -->
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

          <!-- 020: Retroactive full-sync controls -->
          <FullSyncSection />

          <!-- 024-DEV: Sample wireframe generator (mixed instance + native) -->
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
                >
                  Figma에서 열기
                </a>
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

          <!-- 024: Component library scan -->
          <div class="fb-components">
            <div class="fb-components__header">
              <strong>디자인 시스템 컴포넌트</strong>
              <span class="fb-components__count">
                {{ store.binding.componentCount ?? 0 }}개 인식됨
              </span>
            </div>
            <p class="fb-hint">
              연결된 Figma 파일의 <code>COMPONENT</code> / <code>COMPONENT_SET</code>
              노드를 추출하고 시각 LLM으로 1줄 설명을 채웁니다. 와이어프레임 생성 시
              <strong>Figma + Components</strong> 모드에서 이 카탈로그가 사용됩니다.
            </p>
            <div v-if="componentsScanResult" class="fb-hint" style="color:#0acf83;">
              스캔 완료: 추가 {{ componentsScanResult.added }} /
              갱신 {{ componentsScanResult.updated }} /
              제거 {{ componentsScanResult.removed }} ·
              VLM 성공 {{ componentsScanResult.vlmDescribed }} / 실패 {{ componentsScanResult.vlmFailures }}
              ({{ componentsScanResult.durationMs }}ms)
            </div>
            <div v-if="componentsScanError" class="fb-error">
              {{ componentsScanError }}
            </div>
            <div class="fb-actions">
              <button
                class="fb-btn fb-btn--primary"
                @click="submitScanComponents"
                :disabled="componentsScanning"
              >
                {{ componentsScanning ? '스캔 중...' : '컴포넌트 스캔' }}
              </button>
              <button
                v-if="(store.binding.componentCount ?? 0) > 0"
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

        <!-- Connect tab -->
        <form v-if="tab === 'connect'" class="fb-section" @submit.prevent="submitConnect">
          <p v-if="store.binding" class="fb-hint">
            이미 다른 다큐먼트가 바인딩되어 있습니다. <strong>교체</strong> 탭을 사용하거나
            먼저 연결을 해제해 주세요.
          </p>
          <div class="fb-field">
            <label>Figma 파일 URL 또는 File Key</label>
            <input
              v-model="fileKeyInput"
              type="text"
              placeholder="https://www.figma.com/file/abcd1234/..."
              :disabled="!!store.binding"
            />
          </div>
          <div class="fb-field">
            <label>개인 액세스 토큰 (figd_…)</label>
            <input
              v-model="tokenInput"
              type="password"
              placeholder="figd_..."
              :disabled="!!store.binding"
            />
          </div>
          <div v-if="store.lastError && tab === 'connect'" class="fb-error">
            {{ store.lastError }}
          </div>
          <div class="fb-actions">
            <button
              type="submit"
              class="fb-btn fb-btn--primary"
              :disabled="!canSubmitConnect || !!store.binding"
            >
              {{ store.isLoading ? '검증 중...' : '연결' }}
            </button>
          </div>
        </form>

        <!-- Replace tab -->
        <form v-if="tab === 'replace' && store.binding" class="fb-section" @submit.prevent="submitReplace">
          <p class="fb-hint">
            새 Figma 다큐먼트로 교체합니다. 기존 매핑은 <strong>archive</strong> 처리되며,
            기존에 만든 Figma 프레임은 그대로 둡니다. 이전 바인딩에서 생성된 UI 노드는
            "from previous binding" 표시가 붙습니다.
          </p>
          <div class="fb-field">
            <label>새 Figma 파일 URL 또는 File Key</label>
            <input v-model="replaceFileKeyInput" type="text" placeholder="https://www.figma.com/file/..." />
          </div>
          <div class="fb-field">
            <label>개인 액세스 토큰</label>
            <input v-model="replaceTokenInput" type="password" placeholder="figd_..." />
          </div>
          <div v-if="store.lastError && tab === 'replace'" class="fb-error">
            {{ store.lastError }}
          </div>
          <div class="fb-actions">
            <button type="submit" class="fb-btn fb-btn--primary" :disabled="!canSubmitReplace">
              {{ store.isLoading ? '검증 중...' : '교체' }}
            </button>
          </div>
        </form>

        <!-- History tab (020: failures + summary rows + 이전 바인딩 group) -->
        <div v-if="tab === 'history'" class="fb-section">
          <div v-if="store.failures.isLoading || store.syncRuns.isLoading" class="fb-hint">
            불러오는 중...
          </div>

          <!-- Empty state (FR-007 / spec § US3 acceptance scenario 3) -->
          <div v-else-if="!hasAnyHistory" class="fb-hint">
            이력 없음 — '연결 상태' 탭에서 전체 Figma 반영을 시작할 수 있습니다.
          </div>

          <template v-else>
            <!-- Retryable failures + inFlight + non-retryable (current binding) -->
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

            <!-- Sync run summary rows (current binding) -->
            <div v-if="currentSyncRuns.length" class="fb-history-group">
              <div class="fb-history-group__header"><strong>최근 실행</strong></div>
              <HistorySyncRunRow
                v-for="r in currentSyncRuns"
                :key="`sr-${r.runId}`"
                :run="r"
              />
            </div>

            <!-- Previous binding (collapsible) -->
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

.fb-history {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 50vh;
  overflow-y: auto;
}

.fb-history li {
  display: grid;
  grid-template-columns: 150px 130px 100px 1fr;
  gap: 8px;
  font-size: 0.72rem;
  padding: 4px 6px;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.05);
}

.fb-history__time { color: #888; font-family: ui-monospace, monospace; }
.fb-history__type { color: #0acf83; }
.fb-history__actor { color: #aaa; }
.fb-history__payload { color: #888; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

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
