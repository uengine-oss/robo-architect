<script setup lang="ts">
import { ref } from 'vue'
import { useSessionStore } from '../../stores/session'

const sessionStore = useSessionStore()
const showList = ref(false)

function toggleList() {
  showList.value = !showList.value
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

// Generate consistent color from name
function getColor(name: string): string {
  const colors = [
    '#e94560', '#ff6b6b', '#4ecdc4', '#45b7d1', 
    '#96ceb4', '#ffeaa7', '#dfe6e9', '#a29bfe'
  ]
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}
</script>

<template>
  <div class="participant-list-wrapper">
    <button class="participant-btn" @click="toggleList">
      <span class="count">{{ sessionStore.participants.length }}</span>
      <span class="icon">👥</span>
    </button>

    <div v-if="showList" class="participant-dropdown">
      <h4>참가자 ({{ sessionStore.participants.length }})</h4>
      
      <ul class="participant-list">
        <li
          v-for="participant in sessionStore.participants"
          :key="participant.id"
          class="participant-item"
        >
          <div 
            class="avatar"
            :style="{ backgroundColor: getColor(participant.name) }"
          >
            {{ getInitials(participant.name) }}
          </div>
          <span class="name">{{ participant.name }}</span>
          <span 
            v-if="participant.name === sessionStore.currentUser" 
            class="you-badge"
          >
            you
          </span>
        </li>
      </ul>

      <div v-if="sessionStore.participants.length === 0" class="empty-state">
        아직 참가자가 없습니다
      </div>
    </div>

    <!-- Click outside to close -->
    <div 
      v-if="showList" 
      class="backdrop"
      @click="showList = false"
    />
  </div>
</template>

<style scoped>
.participant-list-wrapper {
  position: relative;
}

.participant-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
}

.participant-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.count {
  font-weight: 600;
  font-size: 14px;
}

.icon {
  font-size: 16px;
}

.backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 99;
}

.participant-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  width: 240px;
  background: #1a1a2e;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  padding: 12px;
  z-index: 100;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.participant-dropdown h4 {
  margin: 0 0 12px;
  font-size: 12px;
  color: #888;
  text-transform: uppercase;
}

.participant-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.participant-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.participant-item:last-child {
  border-bottom: none;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.7);
}

.name {
  flex: 1;
  color: #fff;
  font-size: 13px;
}

.you-badge {
  font-size: 10px;
  color: #4caf50;
  background: rgba(76, 175, 80, 0.2);
  padding: 2px 6px;
  border-radius: 4px;
}

.empty-state {
  color: #666;
  font-size: 12px;
  text-align: center;
  padding: 16px 0;
}
</style>


