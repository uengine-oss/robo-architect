<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { useModelModifierStore } from '@/features/modelModifier/modelModifier.store'
import { useCanvasStore } from '@/features/canvas/canvas.store'

const chatStore = useModelModifierStore()
const canvasStore = useCanvasStore()

const inputText = ref('')
const messagesContainer = ref(null)

// Selected nodes as chips
const selectedChips = computed(() => {
  return canvasStore.selectedNodes.map(n => ({
    id: n.id,
    name: n.data?.name || n.data?.label || n.id,
    type: n.data?.type || n.type
  }))
})

function getTypeColor(type) {
  const colors = {
    command: 'var(--color-command)',
    Command: 'var(--color-command)',
    event: 'var(--color-event)',
    Event: 'var(--color-event)',
    policy: 'var(--color-policy)',
    Policy: 'var(--color-policy)',
    aggregate: 'var(--color-aggregate)',
    Aggregate: 'var(--color-aggregate)',
    boundedcontext: 'var(--color-bc)',
    BoundedContext: 'var(--color-bc)',
    ui: 'var(--color-ui)',
    UI: 'var(--color-ui)',
    readmodel: 'var(--color-readmodel)',
    ReadModel: 'var(--color-readmodel)'
  }
  return colors[type] || 'var(--color-text-light)'
}

function getTypeIcon(type) {
  const icons = {
    command: 'C',
    Command: 'C',
    event: 'E',
    Event: 'E',
    policy: 'P',
    Policy: 'P',
    aggregate: 'A',
    Aggregate: 'A',
    boundedcontext: 'BC',
    BoundedContext: 'BC',
    ui: 'UI',
    UI: 'UI',
    readmodel: 'RM',
    ReadModel: 'RM'
  }
  return icons[type] || '?'
}

function removeChip(nodeId) {
  canvasStore.removeFromSelection(nodeId)
}

async function sendMessage() {
  if (!inputText.value.trim() || chatStore.isProcessing) return
  const message = inputText.value
  inputText.value = ''
  await chatStore.sendMessage(message)
  scrollToBottom()
}

