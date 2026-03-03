<script setup>
import { ref, computed, nextTick, watch, inject } from 'vue'
import { useModelModifierStore } from '@/features/modelModifier/modelModifier.store'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useIngestionStore } from '@/features/requirementsIngestion/ingestion.store'
import ImpactDetailsModal from '@/features/modelModifier/ui/ImpactDetailsModal.vue'

const emit = defineEmits(['close'])

const chatStore = useModelModifierStore()
const canvasStore = useCanvasStore()
const ingestionStore = useIngestionStore()

// Inject Inspector opening functions from CanvasWorkspace
const inspectorFunctions = inject('openInspector', null)

const inputText = ref('')
const messagesContainer = ref(null)
const isComposing = ref(false)
const isDragOver = ref(false)

// Impact details modal state
const isImpactModalOpen = ref(false)
const impactModalSeedNodes = ref([])
const impactModalSummary = ref(null)

// Selected nodes as chips
const selectedChips = computed(() => {
  // Use modelModifierStore's currentSelectedNodes which handles both Design and other viewers
  const nodes = chatStore.currentSelectedNodes
  return nodes.map(n => {
    // Handle both VueFlow node format (Design) and plain object format (other viewers)
    const nodeData = n.data || n
    return {
      id: n.id || nodeData.id,
      name: nodeData?.name || nodeData?.label || n.id || nodeData.id,
      type: nodeData?.type || n.type || nodeData.type
    }
  })
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
  // Remove from appropriate store based on viewer
  if (chatStore.selectedNodes.length > 0) {
    // Other viewer (Big Picture, Aggregate)
    chatStore.setSelectedNodes(chatStore.selectedNodes.filter(n => (n.id || n.data?.id) !== nodeId))
  } else {
    // Design viewer
    canvasStore.removeFromSelection(nodeId)
  }
}

async function sendMessage() {
  if (!inputText.value.trim() || chatStore.isProcessing || isComposing.value) return
  
  // Wait for composition to complete if needed
  await nextTick()
  
  const message = inputText.value.trim()
  if (!message) return
  
  inputText.value = ''
  await chatStore.sendMessage(message)
  scrollToBottom()
}

function handleKeyDown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !isComposing.value) {
    event.preventDefault()
    sendMessage()
  }
}

function handleCompositionStart() {
  isComposing.value = true
}

function handleCompositionEnd() {
  isComposing.value = false
}

// Drag and drop handlers for Navigator nodes
function handleDragOver(event) {
  event.preventDefault()
  event.stopPropagation()
  isDragOver.value = true
  event.dataTransfer.dropEffect = 'copy'
}

function handleDragLeave(event) {
  event.preventDefault()
  event.stopPropagation()
  isDragOver.value = false
}

