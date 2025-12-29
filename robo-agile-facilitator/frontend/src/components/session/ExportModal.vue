<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSessionStore } from '../../stores/session'

const props = defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const sessionStore = useSessionStore()

const isLoading = ref(false)
const activeTab = ref<'summary' | 'json' | 'mermaid'>('summary')
const exportData = ref<any>(null)
const error = ref<string | null>(null)

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function loadExport(type: 'summary' | 'json' | 'mermaid') {
  if (!sessionStore.session) return

  activeTab.value = type
  isLoading.value = true
  error.value = null
  exportData.value = null

  try {
    const response = await fetch(
      `${API_BASE}/api/sessions/${sessionStore.session.id}/export/${type}`
    )

    if (!response.ok) throw new Error('Export failed')

    exportData.value = await response.json()
  } catch (e) {
    error.value = '내보내기 중 오류가 발생했습니다.'
  } finally {
    isLoading.value = false
  }
}

function downloadJSON() {
  if (!exportData.value) return

  const blob = new Blob([JSON.stringify(exportData.value, null, 2)], {
    type: 'application/json'
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${sessionStore.session?.title || 'session'}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function downloadMermaid() {
  if (!exportData.value?.mermaid) return

  const blob = new Blob([exportData.value.mermaid], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${sessionStore.session?.title || 'session'}.mmd`
  a.click()
  URL.revokeObjectURL(url)
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text)
  alert('클립보드에 복사되었습니다!')
}

// Load summary by default when modal opens
const isOpenComputed = computed(() => props.isOpen)
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="modal-overlay" @click.self="emit('close')">
      <div class="modal-container">
        <header class="modal-header">
          <h2>세션 내보내기</h2>
          <button class="close-btn" @click="emit('close')">×</button>
        </header>

        <nav class="tab-nav">
          <button
            :class="{ active: activeTab === 'summary' }"
            @click="loadExport('summary')"
          >
            📊 AI 요약
          </button>
          <button
            :class="{ active: activeTab === 'json' }"
            @click="loadExport('json')"
          >
            📄 JSON
          </button>
          <button
            :class="{ active: activeTab === 'mermaid' }"
            @click="loadExport('mermaid')"
          >
            📈 Mermaid
          </button>
        </nav>

        <div class="modal-content">
          <!-- Loading -->
          <div v-if="isLoading" class="loading-state">
            <div class="spinner"></div>
            <p>로딩 중...</p>
          </div>

          <!-- Error -->
          <div v-else-if="error" class="error-state">
            <p>{{ error }}</p>
          </div>

          <!-- Empty state -->
          <div v-else-if="!exportData" class="empty-state">
            <p>탭을 선택하여 내보내기</p>
          </div>

          <!-- Summary Tab -->
          <div v-else-if="activeTab === 'summary'" class="summary-content">
            <div class="statistics">
              <div class="stat-item">
                <span class="stat-value">{{ exportData.statistics?.total_stickers || 0 }}</span>
                <span class="stat-label">전체 스티커</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ exportData.statistics?.events || 0 }}</span>
                <span class="stat-label">이벤트</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ exportData.statistics?.commands || 0 }}</span>
                <span class="stat-label">커맨드</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ exportData.statistics?.policies || 0 }}</span>
                <span class="stat-label">정책</span>
              </div>
            </div>

            <div class="summary-text">
              <h3>AI 분석 결과</h3>
              <pre>{{ exportData.summary }}</pre>
            </div>

            <div class="event-list">
              <h3>주요 이벤트</h3>
              <ul>
                <li v-for="event in exportData.events?.slice(0, 10)" :key="event.id">
                  {{ event.text }}
                  <span class="author">by {{ event.author }}</span>
                </li>
              </ul>
            </div>
          </div>

          <!-- JSON Tab -->
          <div v-else-if="activeTab === 'json'" class="json-content">
            <div class="toolbar">
              <button @click="downloadJSON">📥 다운로드</button>
              <button @click="copyToClipboard(JSON.stringify(exportData, null, 2))">
                📋 복사
              </button>
            </div>
            <pre class="code-block">{{ JSON.stringify(exportData, null, 2) }}</pre>
          </div>

          <!-- Mermaid Tab -->
          <div v-else-if="activeTab === 'mermaid'" class="mermaid-content">
            <div class="toolbar">
              <button @click="downloadMermaid">📥 다운로드</button>
              <button @click="copyToClipboard(exportData.mermaid || '')">
                📋 복사
              </button>
            </div>
            <pre class="code-block">{{ exportData.mermaid }}</pre>
            <p class="hint">
              💡 이 코드를 <a href="https://mermaid.live" target="_blank">mermaid.live</a>에 
              붙여넣어 다이어그램을 확인하세요.
            </p>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  background: #1a1a2e;
  border-radius: 16px;
  width: 90%;
  max-width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: #fff;
}

.close-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.close-btn:hover {
  color: #fff;
}

.tab-nav {
  display: flex;
  gap: 4px;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.tab-nav button {
  flex: 1;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: none;
  border-radius: 8px;
  color: #888;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.tab-nav button:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.tab-nav button.active {
  background: rgba(233, 69, 96, 0.2);
  color: #e94560;
}

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: #888;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: #e94560;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.statistics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-item {
  text-align: center;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}

.stat-value {
  display: block;
  font-size: 2rem;
  font-weight: 700;
  color: #e94560;
}

.stat-label {
  display: block;
  font-size: 0.8rem;
  color: #888;
  margin-top: 4px;
}

.summary-text h3,
.event-list h3 {
  font-size: 1rem;
  color: #fff;
  margin: 0 0 0.75rem;
}

.summary-text pre {
  background: rgba(255, 255, 255, 0.05);
  padding: 1rem;
  border-radius: 8px;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 0.9rem;
  color: #ccc;
  line-height: 1.6;
  margin-bottom: 1.5rem;
}

.event-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.event-list li {
  padding: 0.5rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  color: #fff;
  font-size: 0.9rem;
}

.event-list .author {
  color: #888;
  font-size: 0.8rem;
  margin-left: 0.5rem;
}

.toolbar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.toolbar button {
  padding: 0.5rem 1rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  font-size: 0.85rem;
}

.toolbar button:hover {
  background: rgba(255, 255, 255, 0.2);
}

.code-block {
  background: rgba(0, 0, 0, 0.3);
  padding: 1rem;
  border-radius: 8px;
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 0.8rem;
  color: #4caf50;
  overflow-x: auto;
  white-space: pre;
  line-height: 1.4;
  max-height: 400px;
}

.hint {
  margin-top: 1rem;
  font-size: 0.85rem;
  color: #888;
}

.hint a {
  color: #e94560;
}
</style>


