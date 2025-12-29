import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTerminologyStore = defineStore('terminology', () => {
  // Developer mode toggle
  const developerMode = ref(false)

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

  // Toggle developer mode
  function toggleDeveloperMode() {
    developerMode.value = !developerMode.value
  }

  return {
    developerMode,
    terms,
    getTerm,
    toggleDeveloperMode
  }
})


