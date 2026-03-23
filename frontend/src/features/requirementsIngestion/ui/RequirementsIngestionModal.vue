<script setup>
import { ref, computed, watch, onUnmounted, onMounted } from 'vue'
import { useNavigatorStore } from '@/features/navigator/navigator.store'
import { useIngestionStore } from '@/features/requirementsIngestion/ingestion.store'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'complete', 'session-restored'])

const navigatorStore = useNavigatorStore()
const ingestionStore = useIngestionStore()

// LocalStorage key for persisting session (page refresh recovery)
const SESSION_STORAGE_KEY = 'ingestion_active_session'

// State
const dragActive = ref(false)
const file = ref(null)
const textContent = ref('')
const inputMode = ref('file') // 'file', 'text', or 'jira'
const isUploading = ref(false)
const isProcessing = ref(false)
const sessionId = ref(null)
const progress = ref(0)
const currentPhase = ref('')
const currentMessage = ref('')
const createdItems = ref([])
const eventSource = ref(null)
const error = ref(null)
const summary = ref(null)
const isPanelMinimized = ref(false)
const isPaused = ref(false)
const isPausing = ref(false) // Track if pause request is in progress

// Draggable panel state
const panelPosition = ref({ x: null, y: null })
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })
const hasDragged = ref(false) // Track if actual dragging occurred

// Display language for node/property displayName (ko: 한글, en: English)
const displayLanguage = ref(localStorage.getItem('app_display_language') || 'ko')
watch(displayLanguage, (v) => { localStorage.setItem('app_display_language', v) })

// Source type is auto-detected from filename (*.report.md → legacy_report)

// Cache state
const isCacheEnabled = ref(false)
const isTogglingCache = ref(false)
const cacheFeedback = ref(null) // { kind: 'success' | 'error' | 'info', message: string }

// JIRA/Confluence state
const JIRA_CREDS_KEY = 'jira_confluence_creds'
const jiraEmail = ref('')
const jiraApiToken = ref('')
const jiraBaseUrl = ref('https://uengine-team.atlassian.net')
const isConnecting = ref(false)
const confluencePages = ref([])
const selectedPageId = ref(null)
const selectedPageContent = ref(null) // { title, content, content_length }
const isLoadingPageContent = ref(false)
const jiraError = ref(null)
const jiraConnected = ref(false)
const pageSearchQuery = ref('')

// Data clearing state
const showClearConfirm = ref(false)
const existingDataStats = ref(null)
const isLoadingStats = ref(false)
const isClearing = ref(false)

// Computed
const isOpen = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const canSubmit = computed(() => {
  if (inputMode.value === 'file') {
    return file.value !== null
  }
  if (inputMode.value === 'jira') {
    return selectedPageContent.value !== null
  }
  return textContent.value.trim().length > 10
})

const filteredPages = computed(() => {
  if (!pageSearchQuery.value.trim()) return confluencePages.value
  const q = pageSearchQuery.value.toLowerCase()
  return confluencePages.value.filter(p => p.title.toLowerCase().includes(q))
})

const phaseLabel = computed(() => {
  const labels = {
    'upload': '업로드 중',
    'parsing': '문서 파싱',
    'extracting_user_stories': 'User Story 추출',
    'identifying_bc': 'Bounded Context 식별',
    'extracting_aggregates': 'Aggregate 추출',
    'extracting_commands': 'Command 추출',
    'extracting_events': 'Event 추출',
    'extracting_readmodels': 'ReadModel 추출',
    'generating_properties': 'Property 생성',
    'generating_references': 'Reference 생성',
    'identifying_policies': 'Policy 식별',
    'generating_gwt': '테스트 케이스 생성',
    'generating_ui': 'UI 생성',
    'saving': '저장 중',
    'paused': '⏸️ 일시 정지됨',
    'complete': '완료',
    'error': '오류'
  }
  return labels[currentPhase.value] || currentPhase.value
})

// Show floating panel when processing, has summary, or has error/cancellation message
const showFloatingPanel = computed(() => {
  return isProcessing.value || summary.value !== null || (error.value !== null && sessionId.value !== null)
})

// Has existing data
const hasExistingData = computed(() => {
  return existingDataStats.value && existingDataStats.value.total > 0
})

// Watch for modal open to check existing data + cache status
watch(isOpen, async (newVal) => {
  if (newVal) {
    await Promise.all([checkExistingData(), checkCacheStatus()])
  }
})

// Sync ingestion state to store
watch([isProcessing, isPaused, currentPhase, sessionId], ([processing, paused, phase, sid]) => {
  ingestionStore.setProcessing(processing)
  ingestionStore.setPaused(paused)
  ingestionStore.setPhase(phase || '')
  ingestionStore.setSessionId(sid)
}, { immediate: true })

// Reset store on unmount
onUnmounted(() => {
  ingestionStore.reset()
})

// Methods
function handleDragOver(e) {
  e.preventDefault()
  dragActive.value = true
}

function handleDragLeave(e) {
  e.preventDefault()
  dragActive.value = false
}

function handleDrop(e) {
  e.preventDefault()
  dragActive.value = false
  
  const files = e.dataTransfer.files
  if (files.length > 0) {
    handleFile(files[0])
  }
}

function handleFileSelect(e) {
  const files = e.target.files
  if (files.length > 0) {
    handleFile(files[0])
  }
}

function handleFile(f) {
  const validTypes = ['text/plain', 'application/pdf', 'text/markdown']
  const validExtensions = ['.txt', '.pdf', '.md']
  
  const isValidType = validTypes.includes(f.type) || 
    validExtensions.some(ext => f.name.toLowerCase().endsWith(ext))
  
  if (!isValidType) {
    error.value = '지원하지 않는 파일 형식입니다. (txt, pdf, md 지원)'
    return
  }
  
  file.value = f
  error.value = null
}

function removeFile() {
  file.value = null
}

// Check for existing data in Neo4j
async function checkExistingData() {
  isLoadingStats.value = true
  try {
    const response = await fetch('/api/graph/stats')
    if (response.ok) {
      existingDataStats.value = await response.json()
    }
  } catch (e) {
    console.error('Failed to fetch stats:', e)
    existingDataStats.value = null
  } finally {
    isLoadingStats.value = false
  }
}

// Clear all existing data from Neo4j
async function clearExistingData() {
  isClearing.value = true
  try {
    const response = await fetch('/api/graph/clear', { method: 'DELETE' })
    if (response.ok) {
      existingDataStats.value = { total: 0, by_type: {} }
      navigatorStore.clearAll()
      return true
    }
    return false
  } catch (e) {
    error.value = '데이터 삭제 중 오류가 발생했습니다.'
    return false
  } finally {
    isClearing.value = false
  }
}

// Handle start button click
function handleStartClick() {
  if (hasExistingData.value) {
    showClearConfirm.value = true
  } else {
    startIngestion()
  }
}

// User chose to clear existing data and proceed
async function confirmClearAndStart() {
  showClearConfirm.value = false
  const cleared = await clearExistingData()
  if (cleared) {
    await startIngestion()
  }
}

// User chose to cancel
function cancelClear() {
  showClearConfirm.value = false
}

