/**
 * Pinia store for the Figma document binding (feature 016).
 *
 * State sources:
 *   - server-of-truth: `/api/figma-binding/*` (Neo4j-backed)
 *   - token storage: spec 009's `figma_api_creds` in localStorage (read-only here)
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from './api'

export const useFigmaBindingStore = defineStore('figmaBinding', () => {
  const binding = ref(null) // null when no active binding
  const isLoading = ref(false)
  const lastError = ref(null)
  const storyboards = ref([])

  const isActive = computed(
    () => !!binding.value && binding.value.status === 'active'
  )
  const status = computed(() => binding.value?.status || 'disconnected')
  const fileName = computed(() => binding.value?.figmaFileName || '')
  const fileKey = computed(() => binding.value?.figmaFileKey || '')

  async function loadBinding() {
    isLoading.value = true
    lastError.value = null
    try {
      binding.value = await api.getBinding()
    } catch (e) {
      lastError.value = e?.message || String(e)
    } finally {
      isLoading.value = false
    }
  }

  async function connect(fileKeyInput, apiToken) {
    isLoading.value = true
    lastError.value = null
    try {
      binding.value = await api.connect(fileKeyInput, apiToken)
      return true
    } catch (e) {
      lastError.value = e?.message || String(e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function disconnect() {
    isLoading.value = true
    lastError.value = null
    try {
      await api.disconnect()
      binding.value = null
      storyboards.value = []
      return true
    } catch (e) {
      lastError.value = e?.message || String(e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function replace(fileKeyInput, apiToken) {
    isLoading.value = true
    lastError.value = null
    try {
      binding.value = await api.replace(fileKeyInput, apiToken)
      // Storyboard mappings from the previous file are archived server-side;
      // refresh the local view to reflect that.
      storyboards.value = []
      return true
    } catch (e) {
      lastError.value = e?.message || String(e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function loadStoryboards() {
    if (!isActive.value) {
      storyboards.value = []
      return
    }
    try {
      storyboards.value = await api.listStoryboards()
    } catch (e) {
      // non-fatal — leave previous list in place
      lastError.value = e?.message || String(e)
    }
  }

  return {
    // state
    binding,
    isLoading,
    lastError,
    storyboards,
    // computed
    isActive,
    status,
    fileName,
    fileKey,
    // actions
    loadBinding,
    connect,
    disconnect,
    replace,
    loadStoryboards,
  }
})
