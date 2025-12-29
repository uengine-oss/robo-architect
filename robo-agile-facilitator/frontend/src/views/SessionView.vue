<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useSessionStore } from '../stores/session'
import { useVideoStore } from '../stores/video'
import CanvasBoard from '../components/canvas/CanvasBoard.vue'
import VideoPanel from '../components/video/VideoPanel.vue'
import StickerPalette from '../components/canvas/StickerPalette.vue'
import AIFeedbackPanel from '../components/ai/AIFeedbackPanel.vue'
import PhaseIndicator from '../components/session/PhaseIndicator.vue'
import ParticipantList from '../components/session/ParticipantList.vue'
import ExportModal from '../components/session/ExportModal.vue'
import HeaderTimer from '../components/session/HeaderTimer.vue'

const route = useRoute()
const sessionStore = useSessionStore()
const videoStore = useVideoStore()

const sessionId = route.params.id as string
const participantName = ref('')
const isJoining = ref(false)
const hasJoined = ref(false)
const showVideo = ref(true)
const showExport = ref(false)
const isLoadingSession = ref(true)
const error = ref<string | null>(null)

// Refs for timer and AI panel integration
const timerRef = ref<InstanceType<typeof HeaderTimer> | null>(null)
const aiPanelRef = ref<InstanceType<typeof AIFeedbackPanel> | null>(null)

// Timer event handlers - forward to AI panel
function onTimeWarning(data: { type: string; minutesLeft: number; phase: string }) {
  aiPanelRef.value?.handleTimeWarning(data)
}

function onPhaseTimeUp(phase: string) {
  aiPanelRef.value?.handlePhaseTimeUp(phase)
  // Optionally auto-advance phase
  const nextPhase = getNextPhase(phase)
  if (nextPhase) {
    sessionStore.updatePhase(nextPhase as any)
  }
}

function onWorkshopEnd() {
  aiPanelRef.value?.handleWorkshopEnd()
}

function getNextPhase(phase: string): string | null {
  const order = ['orientation', 'event_elicitation', 'event_refinement', 'command_policy', 'timeline_ordering', 'summary']
  const idx = order.indexOf(phase)
  return idx < order.length - 1 ? order[idx + 1] : null
}

onMounted(async () => {
  try {
    await sessionStore.loadSession(sessionId)
    isLoadingSession.value = false
    
    // Restore previous participant name for this session
    const savedName = localStorage.getItem(`session_${sessionId}_name`)
    if (savedName) {
      participantName.value = savedName
    }
  } catch (e) {
    error.value = '세션을 찾을 수 없습니다.'
    isLoadingSession.value = false
  }
})

onUnmounted(() => {
  sessionStore.disconnectSocket()
  videoStore.disconnect()
})

async function joinSession() {
  if (!participantName.value.trim()) return

  isJoining.value = true
  try {
    // Initialize local media
    await videoStore.initLocalMedia()

    // Save participant name for reconnection
    localStorage.setItem(`session_${sessionId}_name`, participantName.value.trim())

    // Connect to session
    sessionStore.connectSocket(sessionId, participantName.value.trim())
    videoStore.connectVideo(sessionId, participantName.value.trim())

    hasJoined.value = true
  } catch (e) {
    console.error('Failed to join session:', e)
    error.value = '세션 참여에 실패했습니다.'
  } finally {
    isJoining.value = false
  }
}

</script>