async function startIngestion() {
  error.value = null
  isUploading.value = true
  createdItems.value = []
  summary.value = null
  isPanelMinimized.value = false
  isPaused.value = false
  
  try {
    const formData = new FormData()

    if (inputMode.value === 'file' && file.value) {
      formData.append('file', file.value)
    } else if (inputMode.value === 'jira' && selectedPageContent.value) {
      const text = `# ${selectedPageContent.value.title}\n\n${selectedPageContent.value.content}`
      if (!text.trim()) {
        throw new Error('선택한 페이지의 내용이 비어있습니다.')
      }
      formData.append('text', text)
    } else {
      formData.append('text', textContent.value)
    }
    formData.append('display_language', displayLanguage.value === 'en' ? 'en' : 'ko')

    const uploadResponse = await fetch('/api/ingest/upload', {
      method: 'POST',
      body: formData
    })
    
    if (!uploadResponse.ok) {
      const errData = await uploadResponse.json()
      throw new Error(errData.detail || 'Upload failed')
    }
    
    const { session_id } = await uploadResponse.json()
    sessionId.value = session_id
    isUploading.value = false
    isProcessing.value = true

    // Persist session to localStorage for page refresh recovery
    saveSessionToStorage(session_id)
    
    // Close the upload modal, show floating panel
    isOpen.value = false
    
    // Connect to SSE stream
    connectToStream(session_id)
    
  } catch (e) {
    error.value = e.message
    isUploading.value = false
    isProcessing.value = false
    isLoadingPageContent.value = false
  }
}

function connectToStream(sid, isReconnect = false) {
  const url = isReconnect ? `/api/ingest/stream/${sid}?reconnect=true` : `/api/ingest/stream/${sid}`
  eventSource.value = new EventSource(url)
  
  eventSource.value.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data)
    
    currentPhase.value = data.phase
    currentMessage.value = data.message
    progress.value = data.progress

    // Pause state tracking
    if (data.phase === 'paused') {
      isPaused.value = true
      isPausing.value = false // Pause request completed
    } else if (isPaused.value && data.phase !== 'paused') {
      isPaused.value = false
      isPausing.value = false
    }
    
    // Handle User Story assignment to BC FIRST (before created objects)
    // This must happen before "Handle created objects" because we need to move user stories from root to BC trees
    if (data.data && data.data.type === 'UserStoryAssigned') {
      const assignment = data.data.object
      if (!assignment) {
        return
      }
      // Pass user story data from event if available
      const usDataFromEvent = assignment.role || assignment.action ? {
        id: assignment.id,
        role: assignment.role || '',
        action: assignment.action || '',
        benefit: assignment.benefit || '',
        priority: assignment.priority || '',
        status: assignment.status || 'draft'
      } : null
      navigatorStore.assignUserStoryToBC(
        assignment.id,
        assignment.targetBcId,
        assignment.targetBcName,
        usDataFromEvent
      )
      // Return early to avoid processing this as a created object
      return
    }
    
    // Handle created objects
    if (data.data?.object) {
      const obj = data.data.object
      // Only add items that have a type property
      if (!obj.type) {
        return
      }
      // Prevent duplicate items by checking if item with same id already exists
      const existingIndex = createdItems.value.findIndex(item => item.id === obj.id && item.type === obj.type)
      if (existingIndex === -1) {
      createdItems.value.push(obj)
      } else {
        // Update existing item instead of adding duplicate
        createdItems.value[existingIndex] = obj
      }
      
      // Trigger navigator updates for dynamic display
      if (obj.type === 'UserStory') {
        navigatorStore.addUserStory(obj)
      } else if (obj.type === 'BoundedContext') {
        navigatorStore.addContext(obj)
      } else if (obj.type === 'Aggregate') {
        navigatorStore.addAggregate(obj)
      } else if (obj.type === 'Command') {
        navigatorStore.addCommand(obj)
      } else if (obj.type === 'Event') {
        navigatorStore.addEvent(obj)
      } else if (obj.type === 'Policy') {
        navigatorStore.addPolicy(obj)
      } else if (obj.type === 'ReadModel') {
        navigatorStore.addReadModel(obj)
      } else if (obj.type === 'UI') {
        navigatorStore.addUI(obj)
      } else if (obj.type === 'CQRSOperation') {
        navigatorStore.addCQRSOperation(obj)
      } else if (obj.type === 'Property') {
        navigatorStore.addProperty(obj)
      }
    }
    
    // Handle summary
    if (data.data?.summary) {
      summary.value = data.data.summary
    }
    
    // Handle completion
    if (data.phase === 'complete') {
      isProcessing.value = false
      closeStream()
      clearSessionFromStorage()
      navigatorStore.refreshAll()
    }
    
    // Handle error or cancellation
    if (data.phase === 'error') {
      // Only set error message if not already set (prevent duplicates from cancelIngestion)
      if (!error.value) {
        error.value = data.message || data.data?.error || '알 수 없는 오류가 발생했습니다'
      }
      isProcessing.value = false
      isPaused.value = false
      isPausing.value = false
      closeStream()
      // Don't clear sessionId immediately - keep panel open to show error message
      // Session will be cleared when user manually closes the panel
    }
  })
  
  eventSource.value.onerror = (err) => {
    if (isProcessing.value) {
      const errorDetails = {
        error: err,
        eventSourceState: eventSource.value?.readyState,
        url: eventSource.value?.url
      }
      console.error('[RequirementsIngestion] EventSource error:', errorDetails)
      
      // Only set error if not already set (prevent duplicates from cancelIngestion)
      if (!error.value) {
        // Check if it's a connection error
        const isConnectionError = eventSource.value?.readyState === EventSource.CLOSED
        error.value = isConnectionError 
          ? '서버 연결이 끊어졌습니다. 백엔드 서버가 실행 중인지 확인해주세요.'
          : '연결이 끊어졌습니다. 서버와의 연결을 확인해주세요.'
      }
      isProcessing.value = false
      isPaused.value = false
      isPausing.value = false
      // Don't clear sessionId immediately - keep panel open to show error message
      // Session will be cleared when user manually closes the panel
    }
    closeStream()
  }
}

// Cache status
async function checkCacheStatus() {
  try {
    const response = await fetch('/api/ingest/cache/status')
    if (response.ok) {
      const data = await response.json()
      isCacheEnabled.value = !!data.enabled
      // Do not show noisy UI on open; clear stale feedback if backend responds.
      if (cacheFeedback.value?.kind === 'error') {
        cacheFeedback.value = null
      }
    } else {
      // Backend reachable but endpoint failed; keep UX responsive.
      cacheFeedback.value = {
        kind: 'info',
        message: '캐시 상태를 확인할 수 없습니다.'
      }
    }
  } catch (e) {
    // Optional feature if backend missing; avoid "no-op" UX.
    cacheFeedback.value = {
      kind: 'info',
      message: '캐시 기능을 사용할 수 없습니다. (서버 연결 실패)'
    }
    console.error('Failed to check cache status:', e)
  }
}

async function toggleCache() {
  if (isTogglingCache.value) return
  isTogglingCache.value = true
  cacheFeedback.value = { kind: 'info', message: '캐시 설정 적용 중...' }
  try {
    const endpoint = isCacheEnabled.value ? 'disable' : 'enable'
    const response = await fetch(`/api/ingest/cache/${endpoint}`, { method: 'POST' })
    const data = await response.json().catch(() => ({}))

    // Always reflect server state when provided (even on logical failure)
    if (typeof data.enabled !== 'undefined') {
      isCacheEnabled.value = !!data.enabled
    }

    // Handle transport errors
    if (!response.ok) {
      const msg = data.detail || data.message || `캐시 ${endpoint} 요청에 실패했습니다.`
      cacheFeedback.value = { kind: 'error', message: msg }
      return
    }

    // Handle logical success/failure
    const success = typeof data.success === 'boolean' ? data.success : true
    const msg =
      data.message ||
      (success
        ? (isCacheEnabled.value ? '캐시가 활성화되었습니다.' : '캐시가 비활성화되었습니다.')
        : '캐시 설정을 변경할 수 없습니다.')

    cacheFeedback.value = { kind: success ? 'success' : 'error', message: msg }
  } catch (e) {
    cacheFeedback.value = { kind: 'error', message: '캐시 설정 변경 중 오류가 발생했습니다.' }
    console.error('Failed to toggle cache:', e)
  } finally {
    isTogglingCache.value = false
  }
}

