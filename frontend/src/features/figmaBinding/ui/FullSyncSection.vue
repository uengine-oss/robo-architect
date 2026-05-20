<script setup>
/**
 * 020: Retroactive full-sync controls inside the FigmaBindingModal 연결 상태 tab.
 *
 *  - Primary action button "전체 Figma 반영" (with overwrite confirmation)
 *  - Live progress (storyboards X/Y, UI A/B)
 *  - Cancel button while running
 *  - Completion / cancelled / aborted banners (Korean)
 *  - Lock-busy read-only progress when another collaborator is running
 */
import { computed } from 'vue'
import { useFigmaBindingStore } from '../figmaBinding.store'

const store = useFigmaBindingStore()

const fs = computed(() => store.fullSync)
const canDispatch = computed(() => store.isActive && fs.value.state === 'idle')
const isRunning = computed(() => fs.value.state === 'running')
const isLockBusy = computed(() => fs.value.state === 'lockBusy')
const summary = computed(() => fs.value.summary || {})

const hasNoChanges = computed(() => {
  const s = summary.value
  return (
    fs.value.state === 'completed'
    && (s.pagesCreated || 0) === 0
    && (s.framesPushed || 0) === 0
    && (s.generated || 0) === 0
    && (s.overwrites || 0) === 0
    && (s.failures || 0) === 0
  )
})

async function onClickStart() {
  // Human-in-the-loop gate (Constitution IV) — explicit destructive consent.
  // eslint-disable-next-line no-alert
  const confirmed = window.confirm(
    '기존 sceneGraph 가 있으면 덮어씌워집니다. 계속하시겠습니까?'
  )
  if (!confirmed) return
  await store.startFullSync()
}

async function onClickCancel() {
  await store.cancelFullSync()
}
</script>

<template>
  <div class="fs-section">
    <div class="fs-section__header">
      <strong>전체 Figma 반영</strong>
    </div>
    <p class="fs-section__hint">
      현재 프로젝트의 모든 스토리보드와 UI 노드를 Figma 다큐먼트에 반영합니다.
    </p>

    <!-- Idle: primary action -->
    <button
      v-if="canDispatch"
      class="fs-btn fs-btn--primary"
      @click="onClickStart"
    >
      전체 Figma 반영
    </button>

    <!-- Disabled when no active binding -->
    <button
      v-else-if="!store.isActive && fs.state === 'idle'"
      class="fs-btn"
      disabled
      title="활성화된 Figma 바인딩이 없습니다"
    >
      전체 Figma 반영
    </button>

    <!-- Running progress -->
    <div v-if="isRunning" class="fs-progress">
      <div class="fs-progress__row">
        <span>storyboards</span>
        <span>{{ fs.progress.storyboardsDone }} / {{ fs.progress.storyboardsTotal }}</span>
      </div>
      <div class="fs-progress__row">
        <span>UI</span>
        <span>{{ fs.progress.uisDone }} / {{ fs.progress.uisTotal }}</span>
      </div>
      <button class="fs-btn fs-btn--cancel" @click="onClickCancel">취소</button>
    </div>

    <!-- Lock-busy: another user holds the lock -->
    <div v-if="isLockBusy" class="fs-banner fs-banner--info">
      다른 사용자가 동기화 중입니다<span v-if="fs.lockHolder"> — by {{ fs.lockHolder }}</span>
      <div class="fs-progress__row" v-if="fs.progress.uisTotal > 0">
        <span>UI</span>
        <span>{{ fs.progress.uisDone }} / {{ fs.progress.uisTotal }}</span>
      </div>
    </div>

    <!-- Completion banner -->
    <div v-if="fs.state === 'completed'" class="fs-banner fs-banner--ok">
      <template v-if="hasNoChanges">변경 없음</template>
      <template v-else>
        완료 — 페이지 {{ summary.pagesCreated || 0 }}건 / 프레임 {{ summary.framesPushed || 0 }}건 성공
        <span v-if="summary.failures">, {{ summary.failures }}건 실패</span>
      </template>
    </div>

    <div v-if="fs.state === 'cancelled'" class="fs-banner fs-banner--warn">
      취소됨 — 프레임 {{ summary.framesPushed || 0 }}건 성공 (이후 항목은 시도되지 않음)
    </div>

    <div v-if="fs.state === 'aborted'" class="fs-banner fs-banner--err">
      중단됨 — {{ fs.abortedMessageKr || 'Figma 파일에 접근할 수 없습니다' }}
    </div>
  </div>
</template>

<style scoped>
.fs-section { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--color-border, #2a2e3d); }
.fs-section__header { font-size: 0.82rem; }
.fs-section__hint { font-size: 0.74rem; color: var(--color-text-light, #aaa); margin: 0; }
.fs-btn { padding: 6px 14px; font-size: 0.78rem; border-radius: 6px; border: 1px solid #0acf83; background: transparent; color: #0acf83; cursor: pointer; align-self: flex-start; }
.fs-btn:hover:not([disabled]) { background: rgba(10,207,131,0.08); }
.fs-btn[disabled] { opacity: 0.4; cursor: not-allowed; }
.fs-btn--primary { background: #0acf83; color: #0a1015; }
.fs-btn--primary:hover { background: #08b873; }
.fs-btn--cancel { color: var(--color-text-light, #aaa); border-color: var(--color-border, #2a2e3d); margin-top: 4px; }
.fs-progress { display: flex; flex-direction: column; gap: 4px; padding: 8px; background: var(--color-bg-tertiary, #14161f); border-radius: 6px; font-size: 0.76rem; }
.fs-progress__row { display: flex; justify-content: space-between; }
.fs-banner { padding: 8px 10px; border-radius: 6px; font-size: 0.76rem; border: 1px solid; }
.fs-banner--ok { color: #0acf83; border-color: rgba(10,207,131,0.4); background: rgba(10,207,131,0.06); }
.fs-banner--warn { color: #d8a40e; border-color: rgba(216,164,14,0.4); background: rgba(216,164,14,0.06); }
.fs-banner--err { color: #e06b6b; border-color: rgba(224,107,107,0.4); background: rgba(224,107,107,0.06); }
.fs-banner--info { color: #5ea3ff; border-color: rgba(94,163,255,0.4); background: rgba(94,163,255,0.06); }
</style>
