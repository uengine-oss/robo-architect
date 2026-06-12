<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'submit'])

const LANG_KEY = 'app_display_language'
const UI_MODE_KEY = 'app_ui_generation_mode'

const displayLanguage = ref(localStorage.getItem(LANG_KEY) || 'ko')
const uiGenerationMode = ref(localStorage.getItem(UI_MODE_KEY) || 'figma')

const figmaBindingInfo = ref(null)
async function loadFigmaBindingInfo() {
  try {
    const resp = await fetch('/api/figma-binding')
    if (resp.status === 404) { figmaBindingInfo.value = null; return }
    if (!resp.ok) return
    figmaBindingInfo.value = await resp.json()
  } catch {
    figmaBindingInfo.value = null
  }
}
const isFigmaWithComponentsEnabled = computed(() => {
  const b = figmaBindingInfo.value
  return !!(b && b.status === 'active' && (b.componentCount ?? 0) > 0)
})

// 042 — LLM 캐시 토글(전역). 캐시 ON이면 동일 입력에 캐시된 결과가 재사용돼 재생성해도
// 같은 결과만 나온다. 코드 변경 후 재생성 검증 시 OFF로 두면 매번 새로 생성된다.
// /api/ingest/cache/* 는 전역 LangChain 캐시(문서 업로드 모달과 동일 엔드포인트).
const cacheEnabled = ref(false)
const cacheBusy = ref(false)
async function checkCacheStatus() {
  try {
    const r = await fetch('/api/ingest/cache/status')
    if (r.ok) { const d = await r.json(); cacheEnabled.value = !!d.enabled }
  } catch { /* ignore */ }
}
async function setCache(enabled) {
  if (cacheBusy.value || cacheEnabled.value === enabled) return
  cacheBusy.value = true
  try {
    const r = await fetch(`/api/ingest/cache/${enabled ? 'enable' : 'disable'}`, { method: 'POST' })
    const d = await r.json().catch(() => ({}))
    if (typeof d.enabled !== 'undefined') cacheEnabled.value = !!d.enabled
    else if (r.ok) cacheEnabled.value = enabled
  } catch { /* ignore */ } finally { cacheBusy.value = false }
}

watch(() => props.visible, (open) => {
  if (!open) return
  displayLanguage.value = localStorage.getItem(LANG_KEY) || 'ko'
  const stored = localStorage.getItem(UI_MODE_KEY)
  uiGenerationMode.value = (stored === 'html' || stored === 'figma' || stored === 'figma-with-components')
    ? stored
    : 'figma'
  loadFigmaBindingInfo()
  checkCacheStatus()
})

watch(isFigmaWithComponentsEnabled, (enabled) => {
  if (!enabled && uiGenerationMode.value === 'figma-with-components') {
    uiGenerationMode.value = 'figma'
  }
})