function handleDrop(event) {
  event.preventDefault()
  event.stopPropagation()
  isDragOver.value = false
  
  try {
    const data = event.dataTransfer.getData('application/json')
    if (!data) return
    
    const nodeData = JSON.parse(data)
    if (!nodeData || !nodeData.id) return
    
    // Convert navigator node format to chat selection format
    const selectedNode = {
      id: nodeData.id || nodeData.nodeId,
      name: nodeData.nodeData?.name || nodeData.name || nodeData.id,
      type: nodeData.type || nodeData.nodeType || nodeData.nodeData?.type,
      description: nodeData.nodeData?.description,
      bcId: nodeData.nodeData?.bcId,
      bcName: nodeData.nodeData?.bcName,
      aggregateId: nodeData.nodeData?.aggregateId,
      ...nodeData.nodeData
    }
    
    // Add to selection (check if already selected)
    const currentNodes = chatStore.currentSelectedNodes
    const isAlreadySelected = currentNodes.some(n => (n.id || n.data?.id) === selectedNode.id)
    
    if (!isAlreadySelected) {
      // Add to selection based on viewer
      if (chatStore.selectedNodes.length > 0) {
        // Other viewer (Big Picture, Aggregate)
        chatStore.setSelectedNodes([...chatStore.selectedNodes, selectedNode])
      } else {
        // Design viewer - add to canvas selection
        // First check if node exists on canvas, if not, we still add it to chat selection
        const existingNode = canvasStore.nodes.find(n => n.id === selectedNode.id)
        if (existingNode) {
          canvasStore.addToSelection(selectedNode.id)
        } else {
          // Node not on canvas, add to chat selection directly
          chatStore.setSelectedNodes([selectedNode])
        }
      }
    }
  } catch (error) {
    console.error('Failed to handle drop:', error)
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

function getDraftFields(draft) {
  if (!draft) return []
  if (draft.action === 'rename') return ['name']
  if (draft.action === 'connect') return ['relationship']
  if (draft.action === 'delete') return ['delete']
  if (draft.action === 'create') return ['create']
  const updates = draft.updates && typeof draft.updates === 'object' ? draft.updates : {}
  return Object.keys(updates)
}

function formatValue(value) {
  if (value === null || value === undefined) return '(empty)'
  const s = typeof value === 'string' ? value : JSON.stringify(value)
  if (s.length > 240) return `${s.slice(0, 240)}… (${s.length} chars)`
  return s
}

function openImpactDetails(messageId) {
  const idx = chatStore.messages.findIndex(m => m.id === messageId)
  if (idx === -1) return

  const msg = chatStore.messages[idx]
  const summary = msg?.impactSummary || null
  // Seed nodes = previous user message's selectedNodes (seed 정의: 선택 노드만)
  const prevUser = [...chatStore.messages.slice(0, idx)].reverse().find(m => m.type === 'user')
  impactModalSeedNodes.value = Array.isArray(prevUser?.selectedNodes) ? prevUser.selectedNodes : []
  impactModalSummary.value = summary
  isImpactModalOpen.value = true
}

function closeImpactDetails() {
  isImpactModalOpen.value = false
  impactModalSeedNodes.value = []
  impactModalSummary.value = null
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
      <div class="chat-panel__header-actions">
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
          <template v-if="ingestionStore.isIngestionPaused">
            모델 생성이 일시정지되었습니다.<br />
            수정 요청을 입력하세요.
          </template>
          <template v-else>
            캔버스에서 객체를 선택하고<br />
            수정 요청을 입력하세요
          </template>
        </div>
        <div class="chat-empty__hint">
          <template v-if="ingestionStore.isIngestionPaused">
            예: "이 User Story를 주문 BC에 할당해줘" 또는 "주문 Aggregate를 추가해줘"
          </template>
          <template v-else>
            예: "이 Command의 이름을 변경하고 관련 Event도 업데이트해줘"
          </template>
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

            <div v-if="message.impactSummary" class="chat-impact-summary">
              <div class="chat-impact-summary__text">
                영향도(confirmed): <strong>{{ message.impactSummary.confirmedCount }}</strong>개
              </div>
              <button class="chat-impact-summary__btn" @click="openImpactDetails(message.id)">
                상세 보기
              </button>
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

            <div v-if="message.drafts && message.drafts.length > 0" class="chat-drafts">
              <div class="chat-drafts__header">
                <span>변경 제안 (승인 필요)</span>
                <div class="chat-drafts__bulk">
                  <button
                    class="chat-drafts__btn"
                    :disabled="chatStore.isConfirming || message.isApplied"
                    @click="chatStore.setAllDraftApprovals(message.id, true)"
                  >
                    전체 승인
                  </button>
                  <button
                    class="chat-drafts__btn"
                    :disabled="chatStore.isConfirming || message.isApplied"
                    @click="chatStore.setAllDraftApprovals(message.id, false)"
                  >
                    전체 거부
                  </button>
                </div>
              </div>

              <div v-for="draft in message.drafts" :key="draft.changeId" class="chat-draft-item">
                <label class="chat-draft-item__check">
                  <input
                    type="checkbox"
                    :checked="draft.approved"
                    :disabled="chatStore.isConfirming || message.isApplied"
                    @change="chatStore.toggleDraftApproval(message.id, draft.changeId, $event.target.checked)"
                  />
                </label>
                <div class="chat-draft-item__body">
                  <div class="chat-draft-item__top">
                    <span :class="['chat-change-item__action', `chat-change-item__action--${draft.action}`]">
                      {{ draft.action }}
                    </span>
                    <span class="chat-draft-item__target">
                      {{ draft.targetName || draft.targetId }}
                      <span class="chat-draft-item__meta">({{ draft.targetType || 'Unknown' }} · {{ draft.targetId }})</span>
                    </span>
                  </div>

                  <div class="chat-draft-item__fields">
                    <span class="chat-draft-item__label">필드:</span>
                    <span class="chat-draft-item__value">{{ getDraftFields(draft).join(', ') }}</span>
                  </div>

                  <div v-if="draft.rationale" class="chat-draft-item__rationale">
                    <span class="chat-draft-item__label">사유:</span>
                    <span class="chat-draft-item__value">{{ draft.rationale }}</span>
                  </div>

                  <div v-if="draft.before || draft.after" class="chat-draft-item__diff">
                    <div v-for="field in getDraftFields(draft)" :key="field" class="chat-draft-item__diff-row">
                      <div class="chat-draft-item__diff-field">{{ field }}</div>
                      <div class="chat-draft-item__diff-values">
                        <div class="chat-draft-item__diff-col">
                          <div class="chat-draft-item__diff-title">before</div>
                          <pre class="chat-draft-item__diff-pre">{{ formatValue(draft.before?.[field]) }}</pre>
                        </div>
                        <div class="chat-draft-item__diff-col">
                          <div class="chat-draft-item__diff-title">after</div>
                          <pre class="chat-draft-item__diff-pre">{{ formatValue(draft.after?.[field]) }}</pre>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="chat-drafts__footer">
                <button
                  class="chat-drafts__apply"
                  :disabled="chatStore.isConfirming || message.isApplied"
                  @click="chatStore.confirmDrafts(message.id)"
                >
                  선택 항목 적용
                </button>
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

    <div 
      class="chat-panel__input-area"
      :class="{ 'drag-over': isDragOver }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
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
        <template v-if="ingestionStore.isIngestionActive">
          모델 생성이 진행 중입니다. 생성이 완료되거나 일시정지한 후 수정 요청을 보내주세요.
        </template>
        <template v-else-if="ingestionStore.isIngestionPaused">
          모델 생성이 일시정지되었습니다. Explorer에서 노드를 Ctrl/Cmd+클릭하거나 드래그하여 추가한 후 수정 요청을 입력하세요.
        </template>
        <template v-else>
          캔버스에서 객체를 선택하세요 (Ctrl/Cmd+Click으로 다중 선택)
        </template>
      </div>

      <div class="chat-input__wrapper">
        <textarea
          v-model="inputText"
          class="chat-input__textarea"
          :placeholder="ingestionStore.isIngestionPaused 
            ? (selectedChips.length > 0 ? '수정 요청을 입력하세요...' : 'Explorer에서 노드를 선택하거나 캔버스에서 객체를 선택하세요')
            : selectedChips.length > 0 
              ? '수정 요청을 입력하세요...' 
              : '캔버스에서 객체를 선택하고 수정 요청을 입력하세요'"
          :disabled="chatStore.isProcessing || (selectedChips.length === 0)"
          @keydown="handleKeyDown"
          @compositionstart="handleCompositionStart"
          @compositionend="handleCompositionEnd"
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

  <ImpactDetailsModal
    :visible="isImpactModalOpen"
    :seed-nodes="impactModalSeedNodes"
    :impact-summary="impactModalSummary"
    @close="closeImpactDetails"
  />
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
  padding-left: calc(var(--spacing-md) + 20px);
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

.chat-panel__header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.chat-panel__clear-btn,
.chat-panel__close-btn {
  background: none;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-panel__clear-btn:hover,
.chat-panel__close-btn:hover {
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
  word-wrap: break-word;
  overflow-wrap: break-word;
  white-space: pre-wrap;
}

.chat-react-trace {
  margin-bottom: var(--spacing-sm);
  padding: var(--spacing-xs);
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
}

.chat-impact-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
  margin: var(--spacing-xs) 0 var(--spacing-sm);
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: rgba(34, 139, 230, 0.08);
  border: 1px solid rgba(34, 139, 230, 0.18);
}

.chat-impact-summary__text {
  font-size: 0.75rem;
  color: var(--color-text);
}

.chat-impact-summary__btn {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--color-text);
  font-size: 0.75rem;
  padding: 4px 8px;
  border-radius: 8px;
  cursor: pointer;
}

.chat-impact-summary__btn:hover {
  border-color: rgba(34, 139, 230, 0.35);
  background: rgba(34, 139, 230, 0.12);
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
  color: var(--color-text);
  word-wrap: break-word;
  overflow-wrap: break-word;
  white-space: pre-wrap;
}

/* ReAct step colors - adjusted for both dark and light themes */
.chat-react-step--thought .chat-react-step__content { 
  color: #8b5cf6; /* Darker purple for better contrast */
}

.chat-react-step--action .chat-react-step__content { 
  color: #059669; /* Darker green for better contrast */
}

.chat-react-step--observation .chat-react-step__content { 
  color: #0284c7; /* Darker blue for better contrast */
}

/* Light theme adjustments */
:root.theme-light .chat-react-step--thought .chat-react-step__content { 
  color: #7c3aed; /* Even darker purple for light mode */
}

:root.theme-light .chat-react-step--action .chat-react-step__content { 
  color: #047857; /* Even darker green for light mode */
}

:root.theme-light .chat-react-step--observation .chat-react-step__content { 
  color: #0369a1; /* Even darker blue for light mode */
}

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

.chat-drafts {
  margin: var(--spacing-sm) 0;
  padding: var(--spacing-sm);
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-sm);
}

.chat-drafts__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.chat-drafts__bulk {
  display: flex;
  gap: 6px;
}

.chat-drafts__btn {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--color-text);
  font-size: 0.7rem;
  padding: 4px 8px;
  border-radius: 6px;
  cursor: pointer;
}

