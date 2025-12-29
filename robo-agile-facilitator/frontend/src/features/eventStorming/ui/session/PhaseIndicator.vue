<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore, type SessionPhase } from '../../state/session.store'

const sessionStore = useSessionStore()

interface Phase {
  id: SessionPhase
  label: string
  duration: number
  icon: string
}

const phases: Phase[] = [
  { id: 'orientation', label: '오리엔테이션', duration: 5, icon: '👋' },
  { id: 'event_elicitation', label: '이벤트 도출', duration: 10, icon: '⚡' },
  { id: 'event_refinement', label: '이벤트 정제', duration: 15, icon: '✨' },
  { id: 'command_policy', label: '커맨드/정책', duration: 15, icon: '🔗' },
  { id: 'timeline_ordering', label: '타임라인 정렬', duration: 10, icon: '📊' },
  { id: 'summary', label: '요약', duration: 5, icon: '📝' }
]

const currentPhaseIndex = computed(() =>
  phases.findIndex(p => p.id === sessionStore.session?.phase)
)

function goToPhase(phase: SessionPhase) {
  sessionStore.updatePhase(phase)
}
</script>

<template>
  <div class="phase-indicator">
    <div
      v-for="(phase, index) in phases"
      :key="phase.id"
      class="phase-item"
      :class="{
        active: phase.id === sessionStore.session?.phase,
        completed: index < currentPhaseIndex,
        upcoming: index > currentPhaseIndex
      }"
      @click="goToPhase(phase.id)"
    >
      <span class="phase-icon">{{ phase.icon }}</span>
      <span class="phase-label">{{ phase.label }}</span>
      <span class="phase-duration">{{ phase.duration }}분</span>
    </div>
  </div>
</template>

<style scoped>
.phase-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
}

.phase-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 12px;
}

.phase-item.upcoming {
  opacity: 0.4;
}

.phase-item.completed {
  opacity: 0.6;
  background: rgba(76, 175, 80, 0.2);
}

.phase-item.active {
  background: rgba(233, 69, 96, 0.3);
  border: 1px solid rgba(233, 69, 96, 0.5);
}

.phase-item:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.1);
}

.phase-icon {
  font-size: 14px;
}

.phase-label {
  color: #fff;
  font-weight: 500;
}

.phase-duration {
  color: #888;
  font-size: 10px;
}

/* Responsive: hide labels on smaller screens */
@media (max-width: 1200px) {
  .phase-label,
  .phase-duration {
    display: none;
  }

  .phase-item {
    padding: 6px;
  }

  .phase-icon {
    font-size: 16px;
  }
}
</style>