function onSubmit() {
  localStorage.setItem(LANG_KEY, displayLanguage.value)
  localStorage.setItem(UI_MODE_KEY, uiGenerationMode.value)
  emit('submit', {
    displayLanguage: displayLanguage.value,
    uiGenerationMode: uiGenerationMode.value,
  })
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="promote-modal-overlay" @click.self="$emit('close')">
      <div class="promote-modal" role="dialog" aria-modal="true">
        <header class="promote-modal__header">
          <h2>이벤트 스토밍 승격</h2>
          <button class="close-btn" @click="$emit('close')" title="닫기">×</button>
        </header>

        <div class="promote-modal__body">
          <div class="row">
            <span class="row__label">표시 언어</span>
            <div class="row__tabs">
              <button :class="['tab-btn', 'tab-btn--small', { active: displayLanguage === 'ko' }]"
                      @click="displayLanguage = 'ko'">한글</button>
              <button :class="['tab-btn', 'tab-btn--small', { active: displayLanguage === 'en' }]"
                      @click="displayLanguage = 'en'">English</button>
            </div>
          </div>
          <div class="row">
            <span class="row__label">UI 생성</span>
            <div class="row__tabs">
              <button :class="['tab-btn', 'tab-btn--small', { active: uiGenerationMode === 'html' }]"
                      @click="uiGenerationMode = 'html'"
                      title="HTML 와이어프레임 템플릿을 생성합니다">HTML</button>
              <button :class="['tab-btn', 'tab-btn--small', { active: uiGenerationMode === 'figma' }]"
                      @click="uiGenerationMode = 'figma'"
                      title="백엔드 JSX 에이전트로 sceneGraph만 생성합니다">Figma UI</button>
              <button :class="['tab-btn', 'tab-btn--small', { active: uiGenerationMode === 'figma-with-components' }]"
                      @click="isFigmaWithComponentsEnabled && (uiGenerationMode = 'figma-with-components')"
                      :disabled="!isFigmaWithComponentsEnabled"
                      :title="isFigmaWithComponentsEnabled ? '바운드 Figma 파일의 디자인 시스템 컴포넌트를 우선 사용합니다' : 'Figma 바인딩 + 컴포넌트 스캔이 먼저 필요합니다'">
                Figma + Components
                <span v-if="figmaBindingInfo?.componentCount" class="component-count-pill">
                  {{ figmaBindingInfo.componentCount }}
                </span>
              </button>
            </div>
          </div>
          <div class="row">
            <span class="row__label">LLM 캐시</span>
            <div class="row__tabs">
              <button :class="['tab-btn', 'tab-btn--small', { active: cacheEnabled }]"
                      :disabled="cacheBusy" @click="setCache(true)"
                      title="동일 입력은 캐시된 LLM 결과 재사용 (빠름·동일 결과)">켜짐</button>
              <button :class="['tab-btn', 'tab-btn--small', { active: !cacheEnabled }]"
                      :disabled="cacheBusy" @click="setCache(false)"
                      title="캐시 무시하고 매번 새로 생성 (코드 변경·재생성 검증용)">꺼짐</button>
            </div>
          </div>
        </div>

        <footer class="promote-modal__footer">
          <button class="btn-secondary" @click="$emit('close')">취소</button>
          <button class="btn-primary" @click="onSubmit">생성</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.promote-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

.promote-modal {
  background: var(--color-bg-secondary, #fff);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  width: 100%;
  max-width: 440px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
}

.promote-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--color-border);
}
.promote-modal__header h2 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text);
}
.close-btn {
  background: transparent;
  border: none;
  font-size: 18px;
  line-height: 1;
  color: var(--color-text-light);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.close-btn:hover { background: var(--color-bg-tertiary); }

.promote-modal__body {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 8px);
}
.row__label {
  font-size: 0.8rem;
  color: var(--color-text-light);
  font-weight: 500;
  white-space: nowrap;
  min-width: 64px;
}
.row__tabs {
  display: flex;
  gap: var(--spacing-xs, 4px);
  flex-wrap: wrap;
}
.promote-modal__hint {
  margin: 2px 0 0;
  font-size: 0.72rem;
  color: var(--color-text-light);
  line-height: 1.4;
}

.tab-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs, 4px);
  padding: var(--spacing-sm, 8px) var(--spacing-sm, 8px);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 6px);
  color: var(--color-text);
  cursor: pointer;
  font-size: 0.875rem;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.tab-btn:hover { background: var(--color-bg); }
.tab-btn.active {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: white;
}
.tab-btn--small {
  padding: var(--spacing-xs, 4px) var(--spacing-sm, 8px);
  font-size: 0.8rem;
}
.tab-btn[disabled] {
  opacity: 0.45;
  cursor: not-allowed;
}

.component-count-pill {
  display: inline-block;
  margin-left: 4px;
  padding: 0 6px;
  border-radius: 9px;
  background: rgba(10, 207, 131, 0.18);
  color: #0acf83;
  font-size: 0.7rem;
  line-height: 1.3;
}
.tab-btn.active .component-count-pill {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.promote-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 18px;
  border-top: 1px solid var(--color-border);
}
.btn-primary {
  padding: 6px 16px;
  background: var(--color-accent);
  color: #fff;
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-md, 6px);
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:hover { filter: brightness(1.08); }
.btn-secondary {
  padding: 6px 14px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 6px);
  font-size: 0.82rem;
  color: var(--color-text);
  cursor: pointer;
}
.btn-secondary:hover { background: var(--color-bg); }
</style>
