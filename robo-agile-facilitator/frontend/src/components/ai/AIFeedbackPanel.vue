<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useSessionStore } from '../../stores/session'
import { useVideoStore } from '../../stores/video'

const sessionStore = useSessionStore()
const videoStore = useVideoStore()

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// State
const peerConnection = ref<RTCPeerConnection | null>(null)
const dataChannel = ref<RTCDataChannel | null>(null)
const localStream = ref<MediaStream | null>(null)

const isConnected = ref(false)
const isListening = ref(false)
const isSpeaking = ref(false)
const isConnecting = ref(false)
const error = ref<string | null>(null)

interface TranscriptItem {
  role: 'user' | 'assistant'
  text: string
}

const transcript = ref<TranscriptItem[]>([])
const currentTranscript = ref('')
const textInput = ref('')

// ICE servers
const iceServers: RTCIceServer[] = [
  { urls: 'stun:stun.l.google.com:19302' }
]

/**
 * Connect to OpenAI Realtime API
 */
async function connectAI() {
  if (!sessionStore.session?.id) {
    error.value = '세션이 없습니다'
    return
  }
  
  isConnecting.value = true
  error.value = null
  
  try {
    // 1. Get ephemeral token from backend
    const tokenResponse = await fetch(`${API_BASE}/api/realtime/ephemeral-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionStore.session.id })
    })
    
    if (!tokenResponse.ok) {
      throw new Error('토큰 발급 실패')
    }
    
    const { client_secret } = await tokenResponse.json()
    
    if (!client_secret) {
      throw new Error('토큰이 없습니다')
    }
    
    // 2. Create RTCPeerConnection
    const pc = new RTCPeerConnection({ iceServers })
    peerConnection.value = pc
    
    // 3. Set up audio element for AI voice
    const audioEl = document.createElement('audio')
    audioEl.autoplay = true
    document.body.appendChild(audioEl)
    
    // 4. Handle incoming audio - broadcast to all participants via WebRTC
    pc.ontrack = (event) => {
      console.log('Received audio track from OpenAI')
      const aiStream = event.streams[0]
      
      // Play locally
      audioEl.srcObject = aiStream
      isSpeaking.value = true
      
      // Register AI audio stream with videoStore to broadcast to all participants
      videoStore.setAIAudioStream(aiStream)
      console.log('AI audio stream registered for broadcasting')
    }
    
    // 5. Get microphone
    localStream.value = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true
      }
    })
    
    // 6. Add audio track
    localStream.value.getAudioTracks().forEach(track => {
      pc.addTrack(track, localStream.value!)
    })
    
    // 7. Create data channel
    const dc = pc.createDataChannel('oai-events')
    dataChannel.value = dc
    
    dc.onopen = () => {
      console.log('Data channel opened')
      isConnected.value = true
      
      // Send initial session config with energetic voice
      sendEvent({
        type: 'session.update',
        session: {
          instructions: getFacilitatorInstructions(),
          voice: 'shimmer', // 밝고 활기찬 톤
          input_audio_transcription: { model: 'whisper-1' },
          turn_detection: {
            type: 'server_vad',
            threshold: 0.5,
            prefix_padding_ms: 300,
            silence_duration_ms: 500
          }
        }
      })
    }
    
    dc.onclose = () => {
      isConnected.value = false
    }
    
    dc.onmessage = handleServerEvent
    
    // 8. Create offer
    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    
    // 9. Exchange SDP with OpenAI
    const sdpResponse = await fetch(
      'https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${client_secret}`,
          'Content-Type': 'application/sdp'
        },
        body: offer.sdp
      }
    )
    
    if (!sdpResponse.ok) {
      throw new Error(`SDP 교환 실패: ${sdpResponse.status}`)
    }
    
    const answerSdp = await sdpResponse.text()
    
    // 10. Set remote description
    await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp })
    
    isListening.value = true
    
  } catch (e) {
    console.error('AI connection failed:', e)
    error.value = e instanceof Error ? e.message : '연결 실패'
  } finally {
    isConnecting.value = false
  }
}

/**
 * Handle events from OpenAI
 */
