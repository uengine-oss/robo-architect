import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { createLogger } from '@/app/logging/logger'
import { emitDataChanged } from '@/app/lifecycle/dataLifecycle'

/**
 * Requirements tab store (026 — requirements-tab).
 * Holds the Epic→Feature→UserStory tree, the selected story's design trace,
 * and background impact reports.
 */
export const useRequirementsStore = defineStore('requirements', () => {
  const log = createLogger({ scope: 'RequirementsStore' })

  const tree = ref({ epics: [], unassigned: [] })
  const loading = ref(false)
  const error = ref(null)

  const selectedUserStoryId = ref(null)
  const selectedUserStory = ref(null)

  const designTrace = ref({ nodes: [], relationships: [], empty: false })
  const designTraceLoading = ref(false)

  const impactReport = ref(null)
  let impactPollTimer = null

  const hasImpactFindings = computed(
    () => !!impactReport.value && (impactReport.value.findings || []).length > 0,
  )

  async function fetchTree() {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/requirements/tree')
      if (!res.ok) throw new Error(`tree fetch failed: ${res.status}`)
      tree.value = await res.json()
    } catch (e) {
      error.value = String(e)
      log.error('fetch_tree_failed', 'Requirements tree fetch failed', { error: String(e) })
    } finally {
      loading.value = false
    }
  }

  /** Walk the tree to find a user story DTO by id. */
  function findUserStory(usId) {
    for (const epic of tree.value.epics || []) {
      const features = [...(epic.features || [])]
      if (epic.unassignedFeature) features.push(epic.unassignedFeature)
      for (const f of features) {
        const hit = (f.userStories || []).find((us) => us.id === usId)
        if (hit) return hit
      }
    }
    return (tree.value.unassigned || []).find((us) => us.id === usId) || null
  }

  async function selectUserStory(usId) {
    selectedUserStoryId.value = usId
    selectedUserStory.value = findUserStory(usId)
    await fetchDesignTrace(usId)
  }

  async function fetchDesignTrace(usId) {
    designTraceLoading.value = true
    try {
      const res = await fetch(`/api/requirements/user-story/${usId}/design-trace`)
      if (!res.ok) throw new Error(`design-trace failed: ${res.status}`)
      designTrace.value = await res.json()
    } catch (e) {
      designTrace.value = { nodes: [], relationships: [], empty: true }
      log.error('fetch_trace_failed', 'Design trace fetch failed', { error: String(e) })
    } finally {
      designTraceLoading.value = false
    }
  }

  async function proposeUserStory(text, targetBoundedContextId = null) {
    const res = await fetch('/api/requirements/user-story/propose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, targetBoundedContextId }),
    })
    if (!res.ok) throw new Error(`propose failed: ${res.status}`)
    return res.json()
  }

  async function confirmUserStory(payload) {
    const res = await fetch('/api/requirements/user-story/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) throw new Error(`confirm failed: ${res.status}`)
    const data = await res.json()
    await fetchTree()
    if (data.impactReportId) watchImpactReport(data.impactReportId)
    return data
  }

  async function createFeature(boundedContextId, name, description = null) {
    const res = await fetch('/api/requirements/feature', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ boundedContextId, name, description }),
    })
    if (!res.ok) throw new Error(`create feature failed: ${res.status}`)
    await fetchTree()
    return res.json()
  }

  async function deleteFeature(featureId, userStoryDisposition = 'unassign') {
    const res = await fetch('/api/requirements/feature', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ featureId, userStoryDisposition }),
    })
    if (!res.ok) throw new Error(`delete feature failed: ${res.status}`)
    const data = await res.json()
    await fetchTree()
    if (data.impactReportId) watchImpactReport(data.impactReportId)
    return data
  }

  async function moveUserStory(userStoryId, targetFeatureId) {
    const res = await fetch('/api/requirements/user-story/move', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userStoryId, targetFeatureId }),
    })
    if (!res.ok) throw new Error(`move failed: ${res.status}`)
    const data = await res.json()
    await fetchTree()
    if (data.impactReportId) watchImpactReport(data.impactReportId)
    return data
  }

  async function deleteUserStory(userStoryId) {
    const res = await fetch('/api/requirements/user-story', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userStoryId }),
    })
    if (!res.ok) throw new Error(`delete user story failed: ${res.status}`)
    const data = await res.json()
    if (selectedUserStoryId.value === userStoryId) {
      selectedUserStoryId.value = null
      selectedUserStory.value = null
      designTrace.value = { nodes: [], relationships: [], empty: false }
    }
    await fetchTree()
    if (data.impactReportId) watchImpactReport(data.impactReportId)
    return data
  }

  /** Poll a background impact report until it reaches a terminal state. */
  function watchImpactReport(reportId) {
    if (impactPollTimer) clearInterval(impactPollTimer)
    impactReport.value = { id: reportId, status: 'running', findings: [] }
    let ticks = 0
    impactPollTimer = setInterval(async () => {
      ticks += 1
      try {
        const res = await fetch(`/api/requirements/impact-report/${reportId}`)
        if (res.ok) {
          const report = await res.json()
          impactReport.value = report
          if (report.status !== 'running' || ticks > 60) {
            clearInterval(impactPollTimer)
            impactPollTimer = null
          }
        }
      } catch {
        /* keep polling; advisory only */
      }
    }, 1000)
  }

  function dismissImpactReport() {
    impactReport.value = null
  }

  /** Explicit data deletion (US6) — calls the existing clear-all endpoint. */
  async function clearAllData() {
    const res = await fetch('/api/ingest/clear-all', { method: 'DELETE' })
    if (!res.ok) throw new Error(`clear-all failed: ${res.status}`)
    tree.value = { epics: [], unassigned: [] }
    selectedUserStoryId.value = null
    selectedUserStory.value = null
    designTrace.value = { nodes: [], relationships: [], empty: false }
    impactReport.value = null
    emitDataChanged('cleared')  // 다른 탭 네비게이터/캔버스도 비우기
    return res.json()
  }

  return {
    tree,
    loading,
    error,
    selectedUserStoryId,
    selectedUserStory,
    designTrace,
    designTraceLoading,
    impactReport,
    hasImpactFindings,
    fetchTree,
    selectUserStory,
    fetchDesignTrace,
    proposeUserStory,
    confirmUserStory,
    createFeature,
    deleteFeature,
    moveUserStory,
    deleteUserStory,
    watchImpactReport,
    dismissImpactReport,
    clearAllData,
  }
})
