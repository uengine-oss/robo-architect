<script setup lang="ts">
/**
 * Header Timer - Compact timer display for session header
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useSessionStore, type SessionPhase } from '../../stores/session'

const props = defineProps<{
  totalMinutes?: number
}>()

const emit = defineEmits<{
  (e: 'timeWarning', data: { type: string; minutesLeft: number; phase: SessionPhase }): void
  (e: 'phaseTimeUp', phase: SessionPhase): void
  (e: 'workshopEnd'): void
}>()

const sessionStore = useSessionStore()

// Phase labels
const phaseLabels: Record<string, string> = {
  orientation: '오리엔테이션',
  event_elicitation: '이벤트 도출',
  event_refinement: '이벤트 정제',
  command_policy: '커맨드/정책',
  timeline_ordering: '타임라인',
  summary: '요약'
}

// Phase time allocation
const phaseAllocation: Record<string, number> = {
  orientation: 10,
  event_elicitation: 30,
  event_refinement: 20,
  command_policy: 20,
  timeline_ordering: 10,
  summary: 10
}

const phaseOrder: SessionPhase[] = [
  'orientation', 'event_elicitation', 'event_refinement', 
  'command_policy', 'timeline_ordering', 'summary'
]

// State
const elapsedSeconds = ref(0)
const isRunning = ref(false)
const timerInterval = ref<number | null>(null)
const warningsSent = ref<Set<string>>(new Set())
const showDetails = ref(false)

// Computed
const totalSeconds = computed(() => 
  (props.totalMinutes || sessionStore.session?.duration_minutes || 60) * 60
)

const remainingSeconds = computed(() => 
  Math.max(0, totalSeconds.value - elapsedSeconds.value)
)

const progressPercent = computed(() => 
  Math.min(100, (elapsedSeconds.value / totalSeconds.value) * 100)
)

const formattedTime = computed(() => {
  const mins = Math.floor(remainingSeconds.value / 60)
  const secs = remainingSeconds.value % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
})

const currentPhase = computed(() => sessionStore.session?.phase || 'orientation')

const currentPhaseLabel = computed(() => phaseLabels[currentPhase.value] || currentPhase.value)

// Calculate phase timings
const phaseTimings = computed(() => {
  const total = totalSeconds.value
  let accumulated = 0
  
  return phaseOrder.map(phase => {
    const duration = Math.floor(total * (phaseAllocation[phase] / 100))
    const start = accumulated
    accumulated += duration
    return { phase, startSeconds: start, endSeconds: accumulated }
  })
})

// Current phase remaining time
const phaseRemainingSeconds = computed(() => {
  const timing = phaseTimings.value.find(t => t.phase === currentPhase.value)
  if (!timing) return 0
  return Math.max(0, timing.endSeconds - elapsedSeconds.value)
})

const phaseRemainingFormatted = computed(() => {
  const mins = Math.floor(phaseRemainingSeconds.value / 60)
  const secs = phaseRemainingSeconds.value % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
})

// Status
const timerStatus = computed(() => {
  const remaining = remainingSeconds.value / 60
  if (remaining <= 1) return 'critical'
  if (remaining <= 5) return 'warning'
  if (phaseRemainingSeconds.value <= 60) return 'phase-warning'
  return 'normal'
})

// Check if this user is the host (first to join or session creator)
const isHost = computed(() => {
  // For simplicity, anyone can start the workshop
  // In production, you'd check against session creator
  return true
})

// Methods
function toggleTimer() {
  if (isRunning.value) {
    pauseTimerLocal()
    // Broadcast pause to other participants
    sessionStore.pauseTimer(true, elapsedSeconds.value)
  } else {
    if (!sessionStore.isWorkshopRunning) {
      // First start - broadcast to all participants
      sessionStore.startWorkshop()
    } else {
      // Resume from pause
      sessionStore.pauseTimer(false, elapsedSeconds.value)
    }
    startTimerLocal()
  }
}

function startTimerLocal() {
  if (isRunning.value) return
  isRunning.value = true
  
  timerInterval.value = window.setInterval(() => {
    if (!sessionStore.isPaused) {
      elapsedSeconds.value++
      checkTimeEvents()
    }
  }, 1000)
}

function pauseTimerLocal() {
  isRunning.value = false
  if (timerInterval.value) {
    clearInterval(timerInterval.value)
    timerInterval.value = null
  }
}

function checkTimeEvents() {
  const phase = currentPhase.value
  const phaseRemaining = phaseRemainingSeconds.value
  const totalRemaining = remainingSeconds.value
  
  // Phase warnings
  if (phaseRemaining === 300 && !warningsSent.value.has(`${phase}-5min`)) {
    warningsSent.value.add(`${phase}-5min`)
    emit('timeWarning', { type: 'phase-5min', minutesLeft: 5, phase })
  }
  
  if (phaseRemaining === 60 && !warningsSent.value.has(`${phase}-1min`)) {
    warningsSent.value.add(`${phase}-1min`)
    emit('timeWarning', { type: 'phase-1min', minutesLeft: 1, phase })
  }
  
  if (phaseRemaining === 0 && !warningsSent.value.has(`${phase}-end`)) {
    warningsSent.value.add(`${phase}-end`)
    emit('phaseTimeUp', phase)
  }
  
  // Total warnings
  if (totalRemaining === 600 && !warningsSent.value.has('total-10min')) {
    warningsSent.value.add('total-10min')
    emit('timeWarning', { type: 'total-10min', minutesLeft: 10, phase })
  }
  
  if (totalRemaining === 300 && !warningsSent.value.has('total-5min')) {
    warningsSent.value.add('total-5min')
    emit('timeWarning', { type: 'total-5min', minutesLeft: 5, phase })
  }
  
  if (totalRemaining === 0 && !warningsSent.value.has('workshop-end')) {
    warningsSent.value.add('workshop-end')
    emit('workshopEnd')
    pauseTimerLocal()
  }
}

// Watch for workshop start from other participants
watch(() => sessionStore.workshopStartedAt, (startedAt) => {
  if (startedAt) {
    elapsedSeconds.value = Math.floor((Date.now() - startedAt.getTime()) / 1000)
    if (!isRunning.value) {
      startTimerLocal()
    }
  }
})

// Watch for pause/resume from other participants
watch(() => sessionStore.isPaused, (paused) => {
  if (paused) {
    elapsedSeconds.value = sessionStore.syncedElapsedSeconds
    pauseTimerLocal()
  } else if (sessionStore.isWorkshopRunning && !isRunning.value) {
    startTimerLocal()
  }
})

onMounted(() => {
  // Check if workshop already started (for late joiners)
  if (sessionStore.session?.started_at) {
    const started = new Date(sessionStore.session.started_at)
    elapsedSeconds.value = Math.floor((Date.now() - started.getTime()) / 1000)
    startTimerLocal()
  } else if (sessionStore.workshopStartedAt) {
    elapsedSeconds.value = Math.floor((Date.now() - sessionStore.workshopStartedAt.getTime()) / 1000)
    startTimerLocal()
  }
  
  // Request timer sync from server
  sessionStore.requestTimerSync()
})

onUnmounted(() => {
  if (timerInterval.value) {
    clearInterval(timerInterval.value)
  }
})

defineExpose({ startTimerLocal, pauseTimerLocal, isRunning })
</script>

<template>
  <div 
    class="header-timer" 
    :class="timerStatus"
    @click="showDetails = !showDetails"
  >
    <!-- Main Timer Display -->
    <div class="timer-main">
      <button 
        class="play-pause-btn" 
        @click.stop="toggleTimer"
        :title="isRunning ? '일시정지' : '시작'"
      >
        {{ isRunning ? '⏸' : '▶' }}
      </button>
      
      <div class="time-display">
        <span class="time-value">{{ formattedTime }}</span>
        <span class="time-label">남음</span>
      </div>
      
      <div class="phase-badge">
        <span class="phase-name">{{ currentPhaseLabel }}</span>
        <span class="phase-time">{{ phaseRemainingFormatted }}</span>
      </div>
      
      <!-- Mini progress bar -->
      <div class="mini-progress">
        <div class="mini-progress-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
    </div>
    
    <!-- Expanded Details (on click) -->
    <div v-if="showDetails" class="timer-details" @click.stop>
      <h4>단계별 시간</h4>
      <div class="phase-list">
        <div 
          v-for="(timing, idx) in phaseTimings" 
          :key="timing.phase"
          class="phase-item"
          :class="{ 
            current: timing.phase === currentPhase,
            completed: elapsedSeconds >= timing.endSeconds
          }"
        >
          <span class="phase-idx">{{ idx + 1 }}</span>
          <span class="phase-label">{{ phaseLabels[timing.phase] }}</span>
          <span class="phase-duration">
            {{ Math.floor((timing.endSeconds - timing.startSeconds) / 60) }}분
          </span>
        </div>
      </div>
      <div class="timer-actions">
        <button @click.stop="elapsedSeconds = 0; warningsSent.clear()">
          ↻ 초기화
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.header-timer {
  display: flex;
  flex-direction: column;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 8px;
  padding: 6px 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.header-timer:hover {
  background: rgba(0, 0, 0, 0.5);
}

.header-timer.warning {
  border-color: #ff9800;
  background: rgba(255, 152, 0, 0.15);
}

.header-timer.critical {
  border-color: #f44336;
  background: rgba(244, 67, 54, 0.2);
  animation: pulse 1s infinite;
}

.header-timer.phase-warning {
  border-color: #ffc107;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.timer-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.play-pause-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.play-pause-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.1);
}

.time-display {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.time-value {
  font-size: 1.5rem;
  font-weight: 700;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  color: #fff;
  letter-spacing: 1px;
}

.header-timer.warning .time-value { color: #ff9800; }
.header-timer.critical .time-value { color: #f44336; }

.time-label {
  font-size: 10px;
  color: #888;
  text-transform: uppercase;
}

.phase-badge {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 4px 10px;
  background: rgba(233, 69, 96, 0.2);
  border-radius: 6px;
  border: 1px solid rgba(233, 69, 96, 0.3);
}

.phase-name {
  font-size: 11px;
  font-weight: 600;
  color: #e94560;
}

.phase-time {
  font-size: 13px;
  font-weight: 500;
  color: #fff;
  font-family: 'JetBrains Mono', monospace;
}

.mini-progress {
  width: 100px;
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.mini-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50 0%, #8bc34a 50%, #ffc107 80%, #f44336 100%);
  transition: width 1s linear;
}

/* Expanded Details */
.timer-details {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 8px;
  background: #1a1a2e;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 12px;
  z-index: 100;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.timer-details h4 {
  margin: 0 0 8px;
  font-size: 11px;
  color: #888;
  text-transform: uppercase;
}

.phase-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.phase-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #888;
}

.phase-item.current {
  background: rgba(233, 69, 96, 0.2);
  color: #fff;
}

.phase-item.current .phase-label {
  color: #e94560;
  font-weight: 600;
}

.phase-item.completed {
  color: #4caf50;
  text-decoration: line-through;
  opacity: 0.6;
}

.phase-idx {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
}

.phase-item.current .phase-idx {
  background: #e94560;
  color: #fff;
}

.phase-label {
  flex: 1;
}

.phase-duration {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

.timer-actions {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.timer-actions button {
  width: 100%;
  padding: 6px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 4px;
  color: #aaa;
  font-size: 11px;
  cursor: pointer;
}

.timer-actions button:hover {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}
</style>

