<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useVideoStore } from '../../stores/video'

const videoStore = useVideoStore()

const localVideoRef = ref<HTMLVideoElement | null>(null)
const peerVideoRefs = ref<Map<string, HTMLVideoElement>>(new Map())

// Set local video source
watch(() => videoStore.localStream, (stream) => {
  if (localVideoRef.value && stream) {
    localVideoRef.value.srcObject = stream
  }
})

// Set peer video sources
function setPeerVideoRef(peerId: string, el: HTMLVideoElement | null) {
  if (el) {
    peerVideoRefs.value.set(peerId, el)
    const peer = videoStore.peers.get(peerId)
    if (peer?.stream) {
      el.srcObject = peer.stream
    }
  }
}

// Watch for peer stream changes
watch(
  () => [...videoStore.peers.values()],
  (peers) => {
    peers.forEach(peer => {
      const videoEl = peerVideoRefs.value.get(peer.id)
      if (videoEl && peer.stream && videoEl.srcObject !== peer.stream) {
        videoEl.srcObject = peer.stream
      }
    })
  },
  { deep: true }
)

onMounted(() => {
  if (localVideoRef.value && videoStore.localStream) {
    localVideoRef.value.srcObject = videoStore.localStream
  }
})
</script>

<template>
  <div class="video-panel">
    <h3 class="panel-title">Video</h3>

    <!-- Local video -->
    <div class="video-container local">
      <video
        ref="localVideoRef"
        autoplay
        playsinline
        muted
        class="video-element"
        :class="{ muted: videoStore.videoMuted }"
      />
      <div class="video-label">You</div>
      <div class="video-controls">
        <button
          class="control-btn"
          :class="{ active: !videoStore.audioMuted }"
          @click="videoStore.toggleAudio()"
        >
          {{ videoStore.audioMuted ? '🔇' : '🎤' }}
        </button>
        <button
          class="control-btn"
          :class="{ active: !videoStore.videoMuted }"
          @click="videoStore.toggleVideo()"
        >
          {{ videoStore.videoMuted ? '📷' : '🎥' }}
        </button>
        <button
          class="control-btn"
          :class="{ active: videoStore.isScreenSharing }"
          @click="videoStore.isScreenSharing ? videoStore.stopScreenShare() : videoStore.startScreenShare()"
        >
          {{ videoStore.isScreenSharing ? '🖥️' : '💻' }}
        </button>
      </div>
    </div>

    <!-- Peer videos (excluding AI) -->
    <div 
      v-for="peer in videoStore.peerList.filter(p => p.id !== 'ai-facilitator')"
      :key="peer.id"
      class="video-container"
    >
      <video
        :ref="(el) => setPeerVideoRef(peer.id, el as HTMLVideoElement)"
        autoplay
        playsinline
        class="video-element"
        :class="{ muted: peer.videoMuted }"
      />
      <div class="video-label">{{ peer.name }}</div>
      <div v-if="peer.audioMuted" class="mute-indicator">🔇</div>
    </div>

    <!-- AI Facilitator (audio only participant) -->
    <div v-if="videoStore.aiConnected" class="ai-participant">
      <div class="ai-avatar-container" :class="{ speaking: videoStore.peers.get('ai-facilitator')?.stream }">
        <span class="ai-avatar">🤖</span>
        <div class="audio-waves" v-if="videoStore.peers.get('ai-facilitator')?.stream">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
      <div class="ai-info">
        <span class="ai-name">AI 퍼실리테이터</span>
        <span class="ai-status-text">
          {{ videoStore.isAIHost ? '호스트 (내가 연결)' : '연결됨' }}
        </span>
      </div>
      <!-- Hidden audio element for AI -->
      <audio
        v-if="videoStore.peers.get('ai-facilitator')?.stream"
        :srcObject="videoStore.peers.get('ai-facilitator')?.stream"
        autoplay
        style="display: none;"
      />
    </div>
  </div>
</template>

<style scoped>
.video-panel {
  padding: 12px;
  overflow-y: auto;
}

.panel-title {
  font-size: 12px;
  text-transform: uppercase;
  color: #888;
  margin: 0 0 12px;
}

.video-container {
  position: relative;
  margin-bottom: 12px;
  border-radius: 8px;
  overflow: hidden;
  background: #000;
  aspect-ratio: 16/9;
}

.video-container.local {
  border: 2px solid #e94560;
}

.video-element {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-element.muted {
  filter: grayscale(1);
  opacity: 0.5;
}

.video-label {
  position: absolute;
  bottom: 8px;
  left: 8px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.video-controls {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
  gap: 4px;
}

.control-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.control-btn:hover {
  background: rgba(0, 0, 0, 0.8);
}

.control-btn.active {
  background: rgba(76, 175, 80, 0.6);
}

.mute-indicator {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(244, 67, 54, 0.8);
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

/* AI Participant Styles */
.ai-participant {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.2) 0%, rgba(76, 175, 80, 0.2) 100%);
  border-radius: 8px;
  border: 1px solid rgba(233, 69, 96, 0.4);
  margin-bottom: 12px;
}

.ai-avatar-container {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.ai-avatar-container.speaking {
  animation: ai-pulse 1.5s ease-in-out infinite;
}

@keyframes ai-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.4); }
  50% { box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
}

.ai-avatar {
  font-size: 28px;
}

.audio-waves {
  position: absolute;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 2px;
  align-items: flex-end;
  height: 12px;
}

.audio-waves span {
  width: 3px;
  background: #4caf50;
  border-radius: 2px;
  animation: wave 0.5s ease-in-out infinite;
}

.audio-waves span:nth-child(1) { height: 4px; animation-delay: 0s; }
.audio-waves span:nth-child(2) { height: 8px; animation-delay: 0.1s; }
.audio-waves span:nth-child(3) { height: 4px; animation-delay: 0.2s; }

@keyframes wave {
  0%, 100% { transform: scaleY(1); }
  50% { transform: scaleY(1.5); }
}

.ai-info {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.ai-name {
  font-weight: 600;
  color: white;
  font-size: 13px;
}

.ai-status-text {
  font-size: 11px;
  color: #4caf50;
}
</style>