async function togglePause() {
  if (!sessionId.value) return
  if (isPausing.value) return // Prevent multiple simultaneous pause requests
  
  try {
    const endpoint = isPaused.value ? 'resume' : 'pause'
    
    // Set pausing state when requesting pause (not resume)
    if (endpoint === 'pause') {
      isPausing.value = true
    }
    
    const response = await fetch(`/api/ingest/${sessionId.value}/${endpoint}`, { method: 'POST' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.detail || 'Pause/Resume failed')
    }
    
    // Server will also emit 'paused' on next checkpoint, but we can optimistically update UI.
    // Note: Actual pause happens when current LLM request completes, so isPaused will be set to true
    // when server emits 'paused' phase event. We keep isPausing true until then.
    if (endpoint === 'resume') {
      isPaused.value = false
      isPausing.value = false
    }
    // For pause, don't set isPaused immediately - wait for server to emit 'paused' phase
    // isPausing will be set to false when we receive the 'paused' phase event
  } catch (e) {
    console.error('Failed to toggle pause:', e)
    error.value = e.message || '일시정지/재개 실패'
    isPausing.value = false
  }
}

async function cancelIngestion() {
  if (!sessionId.value) return
  if (!confirm('생성을 중단하시겠습니까? 진행 중인 작업이 취소됩니다.')) {
    return
  }
  
  try {
    // Immediately close event source and update UI state
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
    isProcessing.value = false
    isPaused.value = false
    isPausing.value = false
    
    // Set error message only if not already set (prevent duplicates)
    if (!error.value) {
      error.value = '생성이 중단되었습니다'
    }
    // Keep panel open to show error message - don't clear sessionId yet
    
    // Then call cancel API
    try {
      const response = await fetch(`/api/ingest/${sessionId.value}/cancel`, { method: 'POST' })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        // 404 means session not found (already expired/deleted) - this is OK, just log it
        if (response.status === 404) {
          console.log('Session already expired or not found, cancellation may have already completed')
          // Keep error message and panel open
          return
        }
        throw new Error(data.detail || data.message || 'Cancel failed')
      }
    } catch (fetchError) {
      // Network error or other fetch issues - UI is already updated, just log
      if (fetchError.name === 'TypeError' && fetchError.message.includes('fetch')) {
        console.log('Network error during cancel request, but UI state is already updated')
        // Keep error message and panel open
        return
      }
      throw fetchError // Re-throw other errors
    }
    
    // Don't clear sessionId immediately - keep panel open to show error message
    // Session will be cleared when user manually closes the panel
  } catch (e) {
    console.error('Failed to cancel ingestion:', e)
    // Only set error if not already set (prevent duplicates)
    if (!error.value) {
      error.value = e.message || '중단 실패'
    }
    // Keep panel open to show error message
  }
}

// Session persistence for page refresh recovery
function saveSessionToStorage(sid) {
  const sessionData = { sessionId: sid, startedAt: Date.now() }
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sessionData))
}

function clearSessionFromStorage() {
  localStorage.removeItem(SESSION_STORAGE_KEY)
}

function getSessionFromStorage() {
  try {
    const data = localStorage.getItem(SESSION_STORAGE_KEY)
    if (!data) return null
    const session = JSON.parse(data)
    // expire after 30 minutes
    const thirtyMinutes = 30 * 60 * 1000
    if (Date.now() - session.startedAt > thirtyMinutes) {
      clearSessionFromStorage()
      return null
    }
    return session
  } catch (e) {
    clearSessionFromStorage()
    return null
  }
}

async function checkAndRestoreSession() {
  const saved = getSessionFromStorage()
  if (!saved?.sessionId) return

  try {
    const response = await fetch(`/api/ingest/session/${saved.sessionId}/status`)
    if (!response.ok) {
      clearSessionFromStorage()
      return
    }

    const status = await response.json()
    if (!status.active) {
      clearSessionFromStorage()
      return
    }

    sessionId.value = saved.sessionId
    isProcessing.value = true
    currentPhase.value = status.phase || 'processing'
    currentMessage.value = status.message || '진행 중인 세션에 재연결 중...'
    progress.value = status.progress || 0
    isPaused.value = !!status.isPaused

    emit('session-restored')
    connectToStream(saved.sessionId, true)
  } catch (e) {
    console.error('Failed to restore session:', e)
    clearSessionFromStorage()
  }
}

function closeStream() {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
}