function handleServerEvent(event: MessageEvent) {
  try {
    const data = JSON.parse(event.data)
    console.log('Realtime event:', data.type)
    
    switch (data.type) {
      case 'session.created':
      case 'session.updated':
        console.log('Session ready')
        break
        
      case 'input_audio_buffer.speech_started':
        isListening.value = true
        isSpeaking.value = false
        break
        
      case 'input_audio_buffer.speech_stopped':
        isListening.value = false
        break
        
      case 'conversation.item.input_audio_transcription.completed':
        if (data.transcript) {
          transcript.value.push({ role: 'user', text: data.transcript })
        }
        break
        
      case 'response.audio_transcript.delta':
        currentTranscript.value += data.delta || ''
        break
        
      case 'response.audio_transcript.done':
        if (currentTranscript.value) {
          // Parse and execute any canvas actions in the response
          parseAndExecuteActions(currentTranscript.value)
          
          // Clean transcript for display (remove JSON blocks)
          const cleanText = currentTranscript.value.replace(/```json[\s\S]*?```/g, '').trim()
          if (cleanText) {
            transcript.value.push({ role: 'assistant', text: cleanText })
          }
          currentTranscript.value = ''
        }
        isSpeaking.value = false
        break
        
      case 'response.audio.delta':
        isSpeaking.value = true
        break
        
      case 'response.audio.done':
      case 'response.done':
        isSpeaking.value = false
        break
        
      case 'error':
        console.error('API error:', data.error)
        error.value = data.error?.message || '오류 발생'
        break
    }
  } catch (e) {
    console.error('Failed to parse event:', e)
  }
}

/**
 * Parse AI response for canvas actions and execute them
 */
function parseAndExecuteActions(responseText: string) {
  try {
    // Find JSON block in response
    const jsonMatch = responseText.match(/```json\s*([\s\S]*?)\s*```/)
    if (!jsonMatch) return
    
    const jsonStr = jsonMatch[1]
    const actionData = JSON.parse(jsonStr)
    
    if (!actionData.actions || !Array.isArray(actionData.actions)) return
    
    console.log('AI Canvas Actions:', actionData.actions)
    
    // Calculate positions for new stickers (spread them out)
    let xOffset = 100
    let yOffset = 100
    const existingStickers = sessionStore.stickers.length
    
    for (const action of actionData.actions) {
      switch (action.type) {
        case 'add_sticker':
          // Add a new sticker to canvas
          const stickerType = action.sticker_type || 'event'
          const text = action.text
          
          if (text) {
            // Calculate position (grid layout for multiple stickers)
            const position = {
              x: xOffset + (existingStickers % 4) * 220,
              y: yOffset + Math.floor(existingStickers / 4) * 120 + (actionData.actions.indexOf(action) * 100)
            }
            
            sessionStore.addSticker(stickerType, text, position)
            console.log(`AI added ${stickerType} sticker: "${text}"`)
            xOffset += 30 // Slight offset for visual separation
          }
          break
          
        case 'update_sticker':
          // Update existing sticker
          if (action.sticker_id && action.text) {
            sessionStore.updateSticker(action.sticker_id, { text: action.text })
            console.log(`AI updated sticker ${action.sticker_id}: "${action.text}"`)
          }
          break
          
        case 'delete_sticker':
          // Delete sticker
          if (action.sticker_id) {
            sessionStore.deleteSticker(action.sticker_id)
            console.log(`AI deleted sticker ${action.sticker_id}`)
          }
          break
          
        default:
          console.log('Unknown action type:', action.type)
      }
    }
    
    // Show notification that AI added stickers
    if (actionData.actions.length > 0) {
      const addCount = actionData.actions.filter((a: any) => a.type === 'add_sticker').length
      if (addCount > 0) {
        console.log(`AI added ${addCount} sticker(s) to the canvas`)
      }
    }
    
  } catch (e) {
    console.error('Failed to parse AI actions:', e)
  }
}

/**
 * Send event to OpenAI
 */
function sendEvent(event: Record<string, any>) {
  if (dataChannel.value?.readyState === 'open') {
    dataChannel.value.send(JSON.stringify(event))
  }
}

/**
 * Send text message
 */