<template>
  <div class="session-view">
    <!-- Loading state -->
    <div v-if="isLoadingSession" class="loading">
      <div class="spinner"></div>
      <p>세션 로딩 중...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-state">
      <h2>오류</h2>
      <p>{{ error }}</p>
      <router-link to="/" class="back-link">홈으로 돌아가기</router-link>
    </div>

    <!-- Join dialog -->
    <div v-else-if="!hasJoined" class="join-dialog">
      <div class="join-card">
        <h2>{{ sessionStore.session?.title }}</h2>
        <p class="session-desc">{{ sessionStore.session?.description }}</p>
        
        <div class="form-group">
          <label for="name">이름을 입력하세요</label>
          <input
            id="name"
            v-model="participantName"
            type="text"
            placeholder="홍길동"
            :disabled="isJoining"
            @keyup.enter="joinSession"
          />
        </div>

        <button
          class="join-btn"
          :disabled="!participantName.trim() || isJoining"
          @click="joinSession"
        >
          {{ isJoining ? '참여 중...' : '세션 참여하기' }}
        </button>
      </div>
    </div>

    <!-- Main session interface -->
    <div v-else class="session-main">
      <!-- Header -->
      <header class="session-header">
        <div class="header-left">
          <h1>{{ sessionStore.session?.title }}</h1>
          <PhaseIndicator />
        </div>
        
        <!-- Center: Timer -->
        <div class="header-center">
          <HeaderTimer 
            ref="timerRef"
            :total-minutes="sessionStore.session?.duration_minutes"
            @time-warning="onTimeWarning"
            @phase-time-up="onPhaseTimeUp"
            @workshop-end="onWorkshopEnd"
          />
        </div>
        
        <div class="header-right">
          <button 
            class="toggle-video-btn"
            @click="showVideo = !showVideo"
          >
            {{ showVideo ? '🎥' : '📹' }}
          </button>
          <button 
            class="export-btn"
            @click="showExport = true"
          >
            📤 내보내기
          </button>
          <ParticipantList />
        </div>
      </header>

      <!-- Main content -->
      <div class="session-content">
        <!-- Left sidebar: Sticker palette -->
        <aside class="left-sidebar">
          <StickerPalette />
        </aside>

        <!-- Canvas -->
        <main class="canvas-area">
          <CanvasBoard />
        </main>

        <!-- Right sidebar: Video + AI -->
        <aside class="right-sidebar" :class="{ hidden: !showVideo }">
          <VideoPanel />
          <AIFeedbackPanel ref="aiPanelRef" />
        </aside>
      </div>

      <!-- Export Modal -->
      <ExportModal :is-open="showExport" @close="showExport = false" />
    </div>
  </div>
</template>

<style scoped>
.session-view {
  height: 100vh;
  background: #1a1a2e;
  color: #fff;
  display: flex;
  flex-direction: column;
}

.loading,
.error-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-top-color: #e94560;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state h2 {
  color: #e94560;
}

.back-link {
  color: #e94560;
  text-decoration: none;
  margin-top: 1rem;
}

/* Join Dialog */
.join-dialog {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.join-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 2rem;
  max-width: 400px;
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.join-card h2 {
  margin: 0 0 0.5rem;
  color: #fff;
}

.session-desc {
  color: #a0a0a0;
  margin-bottom: 1.5rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #b0b0b0;
}

.form-group input {
  width: 100%;
  padding: 0.8rem 1rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #fff;
  font-size: 1rem;
}

.form-group input:focus {
  outline: none;
  border-color: #e94560;
}

.join-btn {
  width: 100%;
  padding: 1rem;
  background: linear-gradient(135deg, #e94560 0%, #ff6b6b 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
}

.join-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Session Main */
.session-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex: 1;
}

.header-left h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.header-center {
  flex: 0 0 auto;
  margin: 0 1rem;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.toggle-video-btn {
  padding: 0.5rem 0.75rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  font-size: 1.2rem;
}

.export-btn {
  padding: 0.5rem 1rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.export-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* Session Content */
.session-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.left-sidebar {
  width: 80px;
  background: rgba(0, 0, 0, 0.2);
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0.5rem;
}

.canvas-area {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.right-sidebar {
  width: 320px;
  background: rgba(0, 0, 0, 0.2);
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  transition: width 0.3s, opacity 0.3s;
}

.right-sidebar.hidden {
  width: 0;
  opacity: 0;
  overflow: hidden;
}
</style>