// Draggable floating panel handlers
function startDrag(e) {
  // Don't start drag if clicking on buttons or their children
  if (e.target.closest('.panel-btn') || e.target.closest('.floating-panel__actions')) return
  isDragging.value = true
  hasDragged.value = false // Reset drag flag
  const panel = e.currentTarget.closest('.floating-panel')
  const rect = panel.getBoundingClientRect()
  dragOffset.value = { x: e.clientX - rect.left, y: e.clientY - rect.top }
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(e) {
  if (!isDragging.value) return
  hasDragged.value = true // Mark that actual dragging occurred
  const x = e.clientX - dragOffset.value.x
  const y = e.clientY - dragOffset.value.y
  const panelWidth = 320
  const panelHeight = 220
  panelPosition.value = {
    x: Math.max(0, Math.min(window.innerWidth - panelWidth, x)),
    y: Math.max(0, Math.min(window.innerHeight - panelHeight, y))
  }
}

function stopDrag() {
  isDragging.value = false
  // Reset hasDragged after a short delay to allow click handler to check it
  setTimeout(() => {
    hasDragged.value = false
  }, 100)
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

const panelStyle = computed(() => {
  if (panelPosition.value.x !== null && panelPosition.value.y !== null) {
    return { top: `${panelPosition.value.y}px`, left: `${panelPosition.value.x}px`, right: 'auto', bottom: 'auto' }
  }
  // Default position: bottom-right (keep existing UX)
  return { bottom: 'var(--spacing-lg)', right: 'var(--spacing-lg)', top: 'auto', left: 'auto' }
})

function closeModal() {
  // Reset state
  file.value = null
  textContent.value = ''
  error.value = null
  jiraError.value = null
  showClearConfirm.value = false
  isOpen.value = false
}

function closeFloatingPanel() {
  if (isProcessing.value) {
    if (!confirm('진행 중인 작업이 있습니다. 정말 닫으시겠습니까?')) {
      return
    }
    closeStream()
    isProcessing.value = false
  }
  
  // If there's an error or cancellation message, ask for confirmation
  if (error.value && !isProcessing.value) {
    if (!confirm('오류 또는 중단 메시지가 표시되고 있습니다. 정말 닫으시겠습니까?')) {
      return
    }
  }
  
  // Reset state
  progress.value = 0
  currentPhase.value = ''
  currentMessage.value = ''
  createdItems.value = []
  summary.value = null
  error.value = null
  isPaused.value = false
  panelPosition.value = { x: null, y: null }
  sessionId.value = null
  clearSessionFromStorage()
  
  emit('complete')
}

function toggleMinimize() {
  isPanelMinimized.value = !isPanelMinimized.value
}

function handleHeaderClick(e) {
  // Only toggle minimize if:
  // 1. Not currently dragging
  // 2. No actual drag occurred (just a click, not drag)
  // 3. Not clicking on buttons
  if (!isDragging.value && !hasDragged.value && !e.target.closest('.panel-btn') && !e.target.closest('.floating-panel__actions')) {
    toggleMinimize()
  }
}

function getTypeIcon(type) {
  const icons = {
    UserStory: 'US',
    BoundedContext: 'BC',
    Aggregate: 'A',
    Command: 'C',
    Event: 'E',
    Policy: 'P',
    ReadModel: 'RM',
    UI: 'UI',
    CQRSOperation: '⚡',
    Property: '{ }'
  }
  return icons[type] || '?'
}

function getTypeClass(type) {
  if (!type) return 'item-icon--unknown'
  return `item-icon--${type.toLowerCase()}`
}

// Cleanup on unmount
onUnmounted(() => {
  closeStream()
})

onMounted(async () => {
  loadJiraCreds()
  await checkAndRestoreSession()
})

// Sample requirements text
const sampleText = `# 온라인 쇼핑몰 요구사항

## 1. 주문 관리
- 고객은 상품을 장바구니에 담고 주문할 수 있어야 한다
- 고객은 주문을 취소할 수 있어야 한다 (배송 전까지)
- 고객은 주문 상태를 조회할 수 있어야 한다

## 2. 상품 관리
- 판매자는 상품을 등록할 수 있어야 한다
- 판매자는 상품 정보를 수정할 수 있어야 한다
- 판매자는 상품 재고를 관리할 수 있어야 한다

## 3. 결제 처리
- 시스템은 주문 시 결제를 처리해야 한다
- 주문 취소 시 자동으로 환불이 처리되어야 한다

## 4. 재고 관리
- 주문 시 재고가 자동으로 차감되어야 한다
- 주문 취소 시 재고가 복원되어야 한다

## 5. 알림
- 주문 완료 시 고객에게 이메일 알림을 보내야 한다
- 배송 시작 시 고객에게 알림을 보내야 한다`

// JIRA/Confluence methods
function loadJiraCreds() {
  try {
    const saved = localStorage.getItem(JIRA_CREDS_KEY)
    if (saved) {
      const creds = JSON.parse(saved)
      jiraEmail.value = creds.email || ''
      jiraApiToken.value = creds.apiToken || ''
      jiraBaseUrl.value = creds.baseUrl || 'https://uengine-team.atlassian.net'
    }
  } catch (e) {
    console.error('Failed to load JIRA credentials:', e)
  }
}

function saveJiraCreds() {
  localStorage.setItem(JIRA_CREDS_KEY, JSON.stringify({
    email: jiraEmail.value,
    apiToken: jiraApiToken.value,
    baseUrl: jiraBaseUrl.value
  }))
}

async function connectConfluence() {
  if (!jiraEmail.value.trim() || !jiraApiToken.value.trim()) {
    jiraError.value = '이메일과 API 토큰을 입력해주세요.'
    return
  }

  jiraError.value = null
  isConnecting.value = true
  confluencePages.value = []
  selectedPageId.value = null
  selectedPageContent.value = null

  try {
    const response = await fetch('/api/ingest/confluence/pages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: jiraEmail.value.trim(),
        api_token: jiraApiToken.value.trim(),
        base_url: jiraBaseUrl.value.trim()
      })
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || `연결 실패 (${response.status})`)
    }

    const data = await response.json()
    confluencePages.value = data.pages || []
    jiraConnected.value = true
    saveJiraCreds()
  } catch (e) {
    jiraError.value = e.message || 'Confluence 연결에 실패했습니다.'
    jiraConnected.value = false
  } finally {
    isConnecting.value = false
  }
}

async function selectPage(pageId) {
  if (selectedPageId.value === pageId) return
  selectedPageId.value = pageId
  selectedPageContent.value = null
  isLoadingPageContent.value = true
  jiraError.value = null

  try {
    const response = await fetch('/api/ingest/confluence/page-content', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: jiraEmail.value.trim(),
        api_token: jiraApiToken.value.trim(),
        base_url: jiraBaseUrl.value.trim(),
        page_id: pageId
      })
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || `페이지 내용을 가져올 수 없습니다.`)
    }

    selectedPageContent.value = await response.json()
  } catch (e) {
    jiraError.value = e.message
    selectedPageId.value = null
  } finally {
    isLoadingPageContent.value = false
  }
}

function clearSelectedPage() {
  selectedPageId.value = null
  selectedPageContent.value = null
}

async function refreshPages() {
  selectedPageId.value = null
  selectedPageContent.value = null
  jiraError.value = null
  isConnecting.value = true

  try {
    const response = await fetch('/api/ingest/confluence/pages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: jiraEmail.value.trim(),
        api_token: jiraApiToken.value.trim(),
        base_url: jiraBaseUrl.value.trim()
      })
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || `새로고침 실패 (${response.status})`)
    }

    const data = await response.json()
    confluencePages.value = data.pages || []
  } catch (e) {
    jiraError.value = e.message || '페이지 목록 새로고침에 실패했습니다.'
  } finally {
    isConnecting.value = false
  }
}

function disconnectConfluence() {
  jiraConnected.value = false
  confluencePages.value = []
  selectedPageId.value = null
  selectedPageContent.value = null
  pageSearchQuery.value = ''
}

function useSample() {
  textContent.value = sampleText
  inputMode.value = 'text'
}
</script>

