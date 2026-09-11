<script setup>
import { computed, ref } from 'vue'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import { useThemeStore } from '@/app/theme.store'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import { useLanguageStore } from '@/app/language.store'
import { useAuthStore } from '@/features/auth/auth.store.js'
import UserAdminSection from '@/features/auth/ui/UserAdminSection.vue'
import AiRoutingSection from '@/features/auth/ui/AiRoutingSection.vue'

const auth = useAuthStore()

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close'])

const terminologyStore = useTerminologyStore()
const themeStore = useThemeStore()
const canvasStore = useCanvasStore()
const requirementsStore = useRequirementsStore()
const languageStore = useLanguageStore()

// Two-way binding for the Language <input>. Reads from the store directly;
// on write, runs through setLanguage() so validation + localStorage
// persistence fire. Free-form input — FR-011 requires accepting any
// BCP-47 tag, recommended list rendered as a <datalist> for discoverability.
const languageInput = computed({
  get: () => languageStore.language,
  set: (value) => languageStore.setLanguage(value),
})

function handleBackdropClick(e) {
  if (e.target === e.currentTarget) {
    emit('close')
  }
}

// ── 생성 데이터 초기화 ──
//
// 워크플로우(문서 업로드 → BPM → 룰 매핑 → 이벤트 스토밍 → 화면)가 만든
// 설계 데이터를 지운다. 되돌릴 수 없으므로 **무엇이 지워지고 무엇이 남는지를
// 실제 건수로 보여준 뒤** 한 번 더 확인받는다.
//
// 백엔드(`DELETE /api/ingest/clear-all`)가 보존하는 라벨은 지워지는 수에서 뺀다.
// 그 수를 그대로 보여주면 Figma 연결까지 지우는 것처럼 읽힌다.
const PRESERVED_LABELS = ['FigmaBinding', 'StoryboardPageMapping', 'BindingHistoryEvent', 'FigmaComponent']

// 화면에 이름으로 보여줄 것들. 여기 없는 라벨도 지워지지만, 목록을 다 늘어놓으면
// 무엇이 사라지는지가 오히려 안 보인다. 사용자가 화면에서 본 것들만 짚는다.
const CLEAR_SUMMARY = [
  ['BpmProcess', '업무 프로세스'],
  ['UserStory', '사용자 스토리'],
  ['BoundedContext', '바운디드 컨텍스트'],
  ['Aggregate', '애그리거트'],
  ['Command', '커맨드'],
  ['Event', '이벤트'],
  ['UI', '화면'],
  ['Rule', '업무 규칙'],
]

const clearState = ref('idle')   // idle | confirming | clearing | done | error
const clearStats = ref(null)
const clearMessage = ref('')

const clearableCount = computed(() => {
  const by = clearStats.value?.by_type
  if (!by) return null
  return Object.entries(by)
    .filter(([label]) => !PRESERVED_LABELS.includes(label))
    .reduce((sum, [, n]) => sum + n, 0)
})

const clearBreakdown = computed(() => {
  const by = clearStats.value?.by_type || {}
  return CLEAR_SUMMARY
    .map(([label, ko]) => ({ ko, n: by[label] || 0 }))
    .filter((x) => x.n > 0)
})

async function loadClearStats() {
  try {
    const resp = await fetch('/api/graph/stats')
    clearStats.value = resp.ok ? await resp.json() : null
  } catch (_e) {
    clearStats.value = null
  }
}

function askToClear() {
  clearMessage.value = ''
  clearState.value = 'confirming'
  loadClearStats()
}

function cancelClear() {
  clearState.value = 'idle'
}

async function confirmClear() {
  clearState.value = 'clearing'
  try {
    const resp = await fetch('/api/ingest/clear-all', { method: 'DELETE' })
    const body = await resp.json().catch(() => ({}))
    if (!resp.ok || body?.success === false) {
      throw new Error(body?.message || `삭제 실패 (${resp.status})`)
    }
    const total = Object.entries(body?.deleted || {})
      .filter(([label]) => !PRESERVED_LABELS.includes(label))
      .reduce((sum, [, n]) => sum + n, 0)
    clearState.value = 'done'
    clearMessage.value = `${total}개를 지웠습니다.`
  } catch (e) {
    clearState.value = 'error'
    clearMessage.value = e?.message || '삭제하지 못했습니다.'
  }
}

// 지운 뒤 화면을 새로 연다. 캔버스와 트리는 지우기 전 데이터를 들고 있어서,
// 그대로 두면 없는 노드를 눌러 보게 된다 — 조용히 어긋나는 자리다.
function reloadAfterClear() {
  window.location.reload()
}
</script>

