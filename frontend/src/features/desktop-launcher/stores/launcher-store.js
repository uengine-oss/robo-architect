/**
 * Launcher view-state store (spec 032 T018).
 *
 * Transient state for the launcher screen itself: the saved + discovered
 * connection lists, per-entry probe status, current form mode, and any
 * surface-level error. Cleared on Enter.
 *
 * Distinct from the session store (which survives the launcher and is
 * read by the rest of the app for identity / connection identity).
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useLauncherStore = defineStore('launcher', () => {
  /** @type {import('vue').Ref<import('../../../../../desktop/src/shared/launcher-contract').SavedConnection[]>} */
  const savedConnections = ref([])
  /** @type {import('vue').Ref<import('../../../../../desktop/src/shared/launcher-contract').DiscoveredConnection[]>} */
  const discovered = ref([])
  /** id of the currently-highlighted entry (saved or discovered's discoveryId). */
  const selectedConnectionId = ref(null)
  /** Map<id, ProbeStatusResult>. */
  const probeStatusById = ref({})
  /** 'list' | 'add' | 'edit' */
  const formMode = ref('list')
  /** SavedConnection being edited when formMode === 'edit', else null. */
  const editing = ref(null)
  /** Last-error surfaced from any IPC call; user-visible. */
  const error = ref(null)

  const isEmptyState = computed(
    () => savedConnections.value.length === 0 && discovered.value.length === 0,
  )

  function setSavedConnections(list) {
    savedConnections.value = list
    if (selectedConnectionId.value === null && list.length > 0) {
      selectedConnectionId.value = list[0].id
    }
  }

  function setDiscovered(list) {
    discovered.value = list
  }

  function setProbeStatus(id, status) {
    probeStatusById.value = { ...probeStatusById.value, [id]: status }
  }

  function select(id) {
    selectedConnectionId.value = id
  }

  function showForm(mode, target = null) {
    formMode.value = mode
    editing.value = mode === 'edit' ? target : null
  }

  function clearError() {
    error.value = null
  }

  function setError(msg) {
    error.value = msg
  }

  return {
    savedConnections,
    discovered,
    selectedConnectionId,
    probeStatusById,
    formMode,
    editing,
    error,
    isEmptyState,
    setSavedConnections,
    setDiscovered,
    setProbeStatus,
    select,
    showForm,
    clearError,
    setError,
  }
})