<template>
  <!-- Upload Dialog (initial file selection) - Blocking Modal -->
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && !isProcessing" class="modal-overlay" @click.self="closeModal">
        <div class="modal-container">
          <!-- Header -->
          <div class="modal-header">
            <h2 class="modal-title">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="12" y1="18" x2="12" y2="12"></line>
                <line x1="9" y1="15" x2="15" y2="15"></line>
              </svg>
              요구사항 문서 업로드
            </h2>
            <button class="modal-close" @click="closeModal">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          
          <!-- Body -->
          <div class="modal-body">
            <!-- Existing Data Warning -->
            <div v-if="hasExistingData && !showClearConfirm" class="existing-data-warning">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              <span>
                기존 데이터가 있습니다: 
                <strong>{{ existingDataStats.total }}개</strong> 노드
              </span>
            </div>
            
            <!-- Clear Confirmation Dialog -->
            <div v-if="showClearConfirm" class="clear-confirm-dialog">
              <div class="clear-confirm-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                  <line x1="12" y1="9" x2="12" y2="13"></line>
                  <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
              </div>
              <h3 class="clear-confirm-title">기존 데이터 삭제 확인</h3>
              <p class="clear-confirm-message">
                새로운 요구사항을 분석하기 전에 기존 데이터를 모두 삭제해야 합니다.
              </p>
              <div class="clear-confirm-stats">
                <div v-for="(count, type) in existingDataStats.by_type" :key="type" class="stat-chip">
                  <span class="stat-chip-label">{{ type }}</span>
                  <span class="stat-chip-value">{{ count }}</span>
                </div>
              </div>
              <p class="clear-confirm-warning">
                ⚠️ 이 작업은 되돌릴 수 없습니다.
              </p>
              <div class="clear-confirm-actions">
                <button class="btn btn--secondary" @click="cancelClear" :disabled="isClearing">
                  취소
                </button>
                <button class="btn btn--danger" @click="confirmClearAndStart" :disabled="isClearing">
                  <template v-if="isClearing">
                    <span class="spinner"></span>
                    삭제 중...
                  </template>
                  <template v-else>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                    삭제하고 계속
                  </template>
                </button>
              </div>
            </div>
            
            <!-- Normal upload UI (hidden during confirm) -->
            <template v-if="!showClearConfirm">
              <!-- Row 1: Input Mode (파일 업로드 / 텍스트 입력) + Cache Toggle -->
              <div class="options-block">
                <div class="options-row">
                  <div class="input-tabs">
                    <button 
                      :class="['tab-btn', { active: inputMode === 'file' }]"
                      @click="inputMode = 'file'"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
                        <polyline points="13 2 13 9 20 9"></polyline>
                      </svg>
                      파일 업로드
                    </button>
                    <button
                      :class="['tab-btn', { active: inputMode === 'text' }]"
                      @click="inputMode = 'text'"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="17" y1="10" x2="3" y2="10"></line>
                        <line x1="21" y1="6" x2="3" y2="6"></line>
                        <line x1="21" y1="14" x2="3" y2="14"></line>
                        <line x1="17" y1="18" x2="3" y2="18"></line>
                      </svg>
                      텍스트 입력
                    </button>
                    <button
                      :class="['tab-btn', { active: inputMode === 'jira' }]"
                      @click="inputMode = 'jira'"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                        <path d="M2 17l10 5 10-5"></path>
                        <path d="M2 12l10 5 10-5"></path>
                      </svg>
                      JIRA
                    </button>
                  </div>
                  <div class="cache-toggle">
                    <label class="cache-toggle__label" title="LangChain 캐시를 활성화하면 동일한 요청의 속도가 빨라집니다">
                      <span class="cache-toggle__text">캐시</span>
                      <button 
                        class="cache-toggle__switch"
                        :class="{ 'is-enabled': isCacheEnabled }"
                        @click="toggleCache"
                        :disabled="isTogglingCache"
                      >
                        <span class="cache-toggle__knob"></span>
                      </button>
                    </label>
                    <span v-if="isTogglingCache" class="cache-toggle__pending">적용 중...</span>
                  </div>
                </div>
                <!-- Row 2: Source type + Display language -->
                <div class="options-sub-row">
                  <div class="display-language-row">
                    <span class="display-language-label">표시 언어</span>
                    <div class="display-language-tabs">
                      <button
                        :class="['tab-btn', 'tab-btn--small', { active: displayLanguage === 'ko' }]"
                        @click="displayLanguage = 'ko'"
                      >
                        한글
                      </button>
                      <button
                        :class="['tab-btn', 'tab-btn--small', { active: displayLanguage === 'en' }]"
                        @click="displayLanguage = 'en'"
                      >
                        English
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div
                v-if="cacheFeedback?.message"
                class="cache-feedback"
                :class="`cache-feedback--${cacheFeedback.kind}`"
              >
                {{ cacheFeedback.message }}
              </div>
              
              <!-- File Upload Area -->
              <div v-if="inputMode === 'file'" class="upload-section">
                <div 
                  class="dropzone"
                  :class="{ 'is-active': dragActive, 'has-file': file }"
                  @dragover="handleDragOver"
                  @dragleave="handleDragLeave"
                  @drop="handleDrop"
                  @click="$refs.fileInput.click()"
                >
                  <input 
                    ref="fileInput"
                    type="file" 
                    accept=".txt,.pdf,.md"
                    style="display: none"
                    @change="handleFileSelect"
                  />
                  
                  <div v-if="!file" class="dropzone-content">
                    <div class="dropzone-icon">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="17 8 12 3 7 8"></polyline>
                        <line x1="12" y1="3" x2="12" y2="15"></line>
                      </svg>
                    </div>
                    <p class="dropzone-text">파일을 드래그하거나 클릭하여 선택</p>
                    <p class="dropzone-hint">PDF, TXT, MD 파일 지원</p>
                  </div>
                  
                  <div v-else class="file-preview">
                    <div class="file-icon">
                      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                      </svg>
                    </div>
                    <div class="file-info">
                      <span class="file-name">{{ file.name }}</span>
                      <span class="file-size">{{ (file.size / 1024).toFixed(1) }} KB</span>
                    </div>
                    <button class="file-remove" @click.stop="removeFile">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
              
              <!-- Text Input Area -->
              <div v-if="inputMode === 'text'" class="text-section">
                <textarea
                  v-model="textContent"
                  class="text-input"
                  placeholder="요구사항 문서 내용을 입력하세요..."
                  rows="10"
                ></textarea>
                <button class="sample-btn" @click="useSample">
                  샘플 요구사항 사용
                </button>
              </div>

              <!-- JIRA/Confluence Area -->
              <div v-if="inputMode === 'jira'" class="jira-section">
                <!-- Credentials Form -->
                <div v-if="!jiraConnected" class="jira-creds">
                  <div class="jira-field">
                    <label class="jira-label">Confluence Base URL</label>
                    <input
                      v-model="jiraBaseUrl"
                      type="url"
                      class="jira-input"
                      placeholder="https://your-team.atlassian.net"
                    />
                  </div>
                  <div class="jira-field">
                    <label class="jira-label">이메일</label>
                    <input
                      v-model="jiraEmail"
                      type="email"
                      class="jira-input"
                      placeholder="your-email@company.com"
                    />
                  </div>
                  <div class="jira-field">
                    <label class="jira-label">API Token</label>
                    <input
                      v-model="jiraApiToken"
                      type="password"
                      class="jira-input"
                      placeholder="Atlassian API Token"
                    />
                    <span class="jira-hint">
                      <a href="https://id.atlassian.com/manage-profile/security/api-tokens" target="_blank" rel="noopener">API 토큰 발급하기</a>
                    </span>
                  </div>
                  <div v-if="jiraError" class="jira-error">{{ jiraError }}</div>
                  <button
                    class="btn btn--primary jira-connect-btn"
                    :disabled="isConnecting || !jiraEmail.trim() || !jiraApiToken.trim()"
                    @click="connectConfluence"
                  >
                    <template v-if="isConnecting">
                      <span class="spinner"></span>
                      연결 중...
                    </template>
                    <template v-else>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
                        <polyline points="10 17 15 12 10 7"></polyline>
                        <line x1="15" y1="12" x2="3" y2="12"></line>
                      </svg>
                      연동하기
                    </template>
                  </button>
                </div>

                <!-- Page List & Preview (after connection) -->
                <div v-else class="jira-pages">
                  <div class="jira-pages-header">
                    <div class="jira-pages-info">
                      <span class="jira-pages-count">{{ confluencePages.length }}개 페이지</span>
                    </div>
                    <div class="jira-header-actions">
                      <button class="jira-action-btn" @click="refreshPages" :disabled="isConnecting" title="새로고침">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'is-spinning': isConnecting }">
                          <polyline points="23 4 23 10 17 10"></polyline>
                          <polyline points="1 20 1 14 7 14"></polyline>
                          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                        </svg>
                      </button>
                      <button class="jira-action-btn jira-action-btn--disconnect" @click="disconnectConfluence" title="연결 해제">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                          <polyline points="16 17 21 12 16 7"></polyline>
                          <line x1="21" y1="12" x2="9" y2="12"></line>
                        </svg>
                      </button>
                    </div>
                  </div>

                  <!-- Content Preview (shown when a page is selected) -->
                  <div v-if="selectedPageContent" class="jira-preview">
                    <div class="jira-preview-header">
                      <button class="jira-back-btn" @click="clearSelectedPage">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="15 18 9 12 15 6"></polyline>
                        </svg>
                        목록으로
                      </button>
                      <span class="jira-preview-size">{{ (selectedPageContent.content_length / 1024).toFixed(1) }} KB</span>
                    </div>
                    <h4 class="jira-preview-title">{{ selectedPageContent.title }}</h4>
                    <div class="jira-preview-content">{{ selectedPageContent.content }}</div>
                  </div>

                  <!-- Loading state -->
                  <div v-else-if="isLoadingPageContent" class="jira-loading">
                    <span class="spinner"></span>
                    <span>페이지 내용을 불러오는 중...</span>
                  </div>

                  <!-- Page list (shown when no page is selected) -->
                  <template v-else>
                    <div class="jira-search">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="11" cy="11" r="8"></circle>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                      </svg>
                      <input
                        v-model="pageSearchQuery"
                        type="text"
                        class="jira-search-input"
                        placeholder="페이지 검색..."
                      />
                    </div>
                    <div class="jira-page-list">
                      <div
                        v-for="page in filteredPages"
                        :key="page.id"
                        class="jira-page-item"
                        @click="selectPage(page.id)"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                          <polyline points="14 2 14 8 20 8"></polyline>
                        </svg>
                        <div class="jira-page-info">
                          <span class="jira-page-title">{{ page.title }}</span>
                          <span class="jira-page-id">ID: {{ page.id }}</span>
                        </div>
                        <svg class="jira-page-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="9 18 15 12 9 6"></polyline>
                        </svg>
                      </div>
                      <div v-if="filteredPages.length === 0" class="jira-empty">
                        {{ pageSearchQuery ? '검색 결과가 없습니다.' : '페이지가 없습니다.' }}
                      </div>
                    </div>
                  </template>

                  <div v-if="jiraError" class="jira-error">{{ jiraError }}</div>
                </div>
              </div>
              
              <!-- Error Display -->
              <div v-if="error" class="error-message">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                {{ error }}
              </div>
            </template>
          </div>
          
          <!-- Footer (hidden during confirm) -->
          <div v-if="!showClearConfirm" class="modal-footer">
            <button class="btn btn--secondary" @click="closeModal">
              취소
            </button>
            <button 
              class="btn btn--primary"
              :disabled="!canSubmit || isUploading || isLoadingPageContent"
              @click="handleStartClick"
            >
              <template v-if="isUploading || isLoadingPageContent">
                <span class="spinner"></span>
                {{ isLoadingPageContent ? '페이지 내용 가져오는 중...' : '업로드 중...' }}
              </template>
              <template v-else>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                분석 시작
              </template>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
  
  <!-- Floating Progress Panel (Bottom-Right, Non-blocking) -->
  <Teleport to="body">
    <Transition name="slide-up">
      <div v-if="showFloatingPanel" class="floating-panel" :class="{ 'is-minimized': isPanelMinimized }" :style="panelStyle">
        <!-- Panel Header -->
        <div class="floating-panel__header" @mousedown="startDrag" @click="handleHeaderClick">
          <div class="floating-panel__title">
            <div class="floating-panel__status" :class="{ 'is-complete': summary, 'is-error': error, 'is-paused': isPaused, 'is-pausing': isPausing }">
              <span v-if="isPaused" class="status-paused">⏸</span>
              <span v-else-if="isPausing" class="status-pausing">⏸</span>
              <span v-else-if="isProcessing && !error" class="status-spinner"></span>
              <svg v-else-if="summary" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              <svg v-else-if="error" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
              </svg>
            </div>
            <span class="floating-panel__label">
              {{ summary ? '생성 완료' : error ? (error.includes('중단') ? '생성 중단' : '오류 발생') : isPausing ? '일시정지 중...' : phaseLabel }}
            </span>
            <span v-if="!summary && !error && !isPausing" class="floating-panel__percent">{{ progress }}%</span>
          </div>
          <div class="floating-panel__actions" @mousedown.stop>
            <button
              v-if="isProcessing && !summary && !error"
              class="panel-btn panel-btn--pause"
              :class="{ 'is-paused': isPaused, 'is-pausing': isPausing }"
              @click.stop="togglePause"
              :disabled="isPausing"
              :title="isPausing ? '일시정지 중...' : isPaused ? '재개' : '일시정지'"
            >
              <svg v-if="!isPaused" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="6" y="4" width="4" height="16"></rect>
                <rect x="14" y="4" width="4" height="16"></rect>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="8 5 19 12 8 19 8 5"></polygon>
              </svg>
            </button>
            <button
              v-if="isProcessing && !summary && !error"
              class="panel-btn panel-btn--cancel"
              @click.stop="cancelIngestion"
              title="중단"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
              </svg>
            </button>
            <button class="panel-btn" @click.stop="toggleMinimize" :title="isPanelMinimized ? '펼치기' : '접기'">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline v-if="isPanelMinimized" points="18 15 12 9 6 15"></polyline>
                <polyline v-else points="6 9 12 15 18 9"></polyline>
              </svg>
            </button>
            <button class="panel-btn" @click.stop="closeFloatingPanel" title="닫기">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>
        
        <!-- Progress Bar (visible when processing) -->
        <div v-if="isProcessing && !isPanelMinimized" class="floating-panel__progress">
          <div class="mini-progress-bar">
            <div class="mini-progress-fill" :style="{ width: `${progress}%` }"></div>
          </div>
          <p class="floating-panel__message">
            {{ isPausing ? '일시정지 요청 중... (현재 작업 완료 대기 중)' : currentMessage }}
          </p>
        </div>
        
        <!-- Error/Cancellation Message (visible when not processing but has error) -->
        <div v-if="!isProcessing && error && !isPanelMinimized" class="floating-panel__progress">
          <div class="floating-panel__error-header">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <p class="floating-panel__message floating-panel__message--error">{{ error }}</p>
          </div>
        </div>
        
        <!-- Panel Body (collapsible) -->
        <div v-if="!isPanelMinimized" class="floating-panel__body">
          <!-- Live Created Items -->
          <div v-if="isProcessing && !error" class="mini-items">
            <TransitionGroup name="item-list">
              <template v-for="item in createdItems.slice(-5)" :key="item.id">
                <div 
                  v-if="item && item.type"
                  class="mini-item"
                >
                  <span class="item-icon" :class="getTypeClass(item.type)">
                    {{ getTypeIcon(item.type) }}
                  </span>
                  <span class="mini-item__name">{{ item.name || item.id }}</span>
                </div>
              </template>
            </TransitionGroup>
            <div v-if="createdItems.length > 5" class="mini-items__more">
              +{{ createdItems.length - 5 }} items
            </div>
          </div>
          
          <!-- Summary View -->
          <div v-if="summary" class="mini-summary">
            <div class="mini-summary__stats">
              <div class="mini-stat">
                <span class="mini-stat__icon stat-icon--userstory">US</span>
                <span class="mini-stat__value">{{ summary.user_stories || 0 }}</span>
              </div>
              <div class="mini-stat">
                <span class="mini-stat__icon stat-icon--bc">BC</span>
                <span class="mini-stat__value">{{ summary.bounded_contexts }}</span>
              </div>
              <div class="mini-stat">
                <span class="mini-stat__icon stat-icon--aggregate">A</span>
                <span class="mini-stat__value">{{ summary.aggregates }}</span>
              </div>
              <div class="mini-stat">
                <span class="mini-stat__icon stat-icon--command">C</span>
                <span class="mini-stat__value">{{ summary.commands }}</span>
              </div>
              <div class="mini-stat">
                <span class="mini-stat__icon stat-icon--event">E</span>
                <span class="mini-stat__value">{{ summary.events }}</span>
              </div>
              <div class="mini-stat">
                <span class="mini-stat__icon stat-icon--policy">P</span>
                <span class="mini-stat__value">{{ summary.policies }}</span>
              </div>
              <div class="mini-stat">
                <span class="mini-stat__icon stat-icon--readmodel">RM</span>
                <span class="mini-stat__value">{{ summary.readmodels || 0 }}</span>
              </div>
              <div class="mini-stat">
                <span class="mini-stat__icon stat-icon--ui">UI</span>
                <span class="mini-stat__value">{{ summary.uis || 0 }}</span>
              </div>
            </div>
            <p class="mini-summary__hint">네비게이터에서 확인하세요</p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ============================================
   Upload Modal Styles
   ============================================ */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  width: 90%;
  max-width: 560px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
}

