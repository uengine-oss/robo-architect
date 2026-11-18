import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 043-fix — Cross-feature bridge for "open this Proposal node in the Design canvas".
 *
 * The Design canvas + Inspector + Vue Flow (fitView) all live inside
 * CanvasWorkspace and expose nothing to the app shell. The proposals feature
 * must not import viewer stores (Constitution V), so App.vue (orchestrator)
 * receives `robo:open-preview` (viewer === 'design'), enters the preview
 * session, then pushes a request here. CanvasWorkspace watches `requestId`
 * and: fetches the BC design-preview graph, snapshots+replaces the canvas,
 * focuses the target node, and opens its Inspector.
 *
 * Contract mirrors inspectorRequest.store:
 *   - request(payload)  — { proposalId, bcId, targetNodeId, nodeLabel, title }
 *   - pendingRequest    — observable; consumed by CanvasWorkspace
 *   - consume()         — clear after handling
 *   - requestId         — bumped each call so repeat opens still trigger
 */
export const useCanvasPreviewRequestStore = defineStore('canvasPreviewRequest', () => {
  const pendingRequest = ref(null)
  const requestId = ref(0)

  function request(payload) {
    // B-4 ⑧ 전체 미리보기는 { proposalId, bcIds:[…], full:true } — 포커스 대상이 없다.
    const full = !!(payload && payload.full && Array.isArray(payload.bcIds) && payload.bcIds.length)
    if (!payload || (!full && (!payload.bcId || !payload.targetNodeId))) return
    requestId.value += 1
    pendingRequest.value = { ...payload, _reqId: requestId.value }
  }

  function consume() {
    pendingRequest.value = null
  }

  return { pendingRequest, requestId, request, consume }
})