.chat-drafts__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-draft-item {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 8px;
}

.chat-draft-item__check {
  padding-top: 2px;
}

.chat-draft-item__body {
  flex: 1;
  min-width: 0;
}

.chat-draft-item__top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.chat-draft-item__target {
  font-size: 0.8rem;
  color: var(--color-text);
  min-width: 0;
}

.chat-draft-item__meta {
  font-size: 0.7rem;
  color: var(--color-text-light);
  margin-left: 6px;
}

.chat-draft-item__fields,
.chat-draft-item__rationale {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-bottom: 4px;
}

.chat-draft-item__label {
  font-weight: 600;
  color: var(--color-text-light);
  margin-right: 6px;
}

.chat-draft-item__diff {
  margin-top: 8px;
}

.chat-draft-item__diff-row {
  margin-top: 8px;
}

.chat-draft-item__diff-field {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 4px;
}

.chat-draft-item__diff-values {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.chat-draft-item__diff-title {
  font-size: 0.65rem;
  color: var(--color-text-light);
  margin-bottom: 4px;
}

.chat-draft-item__diff-pre {
  margin: 0;
  padding: 8px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.06);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.7rem;
  color: var(--color-text);
  max-height: 140px;
  overflow: auto;
}

.chat-drafts__footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.chat-drafts__apply {
  background: var(--color-accent);
  border: none;
  color: white;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 0.75rem;
  cursor: pointer;
}

.chat-drafts__apply:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

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

.chat-panel__input-area {
  position: relative;
  transition: all 0.2s ease;
}

.chat-panel__input-area.drag-over {
  background: rgba(59, 130, 246, 0.05);
}

.chat-panel__input-area.drag-over::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 2px dashed var(--color-accent);
  border-radius: var(--radius-md);
  pointer-events: none;
}

.chat-panel__input-area.drag-over .chat-input__hint {
  color: var(--color-accent);
  font-weight: 600;
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