.modal-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.modal-title svg {
  color: var(--color-accent);
}

.modal-close {
  background: transparent;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: background 0.15s, color 0.15s;
}

.modal-close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-bright);
}

.modal-body {
  flex: 1;
  padding: var(--spacing-lg);
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--color-border);
}

/* Existing Data Warning */
.existing-data-warning {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: rgba(255, 193, 7, 0.1);
  border: 1px solid rgba(255, 193, 7, 0.3);
  border-radius: var(--radius-md);
  color: #ffc107;
  font-size: 0.85rem;
  margin-bottom: var(--spacing-md);
}

/* Clear Confirmation Dialog */
.clear-confirm-dialog {
  text-align: center;
  padding: var(--spacing-lg) 0;
}

.clear-confirm-icon {
  color: #ff6464;
  margin-bottom: var(--spacing-md);
}

.clear-confirm-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: var(--spacing-sm);
}

.clear-confirm-message {
  color: var(--color-text);
  font-size: 0.9rem;
  margin-bottom: var(--spacing-md);
}

.clear-confirm-stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  justify-content: center;
  margin-bottom: var(--spacing-md);
}

.stat-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--color-bg-tertiary);
  border-radius: 20px;
  font-size: 0.8rem;
}

.stat-chip-label {
  color: var(--color-text-light);
}