<template>
  <Transition name="settings-panel">
    <div v-if="visible" class="settings-panel-backdrop" @click="handleBackdropClick">
      <div class="settings-panel" @click.stop>
        <div class="settings-panel__header">
          <h2 class="settings-panel__title">Settings</h2>
          <button class="settings-panel__close" @click="emit('close')" title="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div class="settings-panel__content">
          <!-- 사용자 관리 — 관리자에게만. 서버도 403 으로 막으므로 여기는 자리를
               감추는 것뿐이다. -->
          <UserAdminSection v-if="auth.isAdmin" />

          <!-- AI 호출 경로 — 어느 갈래가 사내 게이트웨이로 갔고 어느 갈래가
               못 갔는지. 관리자에게만 보인다(운영 설정이다). -->
          <AiRoutingSection v-if="auth.isAdmin" />

          <!-- Domain Terminology (Ubiquitous Language) Setting -->
          <div class="settings-section">
            <div class="settings-section__header">
              <h3 class="settings-section__title">도메인 용어(보편 언어)</h3>
              <span class="settings-section__description">업무/사용자 용어(displayName)를 기술명(name)보다 우선 표시합니다</span>
            </div>
            <div class="settings-section__control">
              <div class="toggle-switch">
                <span class="toggle-switch__label">도메인 용어로 표시</span>
                <button 
                  class="toggle-switch__button"
                  :class="{ 'is-active': terminologyStore.ubiquitousLanguageMode }"
                  @click="terminologyStore.toggleUbiquitousLanguageMode()"
                  :title="terminologyStore.ubiquitousLanguageMode ? 'displayName 표시 (없으면 name)' : '기술명(name)만 표시'"
                >
                  <span class="toggle-switch__knob"></span>
                </button>
              </div>
            </div>
          </div>

          <!-- Theme Setting -->
          <div class="settings-section">
            <div class="settings-section__header">
              <h3 class="settings-section__title">Theme</h3>
              <span class="settings-section__description">Choose your preferred color scheme</span>
            </div>
            <div class="settings-section__control">
              <button 
                class="theme-option"
                :class="{ 'is-active': themeStore.theme === 'dark' }"
                @click="themeStore.setTheme('dark')"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                </svg>
                <span>Dark</span>
              </button>
              <button 
                class="theme-option"
                :class="{ 'is-active': themeStore.theme === 'light' }"
                @click="themeStore.setTheme('light')"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="5"/>
                  <line x1="12" y1="1" x2="12" y2="3"/>
                  <line x1="12" y1="21" x2="12" y2="23"/>
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                  <line x1="1" y1="12" x2="3" y2="12"/>
                  <line x1="21" y1="12" x2="23" y2="12"/>
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                </svg>
                <span>Light</span>
              </button>
            </div>
          </div>

          <!-- Generation Output Language Setting (feature 031) -->
          <div class="settings-section">
            <div class="settings-section__header">
              <h3 class="settings-section__title">Language</h3>
              <span class="settings-section__description">
                AI 생성물(user story, acceptance criteria, 설명 등) 출력 언어 (BCP-47). 사용자 입력 라벨은 그대로 보존됩니다.
              </span>
            </div>
            <div class="settings-section__control settings-section__control--stack">
              <input
                v-model="languageInput"
                type="text"
                class="language-input"
                list="language-options"
                placeholder="ko-KR"
                spellcheck="false"
                autocomplete="off"
              />
              <datalist id="language-options">
                <option value="ko-KR">한국어 (ko-KR)</option>
                <option value="en-US">English (en-US)</option>
                <option value="ja-JP">日本語 (ja-JP)</option>
                <option value="zh-CN">简体中文 (zh-CN)</option>
              </datalist>
            </div>
          </div>

          <!-- Developer Terms Setting -->
          <div class="settings-section">
            <div class="settings-section__header">
              <h3 class="settings-section__title">Terminology</h3>
              <span class="settings-section__description">Switch between Event Storming and Developer terms</span>
            </div>
            <div class="settings-section__control">
              <div class="toggle-switch">
                <span class="toggle-switch__label">Developer Terms</span>
                <button 
                  class="toggle-switch__button"
                  :class="{ 'is-active': terminologyStore.developerMode }"
                  @click="terminologyStore.toggleDeveloperMode()"
                  :title="terminologyStore.developerMode ? 'Switch to Event Storming terms' : 'Switch to Developer terms'"
                >
                  <span class="toggle-switch__knob"></span>
                </button>
              </div>
            </div>
          </div>

          <!-- Design Level Setting -->
          <div class="settings-section">
            <div class="settings-section__header">
              <h3 class="settings-section__title">Design Level</h3>
              <span class="settings-section__description">Show or hide detailed fields in Design Viewer nodes</span>
            </div>
            <div class="settings-section__control">
              <div class="toggle-switch">
                <span class="toggle-switch__label">Show Fields</span>
                <button 
                  class="toggle-switch__button"
                  :class="{ 'is-active': canvasStore.showDesignLevel }"
                  @click="canvasStore.toggleDesignLevel()"
                  title="Toggle Design Level (Show/Hide Fields)"
                >
                  <span class="toggle-switch__knob"></span>
                </button>
              </div>
            </div>
          </div>

          <!-- 요구사항 생성 엔진 (034 US5) -->
          <div class="settings-section">
            <div class="settings-section__header">
              <h3 class="settings-section__title">요구사항 생성 엔진</h3>
              <span class="settings-section__description">하위 User Story 자동 생성에 사용할 엔진을 선택합니다</span>
            </div>
            <div class="settings-section__control">
              <div class="engine-options">
                <button
                  class="engine-option"
                  :class="{ 'is-active': requirementsStore.generationEngine === 'in-process' }"
                  @click="requirementsStore.setGenerationEngine('in-process')"
                >in-process LLM</button>
                <button
                  class="engine-option"
                  :class="{ 'is-active': requirementsStore.generationEngine === 'claude-ide' }"
                  @click="requirementsStore.setGenerationEngine('claude-ide')"
                  title="로컬 Claude Code + speckit 필요 (미설치 시 설치 안내)"
                >Claude IDE</button>
              </div>
            </div>
          </div>

          <!-- 생성 데이터 초기화 — 되돌릴 수 없다. 두 번 확인받는다. -->
          <div class="settings-section settings-section--danger">
            <div class="settings-section__header">
              <h3 class="settings-section__title">생성 데이터 초기화</h3>
              <span class="settings-section__description">
                문서 업로드부터 프로세스·룰 매핑·이벤트 스토밍·화면까지,
                워크플로우가 만든 설계 데이터를 모두 지웁니다.
              </span>
            </div>

            <div class="settings-section__control settings-section__control--stack">
              <template v-if="clearState === 'idle'">
                <button class="danger-button" @click="askToClear">생성 데이터 지우기</button>
              </template>

              <template v-else-if="clearState === 'confirming'">
                <div class="danger-warning">
                  <div class="danger-warning__head">되돌릴 수 없습니다.</div>

                  <div class="danger-warning__row">
                    <span class="danger-warning__label">지워지는 것</span>
                    <span class="danger-warning__value">
                      <template v-if="clearableCount === null">세는 중…</template>
                      <template v-else-if="clearableCount === 0">지울 것이 없습니다</template>
                      <template v-else>
                        <b>{{ clearableCount }}개</b>
                        <span v-if="clearBreakdown.length" class="danger-warning__detail">
                          — {{ clearBreakdown.map(b => `${b.ko} ${b.n}`).join(' · ') }}
                        </span>
                      </template>
                    </span>
                  </div>

                  <div class="danger-warning__row">
                    <span class="danger-warning__label">남는 것</span>
                    <span class="danger-warning__value">
                      Figma 연결과 스캔한 컴포넌트, 그리고 레거시 분석 결과(별도 저장소)
                    </span>
                  </div>

                  <p class="danger-warning__note">
                    다시 만들려면 문서 업로드부터 전 과정을 다시 돌려야 합니다.
                    레거시 분석은 10분 넘게 걸립니다.
                  </p>
                </div>
                <div class="danger-actions">
                  <button class="danger-cancel" @click="cancelClear">취소</button>
                  <button
                    class="danger-button danger-button--confirm"
                    :disabled="clearableCount === 0"
                    @click="confirmClear"
                  >
                    {{ clearableCount === null ? '지웁니다' : `${clearableCount}개를 지웁니다` }}
                  </button>
                </div>
              </template>

              <template v-else-if="clearState === 'clearing'">
                <div class="danger-status">지우는 중…</div>
              </template>

              <template v-else-if="clearState === 'done'">
                <div class="danger-status danger-status--done">{{ clearMessage }}</div>
                <p class="danger-warning__note">
                  화면은 아직 지우기 전 데이터를 들고 있습니다. 새로 열어야 맞습니다.
                </p>
                <button class="danger-button danger-button--confirm" @click="reloadAfterClear">
                  화면 새로 열기
                </button>
              </template>

              <template v-else>
                <div class="danger-status danger-status--error">{{ clearMessage }}</div>
                <button class="danger-cancel" @click="cancelClear">닫기</button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* ── 생성 데이터 초기화 ── */