function sendMessage() {
  if (!textInput.value.trim() || !isConnected.value) return
  
  sendEvent({
    type: 'conversation.item.create',
    item: {
      type: 'message',
      role: 'user',
      content: [{ type: 'input_text', text: textInput.value }]
    }
  })
  
  sendEvent({ type: 'response.create', response: { modalities: ['text', 'audio'] } })
  
  transcript.value.push({ role: 'user', text: textInput.value })
  textInput.value = ''
}

/**
 * Toggle microphone
 */
function toggleMute() {
  if (localStream.value) {
    const track = localStream.value.getAudioTracks()[0]
    if (track) {
      track.enabled = !track.enabled
      isListening.value = track.enabled
    }
  }
}

/**
 * Disconnect
 */
function disconnectAI() {
  dataChannel.value?.close()
  peerConnection.value?.close()
  localStream.value?.getTracks().forEach(t => t.stop())
  
  dataChannel.value = null
  peerConnection.value = null
  localStream.value = null
  isConnected.value = false
  isListening.value = false
  isSpeaking.value = false
  
  // Also disconnect from videoStore (stops broadcasting)
  videoStore.disconnectAI()
}

/**
 * Get facilitator instructions with dynamic tone
 */
function getFacilitatorInstructions(): string {
  const phase = sessionStore.session?.phase || 'orientation'
  
  const base = `당신은 이벤트 스토밍 워크숍의 AI 퍼실리테이터 "아리"입니다.

## 성격과 말투
- 밝고 에너지 넘치는 워크숍 진행자처럼 말하세요
- 참가자들을 격려하고 칭찬을 아끼지 마세요
- "좋아요!", "훌륭해요!", "바로 그거예요!" 같은 긍정적 표현을 자주 사용하세요
- 실수가 있어도 부드럽게 안내하되, 먼저 시도한 것을 칭찬하세요

## 톤 조절 가이드
- 새 스티커 추가: 신나고 격려하는 톤 🎉
- 규칙 위반 발견: 친절하지만 명확하게, 수정 방법 제시
- 진행이 느릴 때: 활기차게 독려
- 좋은 진행: 크게 칭찬하고 다음 단계 안내

## 이벤트 스토밍 규칙
- 이벤트(주황색): 과거형으로 작성 (예: "주문이 생성되었다")
- 커맨드(파란색): 이벤트를 트리거하는 명령 (예: "주문 생성")  
- 정책(보라색): "X가 발생하면 Y를 한다" 형식
- 읽기 모델(초록색): 의사결정에 필요한 데이터 뷰
- 외부 시스템(분홍색): 도메인 외부 시스템

## 대화 스타일
- 한국어로 대화
- 짧고 임팩트 있게 (2-3문장)
- 워크숍 진행자처럼 활기차게!

## 캔버스 액션 기능
참가자가 예시를 요청하거나, 스티커 추가/수정이 필요한 상황에서는 음성 답변과 함께 아래 JSON 형식으로 액션을 응답 끝에 추가하세요:

\`\`\`json
{"actions": [
  {"type": "add_sticker", "sticker_type": "event", "text": "사용자가 회원가입을 완료했다"},
  {"type": "add_sticker", "sticker_type": "event", "text": "상품이 장바구니에 담겼다"},
  {"type": "update_sticker", "sticker_id": "기존스티커ID", "text": "수정된 텍스트"}
]}
\`\`\`

- add_sticker: 새 스티커 추가 (sticker_type: event, command, policy, read_model, external_system)
- update_sticker: 기존 스티커 수정
- 예시 요청 시: 3-5개의 관련 예시 스티커를 추가해주세요
- 수정 제안 시: update_sticker로 올바른 형식 제안`

  const phaseGuide: Record<string, string> = {
    orientation: `

🎯 현재 단계: 오리엔테이션
- 밝고 환영하는 톤으로 이벤트 스토밍을 소개하세요
- 참가자들이 편안하게 느끼도록 분위기를 띄워주세요
- "자, 이제 신나는 이벤트 스토밍을 시작해볼까요?" 같은 표현 사용`,
    
    event_elicitation: `

🎯 현재 단계: 이벤트 도출
- 가장 활기찬 톤! 아이디어가 쏟아지도록 독려
- "어떤 일이 일어날까요?", "더 있을 것 같은데요!" 
- 모든 아이디어를 환영하고 칭찬하세요`,
    
    event_refinement: `

🎯 현재 단계: 이벤트 정제
- 꼼꼼하지만 긍정적인 톤
- 잘못된 형식은 부드럽게 교정
- "거의 완벽해요! 살짝만 바꿔볼까요?"`,
    
    command_policy: `

🎯 현재 단계: 커맨드/정책 추가
- 탐구하는 톤 "무엇이 이 이벤트를 일으켰을까요?"
- 연결고리를 찾으면 크게 칭찬
- 인과관계 발견의 재미를 강조`,
    
    timeline_ordering: `

🎯 현재 단계: 타임라인 정렬
- 차분하지만 명확한 톤
- "시간 순서를 맞춰볼까요?"
- 전체 흐름이 보이기 시작하면 칭찬`,
    
    summary: `

🎯 현재 단계: 요약
- 성취감을 주는 톤! "대단해요, 여러분!"
- 주요 발견사항을 함께 정리
- 워크숍 성과를 축하하세요 🎊`
  }
  
  return base + (phaseGuide[phase] || '')
}

