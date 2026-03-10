import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTerminologyStore = defineStore('terminology', () => {
  // Developer mode toggle
  const developerMode = ref(false)

  // Domain terminology (Ubiquitous Language): prefer displayName for labels
  const ubiquitousLanguageMode = ref(true)

  function initUbiquitousLanguageMode() {
    try {
      const saved = localStorage.getItem('app_ubiquitous_language')
      if (saved === '0' || saved === 'false') ubiquitousLanguageMode.value = false
      if (saved === '1' || saved === 'true') ubiquitousLanguageMode.value = true
    } catch (e) {
      // keep default
    }
  }

  // Term mappings
  const terms = computed(() => {
    if (developerMode.value) {
      return {
        BoundedContext: 'Microservice',
        Aggregate: 'DB',
        Command: 'API',
        Policy: 'Service',
        Event: 'Event', // Event stays the same
        ReadModel: 'READ API',
        UI: 'UI'
      }
    }
    return {
      BoundedContext: 'Bounded Context',
      Aggregate: 'Aggregate',
      Command: 'Command',
      Policy: 'Policy',
      Event: 'Event',
      ReadModel: 'Read Model',
      UI: 'UI'
    }
  })

  // Get term for a type
  function getTerm(type) {
    return terms.value[type] || type
  }

  // Label helper: if ubiquitousLanguageMode is on, prefer displayName
  function getLabel(obj) {
    const name = obj?.name ?? obj?.label ?? obj?.id ?? ''
    const displayName = obj?.displayName ?? ''
    if (ubiquitousLanguageMode.value) {
      return String(displayName || name || '')
    }
    return String(name || '')
  }

  // Toggle developer mode
  function toggleDeveloperMode() {
    developerMode.value = !developerMode.value
  }

  function toggleUbiquitousLanguageMode() {
    ubiquitousLanguageMode.value = !ubiquitousLanguageMode.value
    try {
      localStorage.setItem('app_ubiquitous_language', ubiquitousLanguageMode.value ? '1' : '0')
    } catch (e) {
      // ignore
    }
  }

  // Initialize on store creation
  initUbiquitousLanguageMode()

  return {
    developerMode,
    ubiquitousLanguageMode,
    terms,
    getTerm,
    getLabel,
    toggleDeveloperMode,
    toggleUbiquitousLanguageMode
  }
})