.settings-section--danger {
  border-top: 1px solid var(--color-border);
  padding-top: 16px;
  margin-top: 4px;
}
.settings-section--danger .settings-section__title {
  color: #dc2626;
}
.danger-button {
  align-self: flex-start;
  padding: 6px 12px;
  border: 1px solid #dc2626;
  border-radius: var(--radius-sm);
  background: transparent;
  color: #dc2626;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.danger-button:hover:not(:disabled) {
  background: #dc2626;
  color: #fff;
}
.danger-button--confirm {
  background: #dc2626;
  color: #fff;
}
.danger-button--confirm:hover:not(:disabled) {
  background: #b91c1c;
  border-color: #b91c1c;
}
.danger-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.danger-cancel {
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text);
  font-size: 12px;
  cursor: pointer;
}
.danger-cancel:hover {
  background: var(--color-bg);
}
.danger-warning {
  border: 1px solid #dc2626;
  border-radius: var(--radius-sm);
  background: rgba(220, 38, 38, 0.06);
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.6;
}
.danger-warning__head {
  font-weight: 600;
  color: #dc2626;
  margin-bottom: 6px;
}
.danger-warning__row {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.danger-warning__label {
  flex: 0 0 62px;
  color: var(--color-text-light);
}
.danger-warning__value {
  flex: 1;
  min-width: 0;
  word-break: keep-all;
}
.danger-warning__detail {
  color: var(--color-text-light);
}
.danger-warning__note {
  margin: 8px 0 0;
  color: var(--color-text-light);
  font-size: 11px;
  line-height: 1.6;
}
.danger-actions {
  display: flex;
  gap: 8px;
}
.danger-status {
  font-size: 12px;
  color: var(--color-text-light);
}
.danger-status--done {
  color: #16a34a;
}
.danger-status--error {
  color: #dc2626;
}

.settings-panel-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.settings-panel {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  width: 90%;
  max-width: 480px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.settings-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}

.settings-panel__title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.settings-panel__close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.2s ease;
}