.stat-chip-value {
  color: var(--color-text-bright);
  font-weight: 600;
}

.clear-confirm-warning {
  color: #ff6464;
  font-size: 0.85rem;
  margin-bottom: var(--spacing-lg);
}

.clear-confirm-actions {
  display: flex;
  justify-content: center;
  gap: var(--spacing-md);
}

/* Input Tabs */
.options-block {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.options-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.input-tabs {
  display: flex;
  gap: var(--spacing-xs);
  margin-bottom: 0;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  cursor: pointer;
  font-size: 0.875rem;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.tab-btn:hover {
  background: var(--color-bg);
}

.tab-btn.active {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: white;
}

.tab-btn--small {
  flex: 0 1 auto;
  min-width: 0;
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: 0.8rem;
}

/* Display language (for displayName) */
.options-sub-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  flex-wrap: wrap;
}

.display-language-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.display-language-label {
  font-size: 0.8rem;
  color: var(--color-text-light);
  font-weight: 500;
  white-space: nowrap;
}

.display-language-tabs {
  display: flex;
  gap: var(--spacing-xs);
}

/* Cache Toggle */
.cache-toggle {
  display: flex;
  align-items: center;
}

.cache-toggle__label {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
  user-select: none;
}

.cache-toggle__text {
  font-size: 0.8rem;
  color: var(--color-text-light);
  font-weight: 500;
}

.cache-toggle__switch {
  position: relative;
  width: 42px;
  height: 22px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  padding: 0;
}

.cache-toggle__switch:hover {
  border-color: var(--color-accent);
}

.cache-toggle__switch.is-enabled {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border-color: #059669;
}

.cache-toggle__switch:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cache-toggle__knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  background: white;
  border-radius: 50%;
  transition: transform 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
}

.cache-toggle__switch.is-enabled .cache-toggle__knob {
  transform: translateX(20px);
}

.cache-toggle__pending {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-left: var(--spacing-sm);
}

.cache-feedback {
  margin-top: var(--spacing-sm);
  padding: 8px 10px;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  border: 1px solid transparent;
}

.cache-feedback--success {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.25);
  color: #10b981;
}

.cache-feedback--error {
  background: rgba(255, 100, 100, 0.1);
  border-color: rgba(255, 100, 100, 0.3);
  color: #ff6464;
}

.cache-feedback--info {
  background: rgba(34, 139, 230, 0.08);
  border-color: rgba(34, 139, 230, 0.2);
  color: var(--color-text);
}

/* JIRA/Confluence Section */
.jira-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.jira-creds {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.jira-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.jira-label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--color-text-light);
}

.jira-input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: 0.85rem;
}

.jira-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.jira-hint {
  font-size: 0.7rem;
  color: var(--color-text-light);
}

.jira-hint a {
  color: var(--color-accent);
  text-decoration: none;
}

.jira-hint a:hover {
  text-decoration: underline;
}

.jira-connect-btn {
  align-self: flex-start;
  margin-top: var(--spacing-xs);
}

.jira-error {
  padding: var(--spacing-sm);
  background: rgba(255, 100, 100, 0.1);
  border: 1px solid rgba(255, 100, 100, 0.3);
  border-radius: var(--radius-md);
  color: #ff6464;
  font-size: 0.8rem;
}

.jira-pages {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.jira-pages-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.jira-pages-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.jira-pages-count {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-text-bright);
}

.jira-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xl);
  color: var(--color-text-light);
  font-size: 0.85rem;
}

.jira-loading .spinner {
  border-color: rgba(34, 139, 230, 0.3);
  border-top-color: var(--color-accent);
}

.jira-header-actions {
  display: flex;
  gap: 4px;
}

.jira-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.jira-action-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.jira-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.jira-action-btn--disconnect:hover {
  border-color: #ff6464;
  color: #ff6464;
}

.jira-action-btn .is-spinning {
  animation: spin 0.8s linear infinite;
}

.jira-search {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-light);
}

.jira-search svg {
  flex-shrink: 0;
}

.jira-search-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--color-text);
  font-size: 0.8rem;
  outline: none;
}

/* Preview */
.jira-preview {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.jira-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.jira-back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  font-size: 0.75rem;
  padding: 4px 8px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.jira-back-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.jira-preview-size {
  font-size: 0.7rem;
  color: var(--color-text-light);
}

.jira-preview-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.jira-preview-content {
  max-height: 240px;
  overflow-y: auto;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.6;
  color: var(--color-text);
  white-space: pre-wrap;
  word-break: break-word;
}

.jira-page-list {
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.jira-page-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  transition: background 0.1s;
  border-bottom: 1px solid var(--color-border);
}

.jira-page-item:last-child {
  border-bottom: none;
}

.jira-page-item:hover {
  background: var(--color-bg-tertiary);
}

.jira-page-item svg:first-child {
  color: var(--color-text-light);
  flex-shrink: 0;
}

.jira-page-arrow {
  color: var(--color-text-light);
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;
}

.jira-page-item:hover .jira-page-arrow {
  opacity: 1;
}

.jira-page-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.jira-page-title {
  font-size: 0.8rem;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.jira-page-id {
  font-size: 0.65rem;
  color: var(--color-text-light);
}

.jira-empty {
  padding: var(--spacing-lg);
  text-align: center;
  color: var(--color-text-light);
  font-size: 0.8rem;
}

/* Dropzone */
.dropzone {
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-xl);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.dropzone:hover,
.dropzone.is-active {
  border-color: var(--color-accent);
  background: rgba(34, 139, 230, 0.05);
}

.dropzone.has-file {
  border-style: solid;
  border-color: var(--color-accent);
  background: rgba(34, 139, 230, 0.05);
}

.dropzone-icon {
  color: var(--color-text-light);
  margin-bottom: var(--spacing-md);
}

.dropzone-text {
  font-size: 0.9rem;
  color: var(--color-text);
  margin-bottom: var(--spacing-xs);
}

.dropzone-hint {
  font-size: 0.8rem;
  color: var(--color-text-light);
}

/* File Preview */
.file-preview {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  text-align: left;
}

.file-icon {
  color: var(--color-accent);
}

.file-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.file-name {
  font-size: 0.875rem;
  color: var(--color-text-bright);
  font-weight: 500;
}

.file-size {
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.file-remove {
  background: transparent;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: background 0.15s, color 0.15s;
}

.file-remove:hover {
  background: rgba(255, 100, 100, 0.1);
  color: #ff6464;
}

/* Text Input */
.text-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.text-input {
  width: 100%;
  padding: var(--spacing-md);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  line-height: 1.5;
  resize: vertical;
  min-height: 160px;
}

.text-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.text-input::placeholder {
  color: var(--color-text-light);
}

.sample-btn {
  align-self: flex-start;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  font-size: 0.75rem;
  padding: var(--spacing-xs) var(--spacing-sm);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.sample-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

/* Error Message */
.error-message {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: rgba(255, 100, 100, 0.1);
  border: 1px solid rgba(255, 100, 100, 0.3);
  border-radius: var(--radius-md);
  color: #ff6464;
  font-size: 0.8rem;
  margin-top: var(--spacing-md);
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-lg);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, opacity 0.15s;
}

.btn--secondary {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text);
}

.btn--secondary:hover {
  background: var(--color-bg-tertiary);
}

.btn--primary {
  background: var(--color-accent);
  border: 1px solid var(--color-accent);
  color: white;
}

.btn--primary:hover {
  background: #1c7ed6;
  border-color: #1c7ed6;
}

.btn--danger {
  background: #ff6464;
  border: 1px solid #ff6464;
  color: white;
}

.btn--danger:hover {
  background: #e55555;
  border-color: #e55555;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ============================================
   Floating Panel Styles (Bottom-Right)
   ============================================ */
.floating-panel {
  position: fixed;
  bottom: var(--spacing-lg);
  right: var(--spacing-lg);
  width: 320px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: 900;
  overflow: hidden;
  transition: width 0.2s ease, height 0.2s ease;
}

.floating-panel.is-minimized {
  width: 240px;
}

.floating-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-tertiary);
  cursor: grab;
  user-select: none;
}

.floating-panel__header:active {
  cursor: grabbing;
}

.floating-panel__title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.floating-panel__status {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--color-accent);
  color: white;
}

