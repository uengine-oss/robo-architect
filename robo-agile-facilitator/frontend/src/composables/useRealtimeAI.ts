/**
 * OpenAI Realtime API Composable
 * 
 * Based on: https://platform.openai.com/docs/guides/realtime-conversations
 * 
 * This composable handles the WebRTC connection to OpenAI's Realtime API
 * for voice-based AI facilitation during event storming sessions.
 */
import { ref, computed, onUnmounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Event types from OpenAI Realtime API
export interface RealtimeEvent {
  type: string
  [key: string]: any
}

export interface TranscriptItem {
  role: 'user' | 'assistant'
  text: string
  timestamp: Date
}

export interface AIFacilitatorState {
  isConnected: boolean
  isListening: boolean
  isSpeaking: boolean
  currentPhase: string
}

export function useRealtimeAI(sessionId: string) {
  // State
  const peerConnection = ref<RTCPeerConnection | null>(null)
  const dataChannel = ref<RTCDataChannel | null>(null)
  const localStream = ref<MediaStream | null>(null)
  const remoteAudioElement = ref<HTMLAudioElement | null>(null)
  
  const isConnected = ref(false)
  const isListening = ref(false)
  const isSpeaking = ref(false)
  const error = ref<string | null>(null)
  
  const transcript = ref<TranscriptItem[]>([])
  const currentTranscript = ref<string>('')
  
  // ICE servers for STUN/TURN
  const iceServers: RTCIceServer[] = [
    { urls: 'stun:stun.l.google.com:19302' }
  ]

  /**
   * Get ephemeral token from our backend
   */
  async function getEphemeralToken(): Promise<{ client_secret: string; session_id: string }> {
    const response = await fetch(`${API_BASE}/api/realtime/ephemeral-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId })
    })
    
    if (!response.ok) {
      throw new Error('Failed to get ephemeral token')
    }
    
    return response.json()
  }

  /**
   * Initialize the WebRTC connection to OpenAI Realtime API
   */
  async function connect() {
    try {
      error.value = null
      
      // 1. Get ephemeral token from our backend
      const { client_secret } = await getEphemeralToken()
      
      // 2. Create RTCPeerConnection
      const pc = new RTCPeerConnection({ iceServers })
      peerConnection.value = pc
      
      // 3. Set up audio element for AI voice output
      const audioEl = document.createElement('audio')
      audioEl.autoplay = true
      remoteAudioElement.value = audioEl
      
      // 4. Handle incoming audio track from OpenAI
      pc.ontrack = (event) => {
        console.log('Received remote track:', event.track.kind)
        audioEl.srcObject = event.streams[0]
        isSpeaking.value = true
      }
      
      // 5. Get user's microphone
      localStream.value = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      })
      
      // 6. Add audio track to peer connection
      localStream.value.getAudioTracks().forEach(track => {
        pc.addTrack(track, localStream.value!)
      })
      
      // 7. Create data channel for events
      const dc = pc.createDataChannel('oai-events')
      dataChannel.value = dc
      
      dc.onopen = () => {
        console.log('Data channel opened')
        isConnected.value = true
        
        // Update session with our facilitator instructions
        updateSession({
          instructions: getFacilitatorInstructions(),
          voice: 'alloy',
          input_audio_transcription: {
            model: 'whisper-1'
          },
          turn_detection: {
            type: 'server_vad',
            threshold: 0.5,
            prefix_padding_ms: 300,
            silence_duration_ms: 500
          }
        })
      }
      
      dc.onclose = () => {
        console.log('Data channel closed')
        isConnected.value = false
      }
      
      dc.onerror = (e) => {
        console.error('Data channel error:', e)
        error.value = 'Data channel error'
      }
      
      dc.onmessage = handleServerEvent
      
      // 8. Create and set local description (SDP offer)
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)
      
      // 9. Send offer to OpenAI and get answer
      const sdpResponse = await fetch('https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${client_secret}`,
          'Content-Type': 'application/sdp'
        },
        body: offer.sdp
      })
      
      if (!sdpResponse.ok) {
        throw new Error(`OpenAI SDP exchange failed: ${sdpResponse.status}`)
      }
      
      const answerSdp = await sdpResponse.text()
      
      // 10. Set remote description
      await pc.setRemoteDescription({
        type: 'answer',
        sdp: answerSdp
      })
      
      isListening.value = true
      
    } catch (e) {
      console.error('Failed to connect to Realtime API:', e)
      error.value = e instanceof Error ? e.message : 'Connection failed'
      throw e
    }
  }

  /**
   * Handle events from OpenAI Realtime API
   */
  function handleServerEvent(event: MessageEvent) {
    try {
      const data: RealtimeEvent = JSON.parse(event.data)
      console.log('Realtime event:', data.type, data)
      
      switch (data.type) {
        case 'session.created':
          console.log('Session created:', data.session?.id)
          break
          
        case 'session.updated':
          console.log('Session updated')
          break
          
        case 'input_audio_buffer.speech_started':
          isListening.value = true
          isSpeaking.value = false
          break
          
        case 'input_audio_buffer.speech_stopped':
          isListening.value = false
          break
          
        case 'conversation.item.input_audio_transcription.completed':
          // User's speech transcribed
          const userText = data.transcript
          if (userText) {
            transcript.value.push({
              role: 'user',
              text: userText,
              timestamp: new Date()
            })
          }
          break
          
        case 'response.audio_transcript.delta':
          // AI is speaking - accumulate transcript
          currentTranscript.value += data.delta || ''
          break
          
        case 'response.audio_transcript.done':
          // AI finished speaking
          if (currentTranscript.value) {
            transcript.value.push({
              role: 'assistant',
              text: currentTranscript.value,
              timestamp: new Date()
            })
            currentTranscript.value = ''
          }
          isSpeaking.value = false
          break
          
        case 'response.audio.delta':
          // Audio data coming - AI is speaking
          isSpeaking.value = true
          break
          
        case 'response.audio.done':
          isSpeaking.value = false
          break
          
        case 'response.done':
          isSpeaking.value = false
          break
          
        case 'error':
          console.error('Realtime API error:', data.error)
          error.value = data.error?.message || 'Unknown error'
          break
      }
    } catch (e) {
      console.error('Failed to parse server event:', e)
    }
  }

  /**
   * Send an event to OpenAI Realtime API
   */
  function sendEvent(event: RealtimeEvent) {
    if (dataChannel.value?.readyState === 'open') {
      dataChannel.value.send(JSON.stringify(event))
    } else {
      console.warn('Data channel not open, cannot send event')
    }
  }

  /**
   * Update session configuration
   */
  function updateSession(config: Record<string, any>) {
    sendEvent({
      type: 'session.update',
      session: config
    })
  }

  /**
   * Request AI to respond
   */
  function createResponse(instructions?: string) {
    const event: RealtimeEvent = {
      type: 'response.create',
      response: {
        modalities: ['text', 'audio']
      }
    }
    
    if (instructions) {
      event.response.instructions = instructions
    }
    
    sendEvent(event)
  }

  /**
   * Send a text message to the AI (for typed input)
   */
  function sendTextMessage(text: string) {
    // Add to conversation
    sendEvent({
      type: 'conversation.item.create',
      item: {
        type: 'message',
        role: 'user',
        content: [{
          type: 'input_text',
          text: text
        }]
      }
    })
    
    // Request response
    createResponse()
  }

  /**
   * Notify AI about a sticker change for validation
   */
  function notifyStickerAdded(sticker: { type: string; text: string; author: string }) {
    const message = `참가자 ${sticker.author}가 새로운 ${sticker.type} 스티커를 추가했습니다: "${sticker.text}". 이벤트 스토밍 규칙에 맞는지 확인하고 피드백을 주세요.`
    
    sendEvent({
      type: 'conversation.item.create',
      item: {
        type: 'message',
        role: 'user',
        content: [{
          type: 'input_text',
          text: message
        }]
      }
    })
    
    createResponse()
  }

  /**
   * Announce phase change to AI
   */
  function announcePhaseChange(phase: string) {
    const phaseMessages: Record<string, string> = {
      orientation: '오리엔테이션 단계를 시작합니다. 참가자들에게 이벤트 스토밍을 소개해주세요.',
      event_elicitation: '이벤트 도출 단계입니다. 참가자들이 도메인 이벤트를 자유롭게 추가하도록 안내해주세요.',
      event_refinement: '이벤트 정제 단계입니다. 추가된 이벤트들이 과거형인지, 규칙에 맞는지 검토해주세요.',
      command_policy: '커맨드와 정책 추가 단계입니다. 이벤트를 트리거하는 커맨드와 반응 정책을 추가하도록 안내해주세요.',
      timeline_ordering: '타임라인 정렬 단계입니다. 이벤트들을 시간 순서대로 배치하도록 안내해주세요.',
      summary: '요약 단계입니다. 오늘 발견한 주요 내용을 정리해주세요.'
    }
    
    const message = phaseMessages[phase] || `${phase} 단계로 이동합니다.`
    
    updateSession({
      instructions: getFacilitatorInstructions(phase)
    })
    
    sendEvent({
      type: 'conversation.item.create',
      item: {
        type: 'message',
        role: 'user',
        content: [{
          type: 'input_text',
          text: message
        }]
      }
    })
    
    createResponse()
  }

  /**
   * Get facilitator instructions based on current phase
   */
  function getFacilitatorInstructions(phase?: string): string {
    const baseInstructions = `당신은 이벤트 스토밍 워크숍의 AI 퍼실리테이터 "아리"입니다.

## 역할
- 참가자들이 이벤트 스토밍을 올바르게 수행하도록 안내
- 이벤트 규칙 위반 시 친절하게 교정
- 질문에 답변하고 개념 설명

## 이벤트 스토밍 규칙
1. **이벤트(주황색)**: 반드시 과거형으로 작성 (예: "주문이 생성되었다")
2. **커맨드(파란색)**: 이벤트를 트리거하는 행동 (예: "주문 생성")
3. **정책(보라색)**: "X가 발생하면 Y를 한다" 형식
4. **읽기 모델(초록색)**: 의사결정에 필요한 데이터 뷰
5. **외부 시스템(분홍색)**: 도메인 외부의 시스템

## 대화 스타일
- 한국어로 대화
- 친절하고 격려하는 톤
- 간결하게 핵심만 전달
- 잘못된 것은 즉시 교정하되 이유 설명`

    const phaseInstructions: Record<string, string> = {
      orientation: `\n\n## 현재 단계: 오리엔테이션\n오늘 다룰 도메인을 소개받고, 이벤트 스토밍 진행 방식을 설명하세요.`,
      event_elicitation: `\n\n## 현재 단계: 이벤트 도출\n참가자들이 도메인 이벤트를 자유롭게 추가하도록 독려하세요. 아직 커맨드나 정책은 추가하지 않습니다.`,
      event_refinement: `\n\n## 현재 단계: 이벤트 정제\n추가된 이벤트들을 검토하세요. 과거형이 아닌 것, 너무 모호한 것, 중복된 것을 지적하세요.`,
      command_policy: `\n\n## 현재 단계: 커맨드/정책 추가\n이제 커맨드와 정책을 추가합니다. 각 이벤트의 트리거와 후속 행동을 찾도록 안내하세요.`,
      timeline_ordering: `\n\n## 현재 단계: 타임라인 정렬\n이벤트를 시간 순서대로 정렬하도록 안내하세요. 누락된 이벤트가 있는지 확인하세요.`,
      summary: `\n\n## 현재 단계: 요약\n오늘 세션의 주요 발견사항을 정리하세요. 추가 논의가 필요한 부분을 언급하세요.`
    }

    return baseInstructions + (phaseInstructions[phase || 'orientation'] || '')
  }

  /**
   * Mute/unmute microphone
   */
  function toggleMute() {
    if (localStream.value) {
      const audioTrack = localStream.value.getAudioTracks()[0]
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled
        isListening.value = audioTrack.enabled
      }
    }
  }

  /**
   * Disconnect from Realtime API
   */
  function disconnect() {
    if (dataChannel.value) {
      dataChannel.value.close()
      dataChannel.value = null
    }
    
    if (peerConnection.value) {
      peerConnection.value.close()
      peerConnection.value = null
    }
    
    if (localStream.value) {
      localStream.value.getTracks().forEach(track => track.stop())
      localStream.value = null
    }
    
    if (remoteAudioElement.value) {
      remoteAudioElement.value.srcObject = null
      remoteAudioElement.value = null
    }
    
    isConnected.value = false
    isListening.value = false
    isSpeaking.value = false
  }

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })

  return {
    // State
    isConnected,
    isListening,
    isSpeaking,
    error,
    transcript,
    currentTranscript,
    
    // Actions
    connect,
    disconnect,
    toggleMute,
    sendTextMessage,
    notifyStickerAdded,
    announcePhaseChange,
    updateSession,
    createResponse
  }
}


