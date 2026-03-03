import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * Store for managing ingestion state across the application.
 * This allows other components (like Model Modifier ChatPanel) to check if ingestion is in progress.
 */
export const useIngestionStore = defineStore('ingestion', () => {
  // Ingestion state
  const isProcessing = ref(false)
  const isPaused = ref(false)
  const currentPhase = ref('')
  const sessionId = ref(null)

  // Computed
  const isIngestionActive = computed(() => isProcessing.value && !isPaused.value)
  const isIngestionPaused = computed(() => isProcessing.value && isPaused.value)

  // Actions
  function setProcessing(value) {
    isProcessing.value = value
  }

  function setPaused(value) {
    isPaused.value = value
  }

  function setPhase(phase) {
    currentPhase.value = phase
  }

  function setSessionId(id) {
    sessionId.value = id
  }

  function reset() {
    isProcessing.value = false
    isPaused.value = false
    currentPhase.value = ''
    sessionId.value = null
  }

  return {
    // State
    isProcessing,
    isPaused,
    currentPhase,
    sessionId,
    // Computed
    isIngestionActive,
    isIngestionPaused,
    // Actions
    setProcessing,
    setPaused,
    setPhase,
    setSessionId,
    reset
  }
})