/**
 * Generate feedback prompt based on sticker type - energetic and encouraging tone
 */
function getStickerFeedbackPrompt(sticker: { type: string; text: string; author: string }): string {
  const typeNames: Record<string, string> = {
    event: '이벤트',
    command: '커맨드',
    policy: '정책',
    read_model: '읽기 모델',
    external_system: '외부 시스템'
  }
  
  const typeName = typeNames[sticker.type] || sticker.type
  
  if (sticker.type === 'event') {
    return `🎉 ${sticker.author}님이 새 이벤트 스티커를 추가했어요: "${sticker.text}"

신나게 반응하세요! 먼저 참여를 칭찬하고, 이벤트가 과거형으로 잘 작성되었는지 확인해주세요.
- 잘 됐으면: "완벽해요! 바로 그거예요!" 같이 신나게 칭찬
- 수정 필요하면: "좋은 시도예요! 살짝만 바꿔볼까요? [수정안]" 처럼 부드럽게`
  } else if (sticker.type === 'command') {
    return `💙 ${sticker.author}님이 새 커맨드 스티커를 추가했어요: "${sticker.text}"

커맨드는 이벤트를 일으키는 행동이에요. 활기차게 피드백해주세요!
"오! 이 커맨드가 어떤 이벤트를 일으키나요?" 같이 호기심 어린 톤으로!`
  } else if (sticker.type === 'policy') {
    return `💜 ${sticker.author}님이 새 정책 스티커를 추가했어요: "${sticker.text}"

정책은 "X가 발생하면 Y를 한다" 형식이에요. 
인과관계를 발견했다면 크게 칭찬하고, 형식이 맞는지 확인해주세요!`
  } else if (sticker.type === 'read_model') {
    return `💚 ${sticker.author}님이 읽기 모델을 추가했어요: "${sticker.text}"

의사결정에 필요한 데이터를 잘 파악했네요! 어떤 결정을 내리는 데 도움이 되는지 물어보세요.`
  } else if (sticker.type === 'external_system') {
    return `🩷 ${sticker.author}님이 외부 시스템을 추가했어요: "${sticker.text}"

도메인 경계를 잘 파악했어요! 이 시스템과 어떻게 연동되는지 탐구해보세요.`
  } else {
    return `✨ ${sticker.author}님이 새 ${typeName} 스티커를 추가했어요: "${sticker.text}". 활기차게 피드백해주세요!`
  }
}

// Watch for sticker additions - provide voice feedback for ALL sticker types
watch(() => sessionStore.stickers.length, (newLen, oldLen) => {
  if (newLen > oldLen && isConnected.value) {
    const sticker = sessionStore.stickers[sessionStore.stickers.length - 1]
    if (sticker) {
      const prompt = getStickerFeedbackPrompt({
        type: sticker.type,
        text: sticker.text,
        author: sticker.author
      })
      
      sendEvent({
        type: 'conversation.item.create',
        item: {
          type: 'message',
          role: 'user',
          content: [{
            type: 'input_text',
            text: prompt
          }]
        }
      })
      
      // Request voice response
      sendEvent({ 
        type: 'response.create', 
        response: { 
          modalities: ['text', 'audio'],
          instructions: '짧고 명확하게 피드백하세요. 2-3문장 이내로.'
        } 
      })
    }
  }
})

