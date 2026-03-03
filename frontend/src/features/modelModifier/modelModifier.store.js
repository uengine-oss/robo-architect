import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useIngestionStore } from '@/features/requirementsIngestion/ingestion.store'

/**
 * Store for managing chat-based model modification with ReAct pattern.
 *
 * Users can:
 * 1) Select objects on the canvas
 * 2) Describe modifications in natural language
 * 3) Watch the agent reason and act (ReAct) to make changes
 * 4) Apply changes (streamed via SSE)
 */
export const useModelModifierStore = defineStore('modelModifier', () => {
  const canvasStore = useCanvasStore()
  const ingestionStore = useIngestionStore()

  // Message history
  const messages = ref([])

  // Current session state
  const isProcessing = ref(false)
  const currentThought = ref('')
  const currentAction = ref('')
  const streamingContent = ref('')

  // ReAct trace
  const reactTrace = ref([])

  // Error state
  const error = ref(null)

  // Applied changes history
  const appliedChanges = ref([])

  // Confirm/apply state
  const isConfirming = ref(false)

  // Selected nodes (for viewers other than Design)
  // Format: [{id, name, type, ...}]
  const selectedNodes = ref([])

  // Computed
  const hasMessages = computed(() => messages.value.length > 0)
  const lastMessage = computed(() => messages.value[messages.value.length - 1])
  
  // Get selected nodes from current viewer (Design uses canvasStore, others use selectedNodes)
  const currentSelectedNodes = computed(() => {
    // If using Design viewer, use canvasStore.selectedNodes
    // For other viewers, use selectedNodes ref
    // This will be determined by the active viewer context
    return selectedNodes.value.length > 0 ? selectedNodes.value : canvasStore.selectedNodes
  })

  function setSelectedNodes(nodes) {
    selectedNodes.value = Array.isArray(nodes) ? nodes : []
  }

  function clearSelection() {
    selectedNodes.value = []
  }

  async function sendMessage(content) {
    if (!content.trim()) return

    // Get selected nodes context (from current viewer)
    const nodes = currentSelectedNodes.value
    // Require node selection even during ingestion pause (to avoid context size issues)
    if (nodes.length === 0) {
      messages.value.push({
        id: generateId(),
        type: 'system',
        content: ingestionStore.isIngestionPaused
          ? '먼저 Explorer에서 노드를 선택하거나 캔버스에서 수정할 객체를 선택해주세요.'
          : '먼저 캔버스에서 수정할 객체를 선택해주세요.',
        timestamp: new Date().toISOString()
      })
      return
    }

    // Add user message
    const userMessage = {
      id: generateId(),
      type: 'user',
      content,
      selectedNodes: nodes.map(n => {
        // Handle both VueFlow node format (Design viewer) and plain object format (other viewers)
        const nodeData = n.data || n
        return {
          id: n.id || nodeData.id,
          name: nodeData?.name || nodeData?.label || n.name || n.id || nodeData.id,
          type: nodeData?.type || n.type || nodeData.type
        }
      }),
      timestamp: new Date().toISOString()
    }
    messages.value.push(userMessage)

    // Start processing
    isProcessing.value = true
    error.value = null
    reactTrace.value = []
    streamingContent.value = ''

    try {
      await processModificationRequest(content, nodes)
    } catch (e) {
      error.value = e.message
      messages.value.push({
        id: generateId(),
        type: 'system',
        content: `오류가 발생했습니다: ${e.message}`,
        timestamp: new Date().toISOString(),
        isError: true
      })
    } finally {
      isProcessing.value = false
      currentThought.value = ''
      currentAction.value = ''
    }
  }

  async function processModificationRequest(prompt, selectedNodes) {
    // Require node selection (even during ingestion pause, to avoid context size issues)
    const nodeContext = Array.isArray(selectedNodes) && selectedNodes.length > 0
      ? selectedNodes.map(n => {
          // bcId from parentNode (VueFlow grouping) or data.bcId
          const bcId = n.parentNode || n.data?.bcId
          return {
            id: n.id,
            name: n.data?.name || n.data?.label,
            type: n.data?.type || n.type,
            description: n.data?.description,
            bcId,
            bcName: n.data?.bcName,
            aggregateId: n.data?.aggregateId,
            ...n.data
          }
        })
      : []

    const response = await fetch('/api/chat/modify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        selectedNodes: nodeContext,
        conversationHistory: messages.value.slice(-10)
      })
    })

    if (!response.ok) {
      const maybe = await safeJson(response)
      throw new Error(maybe?.detail || `API error: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    let assistantMessage = {
      id: generateId(),
      type: 'assistant',
      content: '',
      changes: [], // legacy (applied immediately)
      drafts: [], // proposed changes requiring confirm
      reactSteps: [],
      timestamp: new Date().toISOString()
    }
    messages.value.push(assistantMessage)

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)
          if (data === '[DONE]') continue

          try {
            const event = JSON.parse(data)
            handleStreamEvent(event, assistantMessage)
          } catch (e) {
            // ignore non-json events
            console.warn('Failed to parse SSE event:', e, 'data:', data)
          }
        }
      }
    } catch (e) {
      // Handle stream reading errors
      assistantMessage.content = `❌ 스트림 읽기 오류: ${e.message || '알 수 없는 오류가 발생했습니다.'}`
      assistantMessage.isComplete = true
      assistantMessage.hasError = true
      error.value = e.message || '스트림 읽기 오류'
      console.error('SSE stream error:', e)
    }

    updateLastAssistantMessage(assistantMessage)
  }

  /**
   * Streaming 중 thought/action/observation 이벤트는 토큰 단위로 계속 들어올 수 있어
   * 매번 push 하면 UI에 줄이 끝없이 쌓인다.
   * 마지막 step이 같은 타입(그리고 action의 경우 같은 action)이면 content를 "갱신"한다.
   */
  function upsertReactStep(list, nextStep) {
    if (!Array.isArray(list) || list.length === 0) {
      list.push(nextStep)
      return
    }

    const last = list[list.length - 1]
    const sameType = last?.type === nextStep?.type
    const sameAction = nextStep?.type !== 'action' || last?.action === nextStep?.action

    if (sameType && sameAction) {
      // update-in-place (streaming friendly)
      last.content = nextStep.content
      if (nextStep.type === 'action') {
        last.action = nextStep.action
      }
      return
    }

    list.push(nextStep)
  }

  function handleStreamEvent(event, assistantMessage) {
    switch (event.type) {
      case 'impact_summary':
        assistantMessage.impactSummary = {
          seedIds: Array.isArray(event.seedIds) ? event.seedIds : [],
          confirmedCount:
            typeof event.confirmedCount === 'number'
              ? event.confirmedCount
              : Array.isArray(event.propagationConfirmed)
                ? event.propagationConfirmed.length
                : 0,
          propagationConfirmed: Array.isArray(event.propagationConfirmed) ? event.propagationConfirmed : [],
          userStoryIds: Array.isArray(event.userStoryIds) ? event.userStoryIds : [],
          propagationRounds: typeof event.propagationRounds === 'number' ? event.propagationRounds : 0,
          propagationStopReason: typeof event.propagationStopReason === 'string' ? event.propagationStopReason : '',
          k: typeof event.k === 'number' ? event.k : null,
          whitelist: Array.isArray(event.whitelist) ? event.whitelist : [],
          propagationDebug: event.propagationDebug || null
        }
        break

      case 'thought':
        currentThought.value = event.content
        upsertReactStep(reactTrace.value, { type: 'thought', content: event.content })
        upsertReactStep(assistantMessage.reactSteps, { type: 'thought', content: event.content })
        break

      case 'action':
        currentAction.value = event.content
        upsertReactStep(reactTrace.value, { type: 'action', content: event.content, action: event.action })
        upsertReactStep(assistantMessage.reactSteps, { type: 'action', content: event.content, action: event.action })
        break

      case 'observation':
        upsertReactStep(reactTrace.value, { type: 'observation', content: event.content })
        upsertReactStep(assistantMessage.reactSteps, { type: 'observation', content: event.content })
        break

      // Legacy: immediate-apply stream
      case 'change':
        assistantMessage.changes.push(event.change)
        appliedChanges.value.push(event.change)
        break

      // New: draft-only stream (requires confirm)
      case 'draft_change':
        if (!Array.isArray(assistantMessage.drafts)) assistantMessage.drafts = []
        assistantMessage.drafts.push({
          ...(event.draft || {}),
          approved: true
        })
        break

      case 'draft_complete':
        assistantMessage.content = event.summary || assistantMessage.content
        assistantMessage.isComplete = true
        // NOTE: no canvas sync here — drafts must be confirmed first.
        break

      case 'content':
        assistantMessage.content += event.content
        streamingContent.value = assistantMessage.content
        break

      // Legacy: immediate-apply completion
      case 'complete':
        assistantMessage.content = event.summary || assistantMessage.content
        assistantMessage.isComplete = true
        if (assistantMessage.changes?.length) {
          canvasStore.syncAfterChanges(assistantMessage.changes)
        }
        break

      case 'error':
        assistantMessage.content = `❌ 오류: ${event.message || '알 수 없는 오류가 발생했습니다.'}`
        assistantMessage.isComplete = true
        assistantMessage.hasError = true
        error.value = event.message || '알 수 없는 오류가 발생했습니다.'
        break

      case 'error':
        error.value = event.message
        assistantMessage.content = `오류: ${event.message}`
        assistantMessage.isError = true
        break
    }

    updateLastAssistantMessage(assistantMessage)
  }

  function setAllDraftApprovals(messageId, approved) {
    const idx = messages.value.findIndex(m => m.id === messageId)
    if (idx === -1) return
    const msg = messages.value[idx]
    if (!Array.isArray(msg.drafts)) return

    // Create new drafts array with updated approval status
    const updatedDrafts = msg.drafts.map(d => ({ ...d, approved: !!approved }))
    // Create new message object to ensure reactivity
    const updatedMessage = { ...msg, drafts: updatedDrafts }
    // Create new messages array to trigger reactivity
    const newMessages = [...messages.value]
    newMessages[idx] = updatedMessage
    messages.value = newMessages
  }

  function toggleDraftApproval(messageId, changeId, approved) {
    const idx = messages.value.findIndex(m => m.id === messageId)
    if (idx === -1) return
    const msg = messages.value[idx]
    if (!Array.isArray(msg.drafts)) return

    // Create new drafts array with updated approval status for the specific draft
    const updatedDrafts = msg.drafts.map(d => 
      d.changeId === changeId ? { ...d, approved: !!approved } : { ...d }
    )
    // Create new message object to ensure reactivity
    const updatedMessage = { ...msg, drafts: updatedDrafts }
    // Create new messages array to trigger reactivity
    const newMessages = [...messages.value]
    newMessages[idx] = updatedMessage
    messages.value = newMessages
  }

  async function confirmDrafts(messageId) {
    const idx = messages.value.findIndex(m => m.id === messageId)
    if (idx === -1) return
    const msg = messages.value[idx]
    const drafts = Array.isArray(msg.drafts) ? msg.drafts : []
    const approved = drafts.filter(d => d.approved)

    if (approved.length === 0) {
      messages.value.push({
        id: generateId(),
        type: 'system',
        content: '승인된 변경이 없습니다. (적용되지 않았습니다)',
        timestamp: new Date().toISOString()
      })
      return
    }

    isConfirming.value = true
    try {
      const payload = {
        drafts: drafts.map(d => {
          const { approved, ...rest } = d
          return rest
        }),
        approvedChangeIds: approved.map(d => d.changeId)
      }

      const response = await fetch('/api/chat/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      const data = await safeJson(response)
      if (!response.ok) {
        throw new Error(data?.detail || `API error: ${response.status}`)
      }
      if (!data?.success) {
        const reason = Array.isArray(data?.errors) && data.errors.length ? data.errors.join('\n') : '알 수 없는 오류'
        throw new Error(reason)
      }

      const applied = data?.appliedChanges || []
      if (applied.length) {
        canvasStore.syncAfterChanges(applied)
        applied.forEach(c => appliedChanges.value.push(c))
      }

      // mark message as applied + lock approvals
      const lockedDrafts = drafts.map(d => ({ ...d, approved: !!d.approved, isApplied: true }))
      messages.value[idx] = { ...msg, drafts: lockedDrafts, isApplied: true }
      messages.value = [...messages.value]

      messages.value.push({
        id: generateId(),
        type: 'system',
        content: `적용 완료: ${applied.length}개의 변경사항이 반영되었습니다.`,
        timestamp: new Date().toISOString()
      })
    } catch (e) {
      // Handle errors during confirmation
      const errorMessage = e.message || '알 수 없는 오류가 발생했습니다.'
      messages.value.push({
        id: generateId(),
        type: 'system',
        content: `❌ 적용 실패: ${errorMessage}`,
        timestamp: new Date().toISOString(),
        isError: true
      })
      error.value = errorMessage
      console.error('Failed to confirm drafts:', e)
    } finally {
      isConfirming.value = false
    }
  }

  function updateLastAssistantMessage(message) {
    const idx = messages.value.findIndex(m => m.id === message.id)
    if (idx !== -1) {
      messages.value[idx] = { ...message }
      messages.value = [...messages.value]
    }
  }

  function clearMessages() {
    messages.value = []
    reactTrace.value = []
    appliedChanges.value = []
    error.value = null
  }

  function generateId() {
    return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  async function retryLast() {
    const lastUserMessage = [...messages.value].reverse().find(m => m.type === 'user')
    if (lastUserMessage) {
      const errorIdx = messages.value.findIndex(m => m.isError)
      if (errorIdx !== -1) {
        messages.value.splice(errorIdx, 1)
      }
      if (lastUserMessage.selectedNodes) {
        canvasStore.selectNodes(lastUserMessage.selectedNodes.map(n => n.id))
      }
      await processModificationRequest(lastUserMessage.content, canvasStore.selectedNodes)
    }
  }

  function cancelProcessing() {
    isProcessing.value = false
    currentThought.value = ''
    currentAction.value = ''
  }

  async function safeJson(response) {
    try {
      return await response.json()
    } catch {
      return null
    }
  }

    return {
    messages,
    isProcessing,
    isConfirming,
    currentThought,
    currentAction,
    streamingContent,
    reactTrace,
    error,
    appliedChanges,
    selectedNodes,
    currentSelectedNodes,

    hasMessages,
    lastMessage,

    setSelectedNodes,
    clearSelection,
    sendMessage,
    clearMessages,
    retryLast,
    cancelProcessing,

    setAllDraftApprovals,
    toggleDraftApproval,
    confirmDrafts
  }
})


