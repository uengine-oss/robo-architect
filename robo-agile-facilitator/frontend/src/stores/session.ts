/**
 * Session store - manages event storming session state
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { io, Socket } from 'socket.io-client'

export interface Position {
  x: number
  y: number
}

export interface Sticker {
  id: string
  type: 'event' | 'command' | 'policy' | 'read_model' | 'external_system'
  text: string
  position: Position
  author: string
  created_at: string
  updated_at: string
}

export interface Connection {
  id: string
  source_id: string
  target_id: string
  label?: string
}

export interface Participant {
  id: string
  name: string
}

export interface AIFeedback {
  type: 'validation' | 'suggestion' | 'education'
  sticker_id?: string
  message: string
  suggestion?: string
}

export type SessionPhase = 
  | 'orientation'
  | 'event_elicitation'
  | 'event_refinement'
  | 'command_policy'
  | 'timeline_ordering'
  | 'summary'

export interface Session {
  id: string
  title: string
  description?: string
  phase: SessionPhase
  duration_minutes: number
  created_at: string
  started_at?: string
  ended_at?: string
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const useSessionStore = defineStore('session', () => {
  // State
  const socket = ref<Socket | null>(null)
  const connected = ref(false)
  const session = ref<Session | null>(null)
  const stickers = ref<Sticker[]>([])
  const connections = ref<Connection[]>([])
  const participants = ref<Participant[]>([])
  const currentUser = ref<string>('')
  const aiFeedback = ref<AIFeedback | null>(null)
  const cursors = ref<Map<string, { x: number; y: number; name: string }>>(new Map())
  
  // Workshop timer state
  const workshopStartedAt = ref<Date | null>(null)
  const isWorkshopRunning = ref(false)
  const isPaused = ref(false)
  const syncedElapsedSeconds = ref(0)

  // Computed
  const eventCount = computed(() => stickers.value.filter(s => s.type === 'event').length)
  const commandCount = computed(() => stickers.value.filter(s => s.type === 'command').length)
  const isConnected = computed(() => connected.value)

  // Actions
  async function createSession(title: string, description?: string, duration?: number) {
    const response = await fetch(`${API_BASE}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        description,
        duration_minutes: duration || 60
      })
    })
    
    if (!response.ok) throw new Error('Failed to create session')
    
    const data = await response.json()
    session.value = data
    return data
  }

  async function loadSession(sessionId: string) {
    const response = await fetch(`${API_BASE}/api/sessions/${sessionId}`)
    
    if (!response.ok) throw new Error('Session not found')
    
    session.value = await response.json()
    return session.value
  }

  function connectSocket(sessionId: string, participantName: string) {
    if (socket.value?.connected) return

    currentUser.value = participantName
    
    socket.value = io(API_BASE, {
      transports: ['websocket'],
      autoConnect: true
    })

    socket.value.on('connect', () => {
      connected.value = true
      socket.value?.emit('join_session', {
        session_id: sessionId,
        participant_name: participantName
      })
    })

    socket.value.on('disconnect', () => {
      connected.value = false
    })

    // Session state sync
    socket.value.on('session_state', (data) => {
      session.value = data.session
      stickers.value = data.stickers
      connections.value = data.connections
      participants.value = data.participants
    })

    // Sticker events
    socket.value.on('sticker_added', (data) => {
      stickers.value.push(data.sticker)
      if (data.ai_feedback) {
        aiFeedback.value = data.ai_feedback
        // Auto-clear after 10 seconds
        setTimeout(() => { aiFeedback.value = null }, 10000)
      }
    })

    socket.value.on('sticker_updated', (data) => {
      const idx = stickers.value.findIndex(s => s.id === data.sticker.id)
      if (idx !== -1) stickers.value[idx] = data.sticker
    })

    socket.value.on('sticker_moved', (data) => {
      const sticker = stickers.value.find(s => s.id === data.sticker_id)
      if (sticker) {
        sticker.position = data.position
      }
    })

    socket.value.on('sticker_deleted', (data) => {
      stickers.value = stickers.value.filter(s => s.id !== data.sticker_id)
    })

    // Connection events
    socket.value.on('connection_added', (data) => {
      connections.value.push(data.connection)
    })

    socket.value.on('connection_deleted', (data) => {
      connections.value = connections.value.filter(c => c.id !== data.connection_id)
    })

    // Participant events
    socket.value.on('participant_joined', (data) => {
      // Check if participant already exists (avoid duplicates)
      const exists = participants.value.some(p => p.name === data.name)
      if (!exists) {
        participants.value.push({ id: data.sid, name: data.name })
      }
    })

    socket.value.on('participant_reconnected', (data) => {
      // Update existing participant's socket ID
      const participant = participants.value.find(p => p.name === data.name)
      if (participant) {
        participant.id = data.sid
      }
      console.log(`${data.name} reconnected`)
    })

    socket.value.on('participant_offline', (data) => {
      // Mark participant as offline but don't remove them
      const participant = participants.value.find(p => p.id === data.sid)
      if (participant) {
        console.log(`${participant.name} went offline`)
      }
      cursors.value.delete(data.sid)
    })

    socket.value.on('participant_left', (data) => {
      participants.value = participants.value.filter(p => p.id !== data.sid)
      cursors.value.delete(data.sid)
    })

    // Cursor sync
    socket.value.on('cursor_update', (data) => {
      cursors.value.set(data.sid, { x: data.x, y: data.y, name: data.name })
    })

    // Phase change
    socket.value.on('phase_changed', (data) => {
      if (session.value) {
        session.value.phase = data.phase
      }
    })

    // AI Facilitator events
    socket.value.on('ai_connected', (data) => {
      console.log('AI Facilitator connected:', data.message)
      // AI connection is handled by videoStore
    })

    socket.value.on('ai_disconnected', (data) => {
      console.log('AI Facilitator disconnected:', data.message)
      // AI disconnection is handled by videoStore
    })

    // Workshop timer events
    socket.value.on('workshop_started', (data) => {
      console.log('Workshop started:', data)
      workshopStartedAt.value = new Date(data.started_at)
      isWorkshopRunning.value = true
      isPaused.value = false
      if (session.value) {
        session.value.started_at = data.started_at
        session.value.phase = data.phase
      }
    })

    socket.value.on('timer_sync', (data) => {
      console.log('Timer sync:', data)
      if (data.started_at) {
        workshopStartedAt.value = new Date(data.started_at)
        isWorkshopRunning.value = true
      }
      if (session.value) {
        session.value.phase = data.phase
      }
    })

    socket.value.on('timer_paused', (data) => {
      isPaused.value = data.paused
      syncedElapsedSeconds.value = data.elapsed_seconds
      console.log('Timer paused:', data.paused, 'at', data.elapsed_seconds, 'seconds')
    })
  }

  function disconnectSocket() {
    if (socket.value) {
      socket.value.disconnect()
      socket.value = null
      connected.value = false
    }
  }

  // Canvas operations
  function addSticker(type: Sticker['type'], text: string, position: Position) {
    if (!socket.value || !session.value) return

    socket.value.emit('add_sticker', {
      session_id: session.value.id,
      type,
      text,
      position,
      author: currentUser.value
    })
  }

  function updateSticker(stickerId: string, updates: Partial<Pick<Sticker, 'text' | 'position'>>) {
    if (!socket.value || !session.value) return

    socket.value.emit('update_sticker', {
      session_id: session.value.id,
      sticker_id: stickerId,
      ...updates
    })
  }

  function moveSticker(stickerId: string, position: Position) {
    if (!socket.value || !session.value) return

    // Optimistic update
    const sticker = stickers.value.find(s => s.id === stickerId)
    if (sticker) sticker.position = position

    socket.value.emit('move_sticker', {
      session_id: session.value.id,
      sticker_id: stickerId,
      position
    })
  }

  function deleteSticker(stickerId: string) {
    if (!socket.value || !session.value) return

    socket.value.emit('delete_sticker', {
      session_id: session.value.id,
      sticker_id: stickerId
    })
  }

  function addConnection(sourceId: string, targetId: string, label?: string) {
    if (!socket.value || !session.value) return

    socket.value.emit('add_connection', {
      session_id: session.value.id,
      source_id: sourceId,
      target_id: targetId,
      label
    })
  }

  function deleteConnection(connectionId: string) {
    if (!socket.value || !session.value) return

    socket.value.emit('delete_connection', {
      session_id: session.value.id,
      connection_id: connectionId
    })
  }

  function updateCursor(x: number, y: number) {
    if (!socket.value || !session.value) return

    socket.value.emit('cursor_move', {
      session_id: session.value.id,
      x,
      y,
      name: currentUser.value
    })
  }

  function updatePhase(phase: SessionPhase) {
    if (!socket.value || !session.value) return

    socket.value.emit('update_phase', {
      session_id: session.value.id,
      phase
    })
  }

  function clearAIFeedback() {
    aiFeedback.value = null
  }

  // Workshop control functions
  function startWorkshop() {
    if (!socket.value || !session.value) return

    socket.value.emit('start_workshop', {
      session_id: session.value.id,
      host_name: currentUser.value
    })
  }

  function requestTimerSync() {
    if (!socket.value || !session.value) return

    socket.value.emit('sync_timer', {
      session_id: session.value.id
    })
  }

  function pauseTimer(paused: boolean, elapsedSeconds: number) {
    if (!socket.value || !session.value) return

    socket.value.emit('pause_timer', {
      session_id: session.value.id,
      paused,
      elapsed_seconds: elapsedSeconds
    })
  }

  return {
    // State
    session,
    stickers,
    connections,
    participants,
    currentUser,
    aiFeedback,
    cursors,
    connected,
    
    // Workshop timer state
    workshopStartedAt,
    isWorkshopRunning,
    isPaused,
    syncedElapsedSeconds,
    
    // Computed
    eventCount,
    commandCount,
    isConnected,
    
    // Actions
    createSession,
    loadSession,
    connectSocket,
    disconnectSocket,
    addSticker,
    updateSticker,
    moveSticker,
    deleteSticker,
    addConnection,
    deleteConnection,
    updateCursor,
    updatePhase,
    clearAIFeedback,
    
    // Workshop control
    startWorkshop,
    requestTimerSync,
    pauseTimer
  }
})