// Watch for phase changes - trigger comprehensive review
watch(() => sessionStore.session?.phase, (newPhase, oldPhase) => {
  if (newPhase && isConnected.value) {
    // Update AI instructions for new phase
    sendEvent({
      type: 'session.update',
      session: { instructions: getFacilitatorInstructions() }
    })
    
    // If transitioning from a phase (not initial load), do comprehensive review
    if (oldPhase && oldPhase !== newPhase) {
      performPhaseTransitionReview(oldPhase, newPhase)
    }
  }
})

/**
 * Perform comprehensive review when transitioning between phases
 */
function performPhaseTransitionReview(fromPhase: string, toPhase: string) {
  const stickers = sessionStore.stickers
  
  // Build canvas summary
  const summary = buildCanvasSummary(stickers)
  
  const phaseNames: Record<string, string> = {
    orientation: '오리엔테이션',
    event_elicitation: '이벤트 도출',
    event_refinement: '이벤트 정제',
    command_policy: '커맨드/정책',
    timeline_ordering: '타임라인 정렬',
    summary: '요약'
  }
  
  const prompt = `🔄 단계 전환: "${phaseNames[fromPhase]}" → "${phaseNames[toPhase]}"

지금까지의 이벤트 스토밍 결과를 종합 평가하고 교정해주세요.

## 현재 캔버스 상태
${summary}

## 요청사항
1. **종합 평가**: 지금까지 진행된 내용을 칭찬하고 잘된 점 언급
2. **문제점 발견**: 규칙에 맞지 않는 스티커가 있다면 지적
3. **교정 실시**: 수정이 필요한 스티커는 JSON 액션으로 교정
4. **다음 단계 안내**: "${phaseNames[toPhase]}" 단계에서 할 일 소개

교정이 필요한 경우 아래 형식으로 액션을 포함하세요:
\`\`\`json
{"actions": [
  {"type": "update_sticker", "sticker_id": "스티커ID", "text": "교정된 텍스트"}
]}
\`\`\`

신나고 활기찬 톤으로 방송하세요! 🎉`

  sendEvent({
    type: 'conversation.item.create',
    item: {
      type: 'message',
      role: 'user',
      content: [{ type: 'input_text', text: prompt }]
    }
  })
  
  sendEvent({ 
    type: 'response.create', 
    response: { 
      modalities: ['text', 'audio'],
      instructions: '종합 평가를 하되, 너무 길지 않게 핵심만 전달하세요. 교정이 필요하면 JSON 액션을 포함하세요.'
    } 
  })
}

/**
 * Build a summary of current canvas state for AI review
 */
function buildCanvasSummary(stickers: typeof sessionStore.stickers): string {
  if (stickers.length === 0) {
    return '캔버스가 비어있습니다.'
  }
  
  const byType: Record<string, Array<{id: string, text: string, author: string}>> = {
    event: [],
    command: [],
    policy: [],
    read_model: [],
    external_system: []
  }
  
  stickers.forEach(s => {
    if (byType[s.type]) {
      byType[s.type].push({ id: s.id, text: s.text, author: s.author })
    }
  })
  
  const typeNames: Record<string, string> = {
    event: '이벤트 (주황색)',
    command: '커맨드 (파란색)',
    policy: '정책 (보라색)',
    read_model: '읽기 모델 (초록색)',
    external_system: '외부 시스템 (분홍색)'
  }
  
  let summary = `총 ${stickers.length}개 스티커\n\n`
  
  for (const [type, items] of Object.entries(byType)) {
    if (items.length > 0) {
      summary += `### ${typeNames[type]} (${items.length}개)\n`
      items.forEach((item, idx) => {
        summary += `${idx + 1}. [ID: ${item.id.slice(0, 8)}] "${item.text}" (by ${item.author})\n`
      })
      summary += '\n'
    }
  }
  
  return summary
}

/**
 * Handle time-based events from WorkshopTimer
 */
