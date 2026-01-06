<script setup>
// BigPicturePanel - Placeholder for future implementation
</script>

<template>
  <div class="big-picture-panel">
    <div class="placeholder-content">
      <div class="placeholder-icon">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <line x1="3" y1="9" x2="21" y2="9"/>
          <line x1="9" y1="21" x2="9" y2="9"/>
        </svg>
      </div>
      <h2 class="placeholder-title">Big Picture</h2>
      <p class="placeholder-description">
        이벤트 스토밍의 전체 흐름을 한눈에 볼 수 있는 뷰입니다.
      </p>
      <div class="placeholder-badge">준비 중</div>
    </div>
  </div>
</template>

<style scoped>
.big-picture-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e1e2e 0%, #1a1b26 100%);
  position: relative;
  overflow: hidden;
}

.big-picture-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background: 
    radial-gradient(circle at 20% 30%, rgba(92, 124, 250, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 80% 70%, rgba(253, 126, 20, 0.06) 0%, transparent 50%);
  pointer-events: none;
}

.placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px;
  text-align: center;
  position: relative;
  z-index: 1;
}

.placeholder-icon {
  color: var(--color-text-light);
  opacity: 0.4;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

.placeholder-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.placeholder-description {
  font-size: 0.9rem;
  color: var(--color-text-light);
  max-width: 320px;
  line-height: 1.6;
  margin: 0;
}

.placeholder-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  background: rgba(34, 139, 230, 0.15);
  border: 1px solid rgba(34, 139, 230, 0.3);
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--color-accent);
  margin-top: 8px;
}
</style>

