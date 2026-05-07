<script setup>
import { computed, ref, watch } from 'vue'
import { useFigmaBindingStore } from '../figmaBinding.store'
import { getStoredFigmaCreds } from '../api'
import * as api from '../api'

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

          <div class="fb-actions">
            <button class="fb-btn fb-btn--danger" @click="submitDisconnect">
              연결 해제
            </button>
          </div>

          <p class="fb-hint">
            <strong>참고:</strong> 스토리보드 동기화 및 UI 생성 라우팅은 다음 단계
            (T028 이후)에 추가됩니다. 현재는 바인딩 lifecycle만 활성화되어 있습니다.
          </p>
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

        <!-- History tab -->
        <div v-if="tab === 'history'" class="fb-section">
          <div v-if="historyLoading" class="fb-hint">불러오는 중...</div>
          <div v-else-if="history.length === 0" class="fb-hint">이력 없음</div>
          <ul v-else class="fb-history">
            <li v-for="h in history" :key="h.id">
              <span class="fb-history__time">{{ h.at }}</span>
              <span class="fb-history__type">{{ h.eventType }}</span>
              <span class="fb-history__actor">{{ h.actor }}</span>
              <span v-if="h.payload" class="fb-history__payload" :title="JSON.stringify(h.payload)">
                {{ JSON.stringify(h.payload).slice(0, 60) }}
              </span>
            </li>
          </ul>
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
</style>
