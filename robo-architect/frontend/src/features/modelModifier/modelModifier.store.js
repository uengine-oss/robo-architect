import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useCanvasStore } from '@/features/canvas/canvas.store'

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

  // Computed
  const hasMessages = computed(() => messages.value.length > 0)
  const lastMessage = computed(() => messages.value[messages.value.length - 1])

  async function sendMessage(content) {
    if (!content.trim()) return

    // Get selected nodes context
    const selectedNodes = canvasStore.selectedNodes
    if (selectedNodes.length === 0) {
      messages.value.push({
        id: generateId(),
        type: 'system',
        content: '먼저 캔버스에서 수정할 객체를 선택해주세요.',
        timestamp: new Date().toISOString()
      })
      return
    }

    // Add user message
    const userMessage = {
      id: generateId(),
      type: 'user',
      content,
      selectedNodes: selectedNodes.map(n => ({
        id: n.id,
        name: n.data?.name || n.data?.label,
        type: n.data?.type || n.type
      })),
      timestamp: new Date().toISOString()
    }
    messages.value.push(userMessage)

    // Start processing
    isProcessing.value = true
    error.value = null
    reactTrace.value = []
    streamingContent.value = ''

    try {
      await processModificationRequest(content, selectedNodes)
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
    const nodeContext = selectedNodes.map(n => {
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
      changes: [],
      reactSteps: [],
      timestamp: new Date().toISOString()
    }
    messages.value.push(assistantMessage)

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
        }
      }
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

      case 'change':
        assistantMessage.changes.push(event.change)
        appliedChanges.value.push(event.change)
        break

      case 'content':
        assistantMessage.content += event.content
        streamingContent.value = assistantMessage.content
        break

      case 'complete':
        assistantMessage.content = event.summary || assistantMessage.content
        assistantMessage.isComplete = true
        if (assistantMessage.changes?.length) {
          canvasStore.syncAfterChanges(assistantMessage.changes)
        }
        break

      case 'error':
        error.value = event.message
        assistantMessage.content = `오류: ${event.message}`
        assistantMessage.isError = true
        break
    }

    updateLastAssistantMessage(assistantMessage)
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
    currentThought,
    currentAction,
    streamingContent,
    reactTrace,
    error,
    appliedChanges,

    hasMessages,
    lastMessage,

    sendMessage,
    clearMessages,
    retryLast,
    cancelProcessing
  }
})


