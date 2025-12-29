<script setup lang="ts">
/**
 * Workshop Timer Component
 * - Displays remaining time for the entire workshop
 * - Shows phase progress and time allocation
 * - Triggers AI facilitation based on time events
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

// Phase time allocation (percentage of total time)
const phaseAllocation: Record<SessionPhase, { percent: number; label: string }> = {
  orientation: { percent: 10, label: '오리엔테이션' },
  event_elicitation: { percent: 30, label: '이벤트 도출' },
  event_refinement: { percent: 20, label: '이벤트 정제' },
  command_policy: { percent: 20, label: '커맨드/정책' },
  timeline_ordering: { percent: 10, label: '타임라인 정렬' },
  summary: { percent: 10, label: '요약' }
}

const phaseOrder: SessionPhase[] = [
  'orientation',
  'event_elicitation', 
  'event_refinement',
  'command_policy',
  'timeline_ordering',
  'summary'
]

// State
const startTime = ref<Date | null>(null)
const elapsedSeconds = ref(0)
const isRunning = ref(false)
const timerInterval = ref<number | null>(null)
const warningsSent = ref<Set<string>>(new Set())

// Computed
const totalSeconds = computed(() => (props.totalMinutes || sessionStore.session?.duration_minutes || 60) * 60)

const remainingSeconds = computed(() => Math.max(0, totalSeconds.value - elapsedSeconds.value))

const remainingMinutes = computed(() => Math.floor(remainingSeconds.value / 60))

const progressPercent = computed(() => 
  Math.min(100, (elapsedSeconds.value / totalSeconds.value) * 100)
)

const formattedTime = computed(() => {
  const mins = Math.floor(remainingSeconds.value / 60)
  const secs = remainingSeconds.value % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
})

const currentPhase = computed(() => sessionStore.session?.phase || 'orientation')

// Calculate time for each phase
const phaseTimings = computed(() => {
  const total = totalSeconds.value
  let accumulated = 0
  
  return phaseOrder.map(phase => {
    const duration = Math.floor(total * (phaseAllocation[phase].percent / 100))
    const start = accumulated
    accumulated += duration
    return {
      phase,
      label: phaseAllocation[phase].label,
      startSeconds: start,
      endSeconds: accumulated,
      durationMinutes: Math.floor(duration / 60)
    }
  })
})

// Get current phase timing info
const currentPhaseTiming = computed(() => {
  return phaseTimings.value.find(t => t.phase === currentPhase.value)
})

// Time remaining in current phase
const phaseRemainingSeconds = computed(() => {
  const timing = currentPhaseTiming.value
  if (!timing) return 0
  return Math.max(0, timing.endSeconds - elapsedSeconds.value)
})

const phaseProgressPercent = computed(() => {
  const timing = currentPhaseTiming.value
  if (!timing) return 0
  const phaseElapsed = elapsedSeconds.value - timing.startSeconds
  const phaseDuration = timing.endSeconds - timing.startSeconds
  return Math.min(100, Math.max(0, (phaseElapsed / phaseDuration) * 100))
})

// Status indicator
const timerStatus = computed(() => {
  if (remainingMinutes.value <= 1) return 'critical'
  if (remainingMinutes.value <= 5) return 'warning'
  if (phaseRemainingSeconds.value <= 60) return 'phase-ending'
  return 'normal'
})

// Methods
function startTimer() {
  if (isRunning.value) return
  
  startTime.value = new Date()
  isRunning.value = true
  
  timerInterval.value = window.setInterval(() => {
    elapsedSeconds.value++
    checkTimeEvents()
  }, 1000)
}

function pauseTimer() {
  isRunning.value = false
  if (timerInterval.value) {
    clearInterval(timerInterval.value)
    timerInterval.value = null
  }
}

function resetTimer() {
  pauseTimer()
  elapsedSeconds.value = 0
  startTime.value = null
  warningsSent.value.clear()
}

function checkTimeEvents() {
  const phase = currentPhase.value
  const phaseRemaining = phaseRemainingSeconds.value
  const totalRemaining = remainingSeconds.value
  
  // Phase time warnings
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
  
  // Total workshop warnings
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
    pauseTimer()
  }
}

// Suggest next phase based on time
function suggestNextPhase(): SessionPhase | null {
  const currentIdx = phaseOrder.indexOf(currentPhase.value)
  if (currentIdx < phaseOrder.length - 1) {
    return phaseOrder[currentIdx + 1]
  }
  return null
}

// Watch for phase changes to reset phase warnings
watch(currentPhase, () => {
  // Keep total warnings, reset phase-specific ones for new phase
})

onMounted(() => {
  // Auto-start if session has started
  if (sessionStore.session?.started_at) {
    const started = new Date(sessionStore.session.started_at)
    elapsedSeconds.value = Math.floor((Date.now() - started.getTime()) / 1000)
    startTimer()
  }
})

onUnmounted(() => {
  if (timerInterval.value) {
    clearInterval(timerInterval.value)
  }
})

// Expose methods for parent
defineExpose({
  startTimer,
  pauseTimer,
  resetTimer,
  suggestNextPhase,
  phaseTimings,
  remainingMinutes,
  phaseRemainingSeconds
})
</script>

<template>
  <div class="workshop-timer" :class="timerStatus">
    <!-- Main Timer Display -->
    <div class="timer-display">
      <div class="time-value">{{ formattedTime }}</div>
      <div class="time-label">남은 시간</div>
    </div>
    
    <!-- Overall Progress -->
    <div class="progress-section">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        <div 
          v-for="timing in phaseTimings" 
          :key="timing.phase"
          class="phase-marker"
          :class="{ active: timing.phase === currentPhase, completed: elapsedSeconds >= timing.endSeconds }"
          :style="{ left: (timing.endSeconds / totalSeconds * 100) + '%' }"
          :title="`${timing.label} 종료`"
        ></div>
      </div>
    </div>
    
    <!-- Current Phase Info -->
    <div class="phase-info">
      <div class="phase-name">{{ currentPhaseTiming?.label }}</div>
      <div class="phase-time">
        {{ Math.floor(phaseRemainingSeconds / 60) }}분 {{ phaseRemainingSeconds % 60 }}초
      </div>
      <div class="phase-progress">
        <div class="phase-progress-fill" :style="{ width: phaseProgressPercent + '%' }"></div>
      </div>
    </div>
    
    <!-- Timer Controls -->
    <div class="timer-controls">
      <button 
        v-if="!isRunning" 
        class="control-btn start"
        @click="startTimer"
      >
        ▶ 시작
      </button>
      <button 
        v-else 
        class="control-btn pause"
        @click="pauseTimer"
      >
        ⏸ 일시정지
      </button>
      <button 
        class="control-btn reset"
        @click="resetTimer"
        title="타이머 초기화"
      >
        ↻
      </button>
    </div>
    
    <!-- Phase Timeline -->
    <div class="phase-timeline">
      <div 
        v-for="timing in phaseTimings" 
        :key="timing.phase"
        class="timeline-item"
        :class="{ 
          current: timing.phase === currentPhase,
          completed: elapsedSeconds >= timing.endSeconds
        }"
      >
        <span class="timeline-label">{{ timing.label }}</span>
        <span class="timeline-duration">{{ timing.durationMinutes }}분</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workshop-timer {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.workshop-timer.warning {
  border-color: #ff9800;
  box-shadow: 0 0 20px rgba(255, 152, 0, 0.2);
}

.workshop-timer.critical {
  border-color: #f44336;
  box-shadow: 0 0 20px rgba(244, 67, 54, 0.3);
  animation: pulse-critical 1s infinite;
}

.workshop-timer.phase-ending {
  border-color: #ffc107;
}

@keyframes pulse-critical {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

.timer-display {
  text-align: center;
  margin-bottom: 12px;
}

.time-value {
  font-size: 2.5rem;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  color: #fff;
  letter-spacing: 2px;
}

.workshop-timer.warning .time-value { color: #ff9800; }
.workshop-timer.critical .time-value { color: #f44336; }

.time-label {
  font-size: 11px;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.progress-section {
  margin-bottom: 12px;
}

.progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  position: relative;
  overflow: visible;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50 0%, #8bc34a 50%, #ffc107 80%, #f44336 100%);
  border-radius: 3px;
  transition: width 1s linear;
}

.phase-marker {
  position: absolute;
  top: -4px;
  width: 2px;
  height: 14px;
  background: rgba(255, 255, 255, 0.3);
  transform: translateX(-1px);
}

.phase-marker.active {
  background: #e94560;
  width: 4px;
  transform: translateX(-2px);
}

.phase-marker.completed {
  background: #4caf50;
}

.phase-info {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 12px;
}

.phase-name {
  font-size: 13px;
  font-weight: 600;
  color: #e94560;
  margin-bottom: 4px;
}

.phase-time {
  font-size: 18px;
  font-weight: 500;
  color: #fff;
  margin-bottom: 6px;
}

.phase-progress {
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.phase-progress-fill {
  height: 100%;
  background: #e94560;
  transition: width 1s linear;
}

.timer-controls {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.control-btn {
  flex: 1;
  padding: 8px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.control-btn.start {
  background: #4caf50;
  color: white;
}

.control-btn.pause {
  background: #ff9800;
  color: white;
}

.control-btn.reset {
  flex: 0;
  width: 36px;
  background: rgba(255, 255, 255, 0.1);
  color: #aaa;
}

.control-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.phase-timeline {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.timeline-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 11px;
  color: #888;
  background: rgba(255, 255, 255, 0.02);
}

.timeline-item.current {
  background: rgba(233, 69, 96, 0.2);
  color: #fff;
}

.timeline-item.current .timeline-label {
  color: #e94560;
  font-weight: 600;
}

.timeline-item.completed {
  color: #4caf50;
}

.timeline-item.completed .timeline-label {
  text-decoration: line-through;
  opacity: 0.6;
}

.timeline-duration {
  font-family: 'JetBrains Mono', monospace;
}
</style>


