import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Cross-feature bridge for "open this node in the InspectorPanel".
 *
 * The Inspector lives inside CanvasWorkspace (Design tab) and exposes its
 * open-functions only to its own subtree via `provide('openInspector', ...)`.
 * Code outside that subtree (notably navigator/TreeNode) needs another path.
 *
 * Contract:
 *   - `request(nodeData)`     — push a node payload {id, type, ...} to be opened.
 *   - `pendingRequest`        — observable; CanvasWorkspace watches this and
 *                                calls openInspectorForNodeData(nodeData) when
 *                                it transitions from null → non-null.
 *   - `consume()`             — clear the pending request after handling.
 *   - `requestId`             — bumped on each request so consecutive opens of
 *                                the same node still trigger the watcher.
 *
 * Spec: 019-userstory-properties-panel — replaces the legacy
 * userStoryEditor.store + UserStoryEditModal.
 */
export const useInspectorRequestStore = defineStore('inspectorRequest', () => {
  const pendingRequest = ref(null)
  const requestId = ref(0)

  function request(nodeData) {
    if (!nodeData || !nodeData.id) return
    requestId.value += 1
    pendingRequest.value = { ...nodeData, _reqId: requestId.value }
  }

  function consume() {
    pendingRequest.value = null
  }

  return {
    pendingRequest,
    requestId,
    request,
    consume
  }
})
