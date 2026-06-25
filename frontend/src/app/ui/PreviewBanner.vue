<template>
  <div v-if="session.active" class="preview-banner">
    <span class="pb-icon">🔍</span>
    <span class="pb-text">
      <strong>{{ session.label }}</strong> 임팩트 미리보기 · <em>읽기 전용</em> — 라이브 설계가 아닙니다{{ (session.viewer === 'data' || session.viewer === 'design') ? ' (제안 변경 오버레이)' : '' }}
      <span v-if="session.title" class="pb-target">· {{ session.title }}</span>
      <span v-if="session.notice" class="pb-notice">⚠ {{ session.notice }}</span>
    </span>
    <button class="pb-close" @click="onClose">닫기 ✕</button>
  </div>
</template>

<script setup>
import { usePreviewSession, exitPreview } from '../previewSession'

const session = usePreviewSession()

function onClose() {
  // exit + 뷰어에 라이브 재적재를 요청(스토어가 robo:preview-exit 를 수신).
  const viewer = session.viewer
  exitPreview()
  window.dispatchEvent(new CustomEvent('robo:preview-exit', { detail: { viewer } }))
}
</script>

<style scoped>
.preview-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; font-size: 12px;
  background: var(--status-amber-bg, #fef3c7); color: var(--status-amber-fg, #92400e);
  border-bottom: 1px solid var(--status-amber-fg, #d97706);
}
.pb-icon { font-size: 13px; }
.pb-text { flex: 1; }
.pb-target { opacity: 0.8; }
.pb-notice { margin-left: 8px; font-weight: 600; opacity: 0.95; }
.pb-close {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; cursor: pointer;
  border: 1px solid currentColor; background: transparent; color: inherit;
}
.pb-close:hover { background: rgba(0,0,0,0.06); }
</style>