function handleTimeWarning(data: { type: string; minutesLeft: number; phase: string }) {
  if (!isConnected.value) return
  
  let prompt = ''
  
  switch (data.type) {
    case 'phase-5min':
      prompt = `⏰ 현재 단계(${getPhaseLabel(data.phase)})가 5분 남았습니다!
참가자들에게 활기차게 알려주세요. "5분 남았어요! 마무리 준비해볼까요?" 같은 톤으로.
아직 진행이 부족하다면 격려하고, 잘 진행되고 있다면 칭찬해주세요.`
      break
      
    case 'phase-1min':
      prompt = `⚡ 현재 단계(${getPhaseLabel(data.phase)})가 1분 남았습니다!
긴급하지만 긍정적인 톤으로 알려주세요. "1분 남았어요! 마지막 스퍼트!" 
다음 단계로 넘어갈 준비를 안내해주세요.`
      break
      
    case 'total-10min':
      prompt = `🔔 전체 워크숍이 10분 남았습니다!
참가자들에게 시간을 상기시키면서도 긍정적으로 마무리를 향해 가고 있다고 격려해주세요.
"10분 남았어요! 정리 단계로 넘어갈 준비해볼까요?"`
      break
      
    case 'total-5min':
      prompt = `🚨 전체 워크숍이 5분 남았습니다!
에너지를 높이면서 마무리를 안내하세요. 
"5분 남았어요! 오늘 발견한 것들을 정리해봐요!"`
      break
  }
  
  if (prompt) {
    sendEvent({
      type: 'conversation.item.create',
      item: {
        type: 'message',
        role: 'user',
        content: [{ type: 'input_text', text: prompt }]
      }
    })
    sendEvent({ 
      type: 'response.create', 
      response: { modalities: ['text', 'audio'] } 
    })
  }
}

function handlePhaseTimeUp(phase: string) {
  if (!isConnected.value) return
  
  const nextPhase = getNextPhase(phase)
  const prompt = nextPhase 
    ? `🎯 ${getPhaseLabel(phase)} 단계가 끝났습니다!
다음은 "${getPhaseLabel(nextPhase)}" 단계입니다.
신나게 전환을 안내하세요! "좋아요! 이제 ${getPhaseLabel(nextPhase)}로 넘어가볼까요?" 
다음 단계에서 무엇을 할지 간단히 소개해주세요.`
    : `🎊 마지막 단계가 끝났습니다! 워크숍이 곧 마무리됩니다.
참가자들의 노력을 칭찬하고, 오늘 발견한 것들을 축하해주세요!`

  sendEvent({
    type: 'conversation.item.create',
    item: {
      type: 'message',
      role: 'user',
      content: [{ type: 'input_text', text: prompt }]
    }
  })
  sendEvent({ 
    type: 'response.create', 
    response: { modalities: ['text', 'audio'] } 
  })
}

function handleWorkshopEnd() {
  if (!isConnected.value) return
  
  const stickerCount = sessionStore.stickers.length
  const prompt = `🎉 워크숍이 종료되었습니다!
총 ${stickerCount}개의 스티커가 만들어졌네요!
참가자들의 노고를 진심으로 축하하고, 오늘 함께해서 즐거웠다고 말해주세요.
"수고하셨어요! 정말 멋진 워크숍이었어요!" 같은 따뜻한 마무리로!`

  sendEvent({
    type: 'conversation.item.create',
    item: {
      type: 'message',
      role: 'user',
      content: [{ type: 'input_text', text: prompt }]
    }
  })
  sendEvent({ 
    type: 'response.create', 
    response: { modalities: ['text', 'audio'] } 
  })
}

function getPhaseLabel(phase: string): string {
  const labels: Record<string, string> = {
    orientation: '오리엔테이션',
    event_elicitation: '이벤트 도출',
    event_refinement: '이벤트 정제',
    command_policy: '커맨드/정책',
    timeline_ordering: '타임라인 정렬',
    summary: '요약'
  }
  return labels[phase] || phase
}

function getNextPhase(phase: string): string | null {
  const order = ['orientation', 'event_elicitation', 'event_refinement', 'command_policy', 'timeline_ordering', 'summary']
  const idx = order.indexOf(phase)
  return idx < order.length - 1 ? order[idx + 1] : null
}