.settings-panel__close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-bright);
}

.settings-panel__content {
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.settings-section__header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.settings-section__title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.settings-section__description {
  font-size: 0.8rem;
  color: var(--color-text-light);
}

.settings-section__control {
  display: flex;
  align-items: center;
}

.settings-section__control--stack {
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}

.language-input {
  width: 100%;
  padding: 10px 12px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text-bright);
  font-size: 0.9rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  transition: border-color 0.2s ease;
}

.language-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

/* Theme Options */
.theme-option {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  background: var(--color-bg-tertiary);
  border: 2px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 0.85rem;
  font-weight: 500;
}

.engine-options {
  display: flex;
  gap: 6px;
}
.engine-option {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-tertiary);
  color: var(--color-text-light);
  font-size: 0.76rem;
  cursor: pointer;
}
.engine-option.is-active {
  background: var(--color-accent);
  color: #fff;
  border-color: transparent;
  font-weight: 600;
}
.theme-option:first-child {
  margin-right: 8px;
}

.theme-option:hover {
  border-color: var(--color-accent);
  background: var(--color-bg-secondary);
}

.theme-option.is-active {
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: white;
}

.theme-option svg {
  opacity: 0.8;
}

.theme-option.is-active svg {
  opacity: 1;
}

/* Toggle Switch */
.toggle-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.toggle-switch__label {
  font-size: 0.9rem;
  color: var(--color-text);
  font-weight: 500;
}

.toggle-switch__button {
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

.toggle-switch__button:hover {
  border-color: var(--color-accent);
}

.toggle-switch__button.is-active {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border-color: #059669;
}

.toggle-switch__knob {
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

.toggle-switch__button.is-active .toggle-switch__knob {
  transform: translateX(20px);
}

/* Transitions */
.settings-panel-enter-active,
.settings-panel-leave-active {
  transition: opacity 0.2s ease;
}

.settings-panel-enter-active .settings-panel,
.settings-panel-leave-active .settings-panel {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.settings-panel-enter-from,
.settings-panel-leave-to {
  opacity: 0;
}

.settings-panel-enter-from .settings-panel,
.settings-panel-leave-to .settings-panel {
  transform: scale(0.95);
  opacity: 0;
}
</style>