.floating-panel__status.is-complete {
  background: #40c057;
}

.floating-panel__status.is-error {
  background: #ff6464;
}

.floating-panel__status.is-paused {
  background: #fcc419;
  color: #212529;
}

.floating-panel__status.is-pausing {
  background: #fcc419;
  color: #212529;
  opacity: 0.7;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 0.7;
  }
  50% {
    opacity: 1;
  }
}

.status-paused,
.status-pausing {
  font-size: 0.75rem;
  line-height: 1;
}

.status-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.floating-panel__label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--color-text-bright);
}

.floating-panel__percent {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-left: auto;
}

.floating-panel__actions {
  display: flex;
  gap: 2px;
}

.floating-panel__drag-handle {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 4px;
  border-radius: var(--radius-sm);
  cursor: grab;
  opacity: 0;
  transition: opacity 0.15s ease, background 0.15s ease;
}

.floating-panel__header:hover .floating-panel__drag-handle {
  opacity: 1;
}

.floating-panel__drag-handle:hover {
  background: var(--color-bg);
}

.floating-panel__drag-handle span {
  display: block;
  width: 14px;
  height: 2px;
  background: var(--color-text-light);
  border-radius: 2px;
  opacity: 0.7;
}

.panel-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.panel-btn:hover {
  background: var(--color-bg);
  color: var(--color-text-bright);
}

.panel-btn--pause.is-paused {
  color: var(--color-primary);
}

.panel-btn--cancel {
  color: var(--color-error, #ef4444);
}

.panel-btn--cancel:hover {
  background: var(--color-error-light, rgba(239, 68, 68, 0.1));
  color: var(--color-error, #ef4444);
}

.panel-btn--pause.is-paused {
  color: #212529;
}

.panel-btn--pause.is-pausing {
  opacity: 0.6;
  cursor: wait;
  animation: pulse 1.5s ease-in-out infinite;
}

.panel-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.floating-panel__progress {
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
}

.mini-progress-bar {
  height: 4px;
  background: var(--color-bg);
  border-radius: 2px;
  overflow: hidden;
}

.mini-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-accent), var(--color-command));
  border-radius: 2px;
  transition: width 0.3s ease;
}

.floating-panel__message {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-top: var(--spacing-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.floating-panel__message--error {
  color: #ef4444;
  font-weight: 500;
}

.floating-panel__error-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) 0;
}

.floating-panel__error-header svg {
  color: #ef4444;
  flex-shrink: 0;
}

.floating-panel__error {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  color: #ef4444;
  font-size: 0.8rem;
  margin: var(--spacing-sm) var(--spacing-md);
}

.floating-panel__body {
  padding: var(--spacing-sm) var(--spacing-md);
  max-height: 200px;
  overflow-y: auto;
}

/* Mini Items List */
.mini-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mini-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 4px 8px;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  animation: slideIn 0.2s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.item-icon {
  width: 18px;
  height: 18px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.6rem;
  font-weight: 600;
  color: white;
  flex-shrink: 0;
}

.item-icon--userstory { background: #20c997; font-size: 0.5rem; }
.item-icon--boundedcontext { background: var(--color-bc); border: 1.5px solid var(--color-text-light); color: var(--color-text-light); }
.item-icon--aggregate { background: var(--color-aggregate); color: var(--color-bc); }
.item-icon--command { background: var(--color-command); }
.item-icon--event { background: var(--color-event); }
.item-icon--policy { background: var(--color-policy); }
.item-icon--readmodel { background: var(--color-readmodel); font-size: 0.45rem; }
.item-icon--ui { background: var(--color-ui-light); color: #343a40; border: 1px solid #ced4da; font-size: 0.5rem; }
.item-icon--cqrsoperation { background: linear-gradient(135deg, #fcc419 0%, #fd7e14 100%); font-size: 0.55rem; }
.item-icon--property { background: #868e96; font-size: 0.5rem; }

.mini-item__name {
  font-size: 0.75rem;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mini-items__more {
  font-size: 0.7rem;
  color: var(--color-text-light);
  text-align: center;
  padding: 4px;
}

/* Mini Summary */
.mini-summary__stats {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-sm);
}

.mini-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--spacing-xs);
  background: var(--color-bg);
  border-radius: var(--radius-sm);
}

.mini-stat__icon {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.6rem;
  font-weight: 600;
  color: white;
}

.stat-icon--userstory { background: #20c997; font-size: 0.55rem; }
.stat-icon--bc { background: var(--color-bc); border: 1.5px solid var(--color-text-light); color: var(--color-text-light); }
.stat-icon--aggregate { background: var(--color-aggregate); color: var(--color-bc); }
.stat-icon--command { background: var(--color-command); }
.stat-icon--event { background: var(--color-event); }
.stat-icon--policy { background: var(--color-policy); }
.stat-icon--readmodel { background: var(--color-readmodel, #22b8cf); font-size: 0.45rem; }
.stat-icon--ui { background: var(--color-ui-light, #e9ecef); color: #343a40; border: 1px solid #ced4da; font-size: 0.5rem; }

.mini-stat__value {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.mini-summary__hint {
  font-size: 0.7rem;
  color: var(--color-text-light);
  text-align: center;
}

.mini-error {
  padding: var(--spacing-sm);
  background: rgba(255, 100, 100, 0.1);
  border-radius: var(--radius-sm);
  color: #ff6464;
  font-size: 0.75rem;
}

/* Transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(20px);
  opacity: 0;
}

/* Item list transitions */
.item-list-enter-active,
.item-list-leave-active {
  transition: all 0.2s ease;
}

.item-list-enter-from {
  opacity: 0;
  transform: translateX(-10px);
}

.item-list-leave-to {
  opacity: 0;
  transform: translateX(10px);
}
</style>
