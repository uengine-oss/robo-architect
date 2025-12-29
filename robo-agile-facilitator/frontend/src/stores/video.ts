/**
 * Video store - manages WebRTC video conferencing and OpenAI Realtime
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { io, Socket } from 'socket.io-client'

export interface Peer {
  id: string
  name: string
  connection?: RTCPeerConnection
  stream?: MediaStream
  audioMuted: boolean
  videoMuted: boolean
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ICE Server configuration
const ICE_SERVERS: RTCIceServer[] = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' }
]

export const useVideoStore = defineStore('video', () => {
  // State
  const socket = ref<Socket | null>(null)
  const localStream = ref<MediaStream | null>(null)
  const screenStream = ref<MediaStream | null>(null)
  const peers = ref<Map<string, Peer>>(new Map())
  const audioMuted = ref(false)
  const videoMuted = ref(false)
  const isScreenSharing = ref(false)
  const sessionId = ref<string>('')
  const participantName = ref<string>('')

  // OpenAI Realtime - AI as a virtual participant
  const aiConnection = ref<RTCPeerConnection | null>(null)
  const aiConnected = ref(false)
  const aiTranscript = ref<string[]>([])
  const aiAudioStream = ref<MediaStream | null>(null)  // AI audio stream to broadcast
  const isAIHost = ref(false)  // Whether this client hosts the AI

  // Computed
  const peerList = computed(() => Array.from(peers.value.values()))
  const hasLocalStream = computed(() => localStream.value !== null)

  // Initialize local media
  async function initLocalMedia(video = true, audio = true) {
    try {
      localStream.value = await navigator.mediaDevices.getUserMedia({
        video: video ? { width: 1280, height: 720 } : false,
        audio: audio ? {
          echoCancellation: true,
          noiseSuppression: true
        } : false
      })
      return localStream.value
    } catch (error) {
      console.error('Failed to get local media:', error)
      throw error
    }
  }

  // Start screen sharing
  async function startScreenShare() {
    try {
      screenStream.value = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true
      })
      isScreenSharing.value = true

      // Replace video track in all peer connections
      const videoTrack = screenStream.value.getVideoTracks()[0]
      peers.value.forEach(peer => {
        if (peer.connection) {
          const sender = peer.connection.getSenders().find(s => s.track?.kind === 'video')
          if (sender) sender.replaceTrack(videoTrack)
        }
      })

      // Handle screen share end
      videoTrack.onended = () => stopScreenShare()

      socket.value?.emit('screen_share_start', { session_id: sessionId.value })

      return screenStream.value
    } catch (error) {
      console.error('Failed to start screen share:', error)
      throw error
    }
  }

  // Stop screen sharing
  async function stopScreenShare() {
    if (!screenStream.value) return

    screenStream.value.getTracks().forEach(track => track.stop())
    screenStream.value = null
    isScreenSharing.value = false

    // Restore camera track
    if (localStream.value) {
      const videoTrack = localStream.value.getVideoTracks()[0]
      peers.value.forEach(peer => {
        if (peer.connection) {
          const sender = peer.connection.getSenders().find(s => s.track?.kind === 'video')
          if (sender && videoTrack) sender.replaceTrack(videoTrack)
        }
      })
    }

    socket.value?.emit('screen_share_stop', { session_id: sessionId.value })
  }

  // Toggle audio
  function toggleAudio() {
    if (localStream.value) {
      const audioTrack = localStream.value.getAudioTracks()[0]
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled
        audioMuted.value = !audioTrack.enabled

        socket.value?.emit('video_mute', {
          session_id: sessionId.value,
          audio_muted: audioMuted.value,
          video_muted: videoMuted.value
        })
      }
    }
  }

  // Toggle video
  function toggleVideo() {
    if (localStream.value) {
      const videoTrack = localStream.value.getVideoTracks()[0]
      if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled
        videoMuted.value = !videoTrack.enabled

        socket.value?.emit('video_mute', {
          session_id: sessionId.value,
          audio_muted: audioMuted.value,
          video_muted: videoMuted.value
        })
      }
    }
  }

  // Connect to video room
  function connectVideo(sid: string, name: string, existingSocket?: Socket) {
    sessionId.value = sid
    participantName.value = name

    // Use existing socket or create new one
    socket.value = existingSocket || io(API_BASE, { transports: ['websocket'] })

    socket.value.on('video_peers', async (data) => {
      // Connect to all existing peers
      for (const peerId of data.peers) {
        await createPeerConnection(peerId, true)
      }
    })

    socket.value.on('video_peer_joined', async (data) => {
      // New peer joined, wait for their offer
      peers.value.set(data.peer_id, {
        id: data.peer_id,
        name: data.name,
        audioMuted: false,
        videoMuted: false
      })
    })

    socket.value.on('video_peer_left', (data) => {
      const peer = peers.value.get(data.peer_id)
      if (peer?.connection) {
        peer.connection.close()
      }
      peers.value.delete(data.peer_id)
    })

    socket.value.on('video_offer', async (data) => {
      await handleOffer(data.from_id, data.sdp)
    })

    socket.value.on('video_answer', async (data) => {
      await handleAnswer(data.from_id, data.sdp)
    })

    socket.value.on('video_ice_candidate', async (data) => {
      await handleIceCandidate(data.from_id, data.candidate)
    })

    socket.value.on('video_mute_status', (data) => {
      const peer = peers.value.get(data.peer_id)
      if (peer) {
        peer.audioMuted = data.audio_muted
        peer.videoMuted = data.video_muted
      }
    })

    // Join video room
    socket.value.emit('video_join', {
      session_id: sid,
      participant_name: name
    })
  }

  // Create peer connection
  async function createPeerConnection(peerId: string, createOffer: boolean) {
    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS })

    // Add local tracks
    if (localStream.value) {
      localStream.value.getTracks().forEach(track => {
        pc.addTrack(track, localStream.value!)
      })
    }

    // Handle incoming tracks
    pc.ontrack = (event) => {
      const peer = peers.value.get(peerId)
      if (peer) {
        peer.stream = event.streams[0]
        peers.value.set(peerId, { ...peer })
      }
    }

    // ICE candidate handling
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        socket.value?.emit('video_ice_candidate', {
          target_id: peerId,
          candidate: event.candidate
        })
      }
    }

    // Store connection
    const existing = peers.value.get(peerId)
    peers.value.set(peerId, {
      ...existing,
      id: peerId,
      name: existing?.name || 'Unknown',
      connection: pc,
      audioMuted: existing?.audioMuted || false,
      videoMuted: existing?.videoMuted || false
    })

    // Create offer if we're the initiator
    if (createOffer) {
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      socket.value?.emit('video_offer', {
        target_id: peerId,
        sdp: pc.localDescription
      })
    }

    return pc
  }

  // Handle incoming offer
  async function handleOffer(fromId: string, sdp: RTCSessionDescriptionInit) {
    const pc = await createPeerConnection(fromId, false)
    await pc.setRemoteDescription(new RTCSessionDescription(sdp))

    const answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    socket.value?.emit('video_answer', {
      target_id: fromId,
      sdp: pc.localDescription
    })
  }

  // Handle incoming answer
  async function handleAnswer(fromId: string, sdp: RTCSessionDescriptionInit) {
    const peer = peers.value.get(fromId)
    if (peer?.connection) {
      await peer.connection.setRemoteDescription(new RTCSessionDescription(sdp))
    }
  }

  // Handle ICE candidate
  async function handleIceCandidate(fromId: string, candidate: RTCIceCandidateInit) {
    const peer = peers.value.get(fromId)
    if (peer?.connection) {
      await peer.connection.addIceCandidate(new RTCIceCandidate(candidate))
    }
  }

  // Connect to OpenAI Realtime API via WebRTC
  async function connectAIRealtime() {
    if (!localStream.value) {
      throw new Error('Local media not initialized')
    }

    try {
      // Get ephemeral key from our backend
      const response = await fetch(`${API_BASE}/api/realtime/ephemeral-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId.value })
      })

      if (!response.ok) {
        throw new Error('Failed to get ephemeral key')
      }

      const { client_secret } = await response.json()

      // Create RTCPeerConnection for OpenAI
      const pc = new RTCPeerConnection()
      aiConnection.value = pc

      // Add audio track (OpenAI only needs audio)
      const audioTrack = localStream.value.getAudioTracks()[0]
      if (audioTrack) {
        pc.addTrack(audioTrack)
      }

      // Handle AI audio response
      pc.ontrack = (event) => {
        // Create audio element for AI voice
        const audio = new Audio()
        audio.srcObject = event.streams[0]
        audio.play()
      }

      // Create data channel for events
      const dc = pc.createDataChannel('oai-events')
      
      dc.onmessage = (event) => {
        const data = JSON.parse(event.data)
        
        // Handle different event types
        if (data.type === 'conversation.item.input_audio_transcription.completed') {
          aiTranscript.value.push(`You: ${data.transcript}`)
        } else if (data.type === 'response.audio_transcript.done') {
          aiTranscript.value.push(`AI: ${data.transcript}`)
        }
      }

      // Create and send offer
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      // Send offer to OpenAI via our backend
      const sdpResponse = await fetch(`${API_BASE}/api/realtime/session/${sessionId.value}`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/sdp',
          'Authorization': `Bearer ${client_secret}`
        },
        body: offer.sdp
      })

      if (!sdpResponse.ok) {
        throw new Error('Failed to establish AI connection')
      }

      const { sdp: answerSdp } = await sdpResponse.json()
      
      await pc.setRemoteDescription({
        type: 'answer',
        sdp: answerSdp
      })

      aiConnected.value = true

    } catch (error) {
      console.error('Failed to connect to AI Realtime:', error)
      throw error
    }
  }

  // Disconnect AI
  function disconnectAI() {
    if (aiConnection.value) {
      aiConnection.value.close()
      aiConnection.value = null
      aiConnected.value = false
      isAIHost.value = false
      aiAudioStream.value = null
      
      // Remove AI from peers
      peers.value.delete('ai-facilitator')
      
      // Notify others
      socket.value?.emit('ai_disconnected', { session_id: sessionId.value })
    }
  }

  /**
   * Set AI audio stream and broadcast to all peers
   * Called from AIFeedbackPanel when AI connects
   */
  function setAIAudioStream(stream: MediaStream) {
    aiAudioStream.value = stream
    isAIHost.value = true
    aiConnected.value = true
    
    // Add AI as a virtual participant
    peers.value.set('ai-facilitator', {
      id: 'ai-facilitator',
      name: '🤖 AI 퍼실리테이터',
      stream: stream,
      audioMuted: false,
      videoMuted: true
    })
    
    // Notify other participants that AI has joined
    socket.value?.emit('ai_connected', { 
      session_id: sessionId.value,
      host_id: socket.value?.id
    })
    
    // Broadcast AI audio to all existing peer connections
    broadcastAIAudio()
  }

  /**
   * Broadcast AI audio stream to all connected peers
   */
  function broadcastAIAudio() {
    if (!aiAudioStream.value) return
    
    const audioTrack = aiAudioStream.value.getAudioTracks()[0]
    if (!audioTrack) return
    
    // Add AI audio track to all peer connections
    peers.value.forEach((peer, peerId) => {
      if (peerId === 'ai-facilitator') return  // Skip AI itself
      if (!peer.connection) return
      
      // Check if AI track already exists
      const senders = peer.connection.getSenders()
      const hasAITrack = senders.some(s => s.track?.id === audioTrack.id)
      
      if (!hasAITrack) {
        try {
          peer.connection.addTrack(audioTrack, aiAudioStream.value!)
          console.log(`Added AI audio to peer: ${peerId}`)
        } catch (e) {
          console.error(`Failed to add AI audio to peer ${peerId}:`, e)
        }
      }
    })
  }

  /**
   * Handle AI audio from another participant (when they're the AI host)
   */
  function handleRemoteAIAudio(stream: MediaStream) {
    if (isAIHost.value) return  // We're hosting, ignore
    
    aiAudioStream.value = stream
    aiConnected.value = true
    
    // Add AI as a virtual participant
    peers.value.set('ai-facilitator', {
      id: 'ai-facilitator',
      name: '🤖 AI 퍼실리테이터',
      stream: stream,
      audioMuted: false,
      videoMuted: true
    })
  }

  // Cleanup
  function disconnect() {
    // Close all peer connections
    peers.value.forEach(peer => {
      if (peer.connection) {
        peer.connection.close()
      }
    })
    peers.value.clear()

    // Stop local streams
    localStream.value?.getTracks().forEach(track => track.stop())
    localStream.value = null

    screenStream.value?.getTracks().forEach(track => track.stop())
    screenStream.value = null

    // Disconnect AI
    disconnectAI()

    // Leave video room
    socket.value?.emit('video_leave', { session_id: sessionId.value })
  }

  return {
    // State
    localStream,
    screenStream,
    peers,
    audioMuted,
    videoMuted,
    isScreenSharing,
    aiConnected,
    aiTranscript,
    aiAudioStream,
    isAIHost,

    // Computed
    peerList,
    hasLocalStream,

    // Actions
    initLocalMedia,
    startScreenShare,
    stopScreenShare,
    toggleAudio,
    toggleVideo,
    connectVideo,
    connectAIRealtime,
    disconnectAI,
    disconnect,
    setAIAudioStream,
    broadcastAIAudio,
    handleRemoteAIAudio
  }
})