function handleKeyDown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, () => {
  scrollToBottom()
})

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<template>
  <div class="chat-panel">
    <div class="chat-panel__header">
      <div class="chat-panel__title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <span>Model Modifier</span>
      </div>
      <button
        v-if="chatStore.hasMessages"
        class="chat-panel__clear-btn"
        @click="chatStore.clearMessages()"
        title="Clear chat"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      </button>
    </div>

    <div class="chat-panel__messages" ref="messagesContainer">
      <div v-if="!chatStore.hasMessages" class="chat-empty">
        <div class="chat-empty__icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        </div>
        <div class="chat-empty__text">
          캔버스에서 객체를 선택하고<br />
          수정 요청을 입력하세요
        </div>
        <div class="chat-empty__hint">
          예: "이 Command의 이름을 변경하고 관련 Event도 업데이트해줘"
        </div>
      </div>

      <div v-else class="chat-messages">
        <div
          v-for="message in chatStore.messages"
          :key="message.id"
          :class="['chat-message', `chat-message--${message.type}`, { 'chat-message--error': message.isError }]"
        >
          <template v-if="message.type === 'user'">
            <div class="chat-message__header">
              <span class="chat-message__sender">You</span>
              <span class="chat-message__time">{{ formatTime(message.timestamp) }}</span>
            </div>
            <div class="chat-message__selected-nodes">
              <span
                v-for="node in message.selectedNodes"
                :key="node.id"
                class="chat-chip chat-chip--small"
                :style="{ borderColor: getTypeColor(node.type) }"
              >
                <span class="chat-chip__icon" :style="{ background: getTypeColor(node.type) }">
                  {{ getTypeIcon(node.type) }}
                </span>
                {{ node.name }}
              </span>
            </div>
            <div class="chat-message__content">{{ message.content }}</div>
          </template>

          <template v-else-if="message.type === 'assistant'">
            <div class="chat-message__header">
              <span class="chat-message__sender">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
                </svg>
                Agent
              </span>
              <span class="chat-message__time">{{ formatTime(message.timestamp) }}</span>
            </div>

            <div v-if="message.reactSteps && message.reactSteps.length > 0" class="chat-react-trace">
              <div
                v-for="(step, idx) in message.reactSteps"
                :key="idx"
                :class="['chat-react-step', `chat-react-step--${step.type}`]"
              >
                <span class="chat-react-step__label">
                  {{ step.type === 'thought' ? '💭' : step.type === 'action' ? '⚡' : '👁️' }}
                </span>
                <span class="chat-react-step__content">{{ step.content }}</span>
              </div>
            </div>

            <div v-if="message.changes && message.changes.length > 0" class="chat-changes">
              <div class="chat-changes__header">변경 사항:</div>
              <div v-for="(change, idx) in message.changes" :key="idx" class="chat-change-item">
                <span :class="['chat-change-item__action', `chat-change-item__action--${change.action}`]">
                  {{ change.action }}
                </span>
                <span class="chat-change-item__target">{{ change.targetName }}</span>
              </div>
            </div>

            <div class="chat-message__content" v-html="message.content"></div>
          </template>

          <template v-else-if="message.type === 'system'">
            <div class="chat-message__content">{{ message.content }}</div>
          </template>
        </div>

        <div v-if="chatStore.isProcessing" class="chat-processing">
          <div class="chat-processing__indicator">
            <div class="chat-processing__dot"></div>
            <div class="chat-processing__dot"></div>
            <div class="chat-processing__dot"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-panel__input-area">
      <div v-if="selectedChips.length > 0" class="chat-input__chips">
        <span
          v-for="chip in selectedChips"
          :key="chip.id"
          class="chat-chip"
          :style="{ borderColor: getTypeColor(chip.type) }"
        >
          <span class="chat-chip__icon" :style="{ background: getTypeColor(chip.type) }">
            {{ getTypeIcon(chip.type) }}
          </span>
          <span class="chat-chip__name">{{ chip.name }}</span>
          <button class="chat-chip__remove" @click="removeChip(chip.id)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </span>
      </div>

      <div v-else class="chat-input__hint">
        캔버스에서 객체를 선택하세요 (Ctrl/Cmd+Click으로 다중 선택)
      </div>

      <div class="chat-input__wrapper">
        <textarea
          v-model="inputText"
          class="chat-input__textarea"
          placeholder="수정 요청을 입력하세요..."
          :disabled="chatStore.isProcessing || selectedChips.length === 0"
          @keydown="handleKeyDown"
          rows="1"
        ></textarea>
        <button
          class="chat-input__send"
          :disabled="!inputText.trim() || chatStore.isProcessing || selectedChips.length === 0"
          @click="sendMessage"
        >
          <svg v-if="!chatStore.isProcessing" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin">
            <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="12"></circle>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg-secondary);
  border-left: 1px solid var(--color-border);
}

.chat-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.chat-panel__title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.chat-panel__clear-btn {
  background: none;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.chat-panel__clear-btn:hover {
  background: var(--color-bg);
  color: var(--color-text);
}

.chat-panel__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: var(--color-text-light);
}

.chat-empty__icon {
  margin-bottom: var(--spacing-md);
}

.chat-empty__text {
  font-size: 0.875rem;
  line-height: 1.5;
  margin-bottom: var(--spacing-sm);
}

.chat-empty__hint {
  font-size: 0.75rem;
  opacity: 0.7;
  max-width: 200px;
}

