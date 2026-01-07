<script setup>
// AggregatePanel - Placeholder for future implementation
</script>

<template>
  <div class="aggregate-panel">
    <div class="placeholder-content">
      <div class="placeholder-icon">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
        </svg>
      </div>
      <h2 class="placeholder-title">Aggregate</h2>
      <p class="placeholder-description">
        도메인 모델의 Aggregate 구조를 상세히 설계하고 관리하는 뷰입니다.
      </p>
      <div class="placeholder-badge">준비 중</div>
    </div>
  </div>
</template>

<style scoped>
.aggregate-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e1e2e 0%, #1a1b26 100%);
  position: relative;
  overflow: hidden;
}

.aggregate-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background: 
    radial-gradient(circle at 70% 20%, rgba(252, 196, 25, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 30% 80%, rgba(177, 151, 252, 0.06) 0%, transparent 50%);
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
  color: var(--color-aggregate);
  opacity: 0.5;
  animation: pulse 2.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.05); opacity: 0.7; }
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
  background: rgba(252, 196, 25, 0.15);
  border: 1px solid rgba(252, 196, 25, 0.3);
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--color-aggregate);
  margin-top: 8px;
}
</style>