// Expose methods for parent component
defineExpose({
  handleTimeWarning,
  handlePhaseTimeUp,
  handleWorkshopEnd,
  isConnected
})

// Cleanup
onUnmounted(() => {
  disconnectAI()
})

function dismissFeedback() {
  sessionStore.clearAIFeedback()
}

function applySuggestion() {
  if (sessionStore.aiFeedback?.sticker_id && sessionStore.aiFeedback?.suggestion) {
    sessionStore.updateSticker(sessionStore.aiFeedback.sticker_id, {
      text: sessionStore.aiFeedback.suggestion
    })
    sessionStore.clearAIFeedback()
  }
}
</script>

<template>
  <div class="ai-feedback-panel">
    <h3 class="panel-title">AI Facilitator</h3>

    <!-- Connection status -->
    <div class="connection-status">
      <template v-if="!isConnected">
        <button 
          class="connect-btn"
          :disabled="isConnecting"
          @click="connectAI"
        >
          <span v-if="isConnecting">🔄 연결 중...</span>
          <span v-else>🤖 AI 연결하기</span>
        </button>
        <p class="connect-hint">음성으로 AI와 대화하세요</p>
      </template>
      
      <template v-else>
        <div class="status-connected">
          <div class="status-indicator" :class="{ speaking: isSpeaking, listening: isListening }">
            <span class="status-icon">🤖</span>
          </div>
          <div class="status-info">
            <span class="status-label">
              {{ isSpeaking ? '말하는 중...' : isListening ? '듣는 중...' : '연결됨' }}
            </span>
          </div>
          <button class="mute-btn" @click="toggleMute" :title="isListening ? '음소거' : '음소거 해제'">
            {{ isListening ? '🎤' : '🔇' }}
          </button>
          <button class="disconnect-btn" @click="disconnectAI" title="연결 해제">
            ✕
          </button>
        </div>
      </template>
    </div>

    <!-- Error -->
    <div v-if="error" class="error-message">
      ⚠️ {{ error }}
    </div>

    <!-- Sticker feedback -->
    <div v-if="sessionStore.aiFeedback" class="feedback-card" :class="{ 'is-tip': sessionStore.aiFeedback.type === 'tip' }">
      <div class="feedback-header">
        <span class="feedback-icon">{{ sessionStore.aiFeedback.type === 'tip' ? '✅' : '💡' }}</span>
        <span class="feedback-type">{{ sessionStore.aiFeedback.type === 'tip' ? '팁' : '검증' }}</span>
      </div>
      <p class="feedback-message">{{ sessionStore.aiFeedback.message }}</p>
      <div v-if="sessionStore.aiFeedback.suggestion" class="suggestion-box">
        <span class="suggestion-label">제안:</span>
        <span class="suggestion-text">{{ sessionStore.aiFeedback.suggestion }}</span>
      </div>
      <div class="feedback-actions">
        <button v-if="sessionStore.aiFeedback.suggestion" class="action-btn apply" @click="applySuggestion">적용</button>
        <button class="action-btn dismiss" @click="dismissFeedback">닫기</button>
      </div>
    </div>

    <!-- Transcript -->
    <div v-if="transcript.length || currentTranscript" class="transcript-section">
      <h4>대화</h4>
      <div class="transcript-list">
        <div
          v-for="(item, idx) in transcript.slice(-8)"
          :key="idx"
          class="transcript-item"
          :class="{ 'ai-message': item.role === 'assistant' }"
        >
          <span class="transcript-role">{{ item.role === 'assistant' ? '🤖' : '👤' }}</span>
          <span class="transcript-text">{{ item.text }}</span>
        </div>
        <div v-if="currentTranscript" class="transcript-item ai-message current">
          <span class="transcript-role">🤖</span>
          <span class="transcript-text">{{ currentTranscript }}</span>
        </div>
      </div>
    </div>

    <!-- Text input -->
    <div v-if="isConnected" class="text-input-section">
      <input
        v-model="textInput"
        type="text"
        placeholder="메시지 입력..."
        @keyup.enter="sendMessage"
      />
      <button @click="sendMessage" :disabled="!textInput.trim()">전송</button>
    </div>

    <!-- Tips -->
    <div v-if="!isConnected && !sessionStore.aiFeedback" class="tips-section">
      <h4>이벤트 스토밍 팁</h4>
      <ul class="tips-list">
        <li><strong>Event</strong>는 과거형<br/><small>예: "주문이 생성되었다"</small></li>
        <li><strong>Command</strong>는 트리거<br/><small>예: "주문 생성"</small></li>
        <li><strong>Policy</strong>는 반응<br/><small>예: "결제 시 배송 시작"</small></li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.ai-feedback-panel {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-title {
  font-size: 12px;
  text-transform: uppercase;
  color: #888;
  margin: 0;
}

.connection-status { text-align: center; }

.connect-btn {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #4caf50, #45a049);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.connect-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(76, 175, 80, 0.4);
}

.connect-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.connect-hint { font-size: 11px; color: #888; margin-top: 8px; }

.status-connected {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: rgba(76, 175, 80, 0.15);
  border-radius: 8px;
  border: 1px solid rgba(76, 175, 80, 0.3);
}

.status-indicator {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(76, 175, 80, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  transition: all 0.3s;
}

.status-indicator.speaking {
  background: rgba(233, 69, 96, 0.3);
  animation: pulse 1s infinite;
}

.status-indicator.listening {
  background: rgba(33, 150, 243, 0.3);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.status-info { flex: 1; }
.status-label { color: #4caf50; font-size: 13px; font-weight: 500; }

.mute-btn, .disconnect-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  cursor: pointer;
  font-size: 14px;
}

.disconnect-btn { color: #f44336; }

.error-message {
  padding: 8px 12px;
  background: rgba(244, 67, 54, 0.2);
  border-radius: 6px;
  color: #f44336;
  font-size: 12px;
}

.feedback-card {
  background: rgba(233, 69, 96, 0.15);
  border: 1px solid rgba(233, 69, 96, 0.3);
  border-radius: 8px;
  padding: 12px;
}

.feedback-card.is-tip {
  background: rgba(76, 175, 80, 0.15);
  border-color: rgba(76, 175, 80, 0.3);
}

.feedback-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.feedback-icon { font-size: 18px; }
.feedback-type { font-size: 11px; text-transform: uppercase; color: #e94560; font-weight: 600; }
.feedback-card.is-tip .feedback-type { color: #4caf50; }
.feedback-message { color: #fff; font-size: 13px; line-height: 1.5; margin: 0 0 12px; }

.suggestion-box {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 12px;
}

.suggestion-label { font-size: 10px; color: #888; display: block; margin-bottom: 4px; }
.suggestion-text { color: #4caf50; font-weight: 500; }

.feedback-actions { display: flex; gap: 8px; }
.action-btn { flex: 1; padding: 8px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 500; }
.action-btn.apply { background: #4caf50; color: white; }
.action-btn.dismiss { background: rgba(255, 255, 255, 0.1); color: #aaa; }

.transcript-section { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.transcript-section h4 { font-size: 11px; color: #888; margin: 0 0 8px; }

.transcript-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.transcript-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  color: #ccc;
  padding: 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
}

.transcript-item.ai-message { background: rgba(76, 175, 80, 0.15); }
.transcript-item.current { border: 1px dashed rgba(76, 175, 80, 0.5); }
.transcript-role { font-size: 14px; }
.transcript-text { flex: 1; line-height: 1.4; }

.text-input-section { display: flex; gap: 8px; }

.text-input-section input {
  flex: 1;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
}

.text-input-section input:focus { outline: none; border-color: #4caf50; }

.text-input-section button {
  padding: 8px 16px;
  background: #4caf50;
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 13px;
  cursor: pointer;
}

.text-input-section button:disabled { opacity: 0.5; cursor: not-allowed; }

.tips-section h4 { font-size: 11px; color: #888; margin: 0 0 12px; }
.tips-list { list-style: none; padding: 0; margin: 0; }
.tips-list li { font-size: 12px; color: #ccc; padding: 8px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
.tips-list li:last-child { border-bottom: none; }
.tips-list strong { color: #ff9800; }
.tips-list small { color: #888; }
</style>