.chat-messages {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.chat-message {
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  animation: slideIn 0.2s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-message--user {
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
}

.chat-message--assistant {
  background: linear-gradient(135deg, rgba(34, 139, 230, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
  border: 1px solid rgba(34, 139, 230, 0.2);
}

.chat-message--system {
  background: var(--color-bg);
  text-align: center;
  font-size: 0.8rem;
  color: var(--color-text-light);
}

.chat-message--error {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
}

.chat-message__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-xs);
}

.chat-message__sender {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.chat-message__time {
  font-size: 0.65rem;
  color: var(--color-text-light);
}

.chat-message__selected-nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: var(--spacing-xs);
}

.chat-message__content {
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--color-text);
}

.chat-react-trace {
  margin-bottom: var(--spacing-sm);
  padding: var(--spacing-xs);
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
}

.chat-react-step {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-xs);
  padding: 2px 0;
}

.chat-react-step__label {
  flex-shrink: 0;
}

.chat-react-step__content {
  color: var(--color-text-light);
}

.chat-react-step--thought .chat-react-step__content { color: #a78bfa; }
.chat-react-step--action .chat-react-step__content { color: #34d399; }
.chat-react-step--observation .chat-react-step__content { color: #60a5fa; }

.chat-changes {
  margin: var(--spacing-sm) 0;
  padding: var(--spacing-sm);
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-sm);
}

.chat-changes__header {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-text-light);
  margin-bottom: var(--spacing-xs);
}

.chat-change-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 0.75rem;
  padding: 2px 0;
}

.chat-change-item__action {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}

.chat-change-item__action--create { background: rgba(52, 211, 153, 0.2); color: #34d399; }
.chat-change-item__action--update { background: rgba(96, 165, 250, 0.2); color: #60a5fa; }
.chat-change-item__action--rename { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
.chat-change-item__action--delete { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
.chat-change-item__action--connect { background: rgba(167, 139, 250, 0.2); color: #a78bfa; }

.chat-processing {
  padding: var(--spacing-md);
  text-align: center;
}

.chat-processing__indicator {
  display: flex;
  justify-content: center;
  gap: 4px;
  margin-bottom: var(--spacing-sm);
}

.chat-processing__dot {
  width: 8px;
  height: 8px;
  background: var(--color-accent);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.chat-processing__dot:nth-child(1) { animation-delay: -0.32s; }
.chat-processing__dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.chat-processing__thought,
.chat-processing__action {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-top: var(--spacing-xs);
}

.chat-panel__input-area {
  padding: var(--spacing-sm) var(--spacing-md);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg);
}

.chat-input__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: var(--spacing-sm);
  max-height: 80px;
  overflow-y: auto;
}

.chat-input__hint {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-bottom: var(--spacing-sm);
  text-align: center;
}

.chat-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px 2px 2px;
  background: var(--color-bg-tertiary);
  border: 1px solid;
  border-radius: 16px;
  font-size: 0.75rem;
  color: var(--color-text);
}

.chat-chip--small {
  font-size: 0.7rem;
  padding: 1px 6px 1px 1px;
}

.chat-chip__icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 0.6rem;
  font-weight: 600;
  color: white;
}

.chat-chip--small .chat-chip__icon {
  width: 14px;
  height: 14px;
  font-size: 0.5rem;
}

.chat-chip__name {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-chip__remove {
  background: none;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.15s ease;
}

.chat-chip__remove:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-text);
}

.chat-input__wrapper {
  display: flex;
  align-items: flex-end;
  gap: var(--spacing-sm);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-xs);
  transition: border-color 0.15s ease;
}

.chat-input__wrapper:focus-within {
  border-color: var(--color-accent);
}

.chat-input__textarea {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--color-text);
  font-family: inherit;
  font-size: 0.875rem;
  resize: none;
  padding: var(--spacing-xs);
  min-height: 36px;
  max-height: 120px;
}

.chat-input__textarea:focus {
  outline: none;
}

.chat-input__textarea::placeholder {
  color: var(--color-text-light);
}

.chat-input__textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-input__send {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-accent);
  border: none;
  border-radius: var(--radius-sm);
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.chat-input__send:hover:not(:disabled) {
  background: #1c7ed6;
  transform: scale(1.05);
}

.chat-input__send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>


