import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
// 040 — 도메인 중립 미리보기 세션(앱 셸). 라이브↔미리보기 fetch 분기 + 편집 → 제안 diff 반영.
import { previewUrl, isPreviewFor, usePreviewSession } from '@/app/previewSession'

export const useAggregateViewerStore = defineStore('aggregateViewer', () => {
  // Data from API
  const boundedContexts = ref([])
  const loading = ref(false)
  const error = ref(null)

  // 040 — 미리보기 진입 시 라이브 상태 스냅샷(닫을 때 복원, US2 격리).
  const _liveSnapshot = ref(null)

  // Selected BC IDs (for filtering)
  const selectedBcIds = ref(new Set())

  // Aggregate-level visibility filter: ids of aggregates currently shown on
  // the canvas. Lets the viewer show a single aggregate, not the whole BC.
  const visibleAggregateIds = ref(new Set())

  // One-shot cross-tab focus intent: { aggregateId, bcId } | null
  const pendingFocus = ref(null)

  // Selected node for editing
  const selectedNodeId = ref(null)
  const selectedNodeType = ref(null) // 'aggregate' | 'enum' | 'valueObject'

  // Load a BC's full tree into state without changing aggregate visibility.
  // 040 — 미리보기 활성 시 fetch base 를 Proposal preview 로 분기(오버레이 투영).
  async function loadBcTree(bcId) {
    const response = await fetch(previewUrl('data', `/api/contexts/${bcId}/full-tree`))
    if (!response.ok) {
      throw new Error(`Failed to fetch aggregates: ${response.statusText}`)
    }
    const data = await response.json()

    const bc = {
      id: data.id,
      name: data.name,
      displayName: data.displayName || data.name,
      description: data.description,
      aggregates: (data.aggregates || []).map(agg => ({
        id: agg.id,
        name: agg.name,
        displayName: agg.displayName || agg.name,
        rootEntity: agg.rootEntity,
        invariants: agg.invariants || [],
        enumerations: agg.enumerations || [],
        valueObjects: agg.valueObjects || [],
        properties: agg.properties || [],
        // 040 — Proposal 미리보기 오버레이 출처/배지(신규/수정/충돌)를 노드까지 전달.
        source: agg.source,
        badge: agg.badge,
      }))
    }

    const existingIndex = boundedContexts.value.findIndex(b => b.id === bcId)
    if (existingIndex >= 0) {
      boundedContexts.value[existingIndex] = bc
    } else {
      boundedContexts.value.push(bc)
    }
    selectedBcIds.value.add(bcId)
    return bc
  }

  // Resolve the owning BoundedContext id for an aggregate via the graph.
  async function resolveBcId(aggregateId) {
    const response = await fetch(previewUrl('data', `/api/graph/expand-with-bc/${aggregateId}`))
    if (!response.ok) {
      throw new Error(`Failed to resolve bounded context: ${response.statusText}`)
    }
    const data = await response.json()
    const nodes = data.nodes || []
    const bcNode = nodes.find(n => n.type === 'BoundedContext')
    const aggNode = nodes.find(n => n.id === aggregateId)
    return bcNode?.id || aggNode?.bcId || null
  }

  // Fetch a whole BC and make all of its aggregates visible.
  async function fetchAggregatesForBC(bcId) {
    loading.value = true
    error.value = null
    try {
      const bc = await loadBcTree(bcId)
      bc.aggregates.forEach(agg => {
        if (agg.id) visibleAggregateIds.value.add(agg.id)
      })
      visibleAggregateIds.value = new Set(visibleAggregateIds.value)
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch aggregates:', err)
    } finally {
      loading.value = false
    }
  }

  // Fetch a single aggregate and make only it visible (additive, de-duplicated).
  async function fetchAggregate(aggregateId, bcId = null) {
    if (!aggregateId) return
    loading.value = true
    error.value = null
    try {
      let resolvedBcId = bcId
      if (!resolvedBcId) {
        resolvedBcId = await resolveBcId(aggregateId)
      }
      if (!resolvedBcId) {
        throw new Error('Could not determine the bounded context for this aggregate')
      }

      const alreadyLoaded = boundedContexts.value.find(b => b.id === resolvedBcId)
      const bc = alreadyLoaded || await loadBcTree(resolvedBcId)

      const found = bc.aggregates?.some(a => a.id === aggregateId)
      if (!found) {
        throw new Error('Aggregate not found in its bounded context')
      }

      visibleAggregateIds.value.add(aggregateId)
      visibleAggregateIds.value = new Set(visibleAggregateIds.value)
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch aggregate:', err)
    } finally {
      loading.value = false
    }
  }

  // Set / consume a one-shot cross-tab focus target.
  function focusAggregate(aggregateId, bcId = null) {
    if (!aggregateId) return
    pendingFocus.value = { aggregateId, bcId: bcId || null }
  }

  function consumeFocus() {
    const target = pendingFocus.value
    pendingFocus.value = null
    return target
  }

  // Remove BC from viewer
  function removeBC(bcId) {
    selectedBcIds.value.delete(bcId)
    boundedContexts.value = boundedContexts.value.filter(bc => bc.id !== bcId)
  }

  // Clear all selected BCs
  function clearAllBCs() {
    selectedBcIds.value.clear()
    visibleAggregateIds.value = new Set()
    pendingFocus.value = null
    boundedContexts.value = []
  }

  // 040 — 미리보기 진입: 라이브 상태를 스냅샷 후 비워, 이후 fetch 가 preview 소스에서
  // 신선하게 적재되도록 한다(이미 적재된 라이브 BC 재사용 방지, US2 격리).
  function beginPreview() {
    _liveSnapshot.value = {
      boundedContexts: boundedContexts.value,
      selectedBcIds: new Set(selectedBcIds.value),
      visibleAggregateIds: new Set(visibleAggregateIds.value),
    }
    boundedContexts.value = []
    selectedBcIds.value = new Set()
    visibleAggregateIds.value = new Set()
    pendingFocus.value = null
  }

  // 040 — 미리보기 종료: 라이브 상태 복원. 미리보기 잔존물 0(US2/SC-003).
  function endPreview() {
    const snap = _liveSnapshot.value
    _liveSnapshot.value = null
    if (snap) {
      boundedContexts.value = snap.boundedContexts
      selectedBcIds.value = snap.selectedBcIds
      visibleAggregateIds.value = snap.visibleAggregateIds
    } else {
      clearAllBCs()
    }
    pendingFocus.value = null
  }

  // Get filtered bounded contexts (selected BCs, aggregates gated by visibility)
  const filteredBoundedContexts = computed(() => {
    if (selectedBcIds.value.size === 0) {
      return []
    }
    return boundedContexts.value
      .filter(bc => selectedBcIds.value.has(bc.id))
      .map(bc => ({
        ...bc,
        aggregates: (bc.aggregates || []).filter(agg => visibleAggregateIds.value.has(agg.id))
      }))
      .filter(bc => bc.aggregates.length > 0)
  })

  // Fetch all aggregates with VO/Enum/Properties (deprecated - use fetchAggregatesForBC instead)
  async function fetchAllAggregates() {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/contexts/aggregates/viewer')
      if (!response.ok) {
        throw new Error(`Failed to fetch aggregates: ${response.statusText}`)
      }
      const data = await response.json()
      boundedContexts.value = data.boundedContexts || []
      // Add all BC IDs to selected
      data.boundedContexts?.forEach(bc => {
        if (bc.id) selectedBcIds.value.add(bc.id)
      })
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch aggregates:', err)
    } finally {
      loading.value = false
    }
  }

  // 040 — 미리보기 편집을 Proposal.tacticalDiff 에 반영(라이브 그래프 무변경).
  // 갱신된 미리보기 트리를 받아 로컬 상태를 그 트리로 교체 → 즉시 재렌더.
  async function _savePreviewAggregateEdit(aggregateId, patch) {
    const ps = usePreviewSession()
    const res = await fetch(`/api/proposals/${ps.proposalId}/preview/aggregate/${aggregateId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bcId: ps.bcId, ...patch }),
    })
    if (!res.ok) throw new Error(`제안 diff 반영 실패: ${res.status}`)
    const tree = await res.json()
    applyPreviewTree(tree)
    return tree
  }

  // 040 — preview/edit 응답(갱신된 full-tree)을 로컬 상태에 반영(즉시 재렌더).
  // Chat 편집 경로(modelModifier)도 robo:preview-updated 이벤트로 이 메서드를 호출한다.
  function applyPreviewTree(tree) {
    if (!tree || !tree.id) return
    const mapped = {
      id: tree.id, name: tree.name, displayName: tree.displayName || tree.name, description: tree.description,
      aggregates: (tree.aggregates || []).map(agg => ({
        id: agg.id, name: agg.name, displayName: agg.displayName || agg.name, rootEntity: agg.rootEntity,
        invariants: agg.invariants || [], enumerations: agg.enumerations || [],
        valueObjects: agg.valueObjects || [], properties: agg.properties || [],
        source: agg.source, badge: agg.badge,
      })),
    }
    const i = boundedContexts.value.findIndex(b => b.id === tree.id)
    if (i >= 0) {
      // BC 가 이미 로드된 상태에서의 미리보기 편집 갱신(단일 Aggregate 편집 후).
      // 트리는 BC 전체를 담고 있으므로 전부 visible 로 만들면 편집하지 않은 형제
      // Aggregate 까지 갑자기 로드된다. 기존에 보이던 집합을 그대로 유지하고,
      // 트리에서 사라진 id 만 정리한다.
      boundedContexts.value[i] = mapped
      const present = new Set(mapped.aggregates.map(a => a.id).filter(Boolean))
      visibleAggregateIds.value = new Set(
        [...visibleAggregateIds.value].filter(id => present.has(id)),
      )
    } else {
      // BC 최초 적재(편집 외 경로): 해당 BC 의 Aggregate 를 노출.
      boundedContexts.value.push(mapped)
      selectedBcIds.value.add(tree.id)
      mapped.aggregates.forEach(a => a.id && visibleAggregateIds.value.add(a.id))
      visibleAggregateIds.value = new Set(visibleAggregateIds.value)
    }

    // 040 — 모든 미리보기 편집(Inspector 직접·Chat)은 이 메서드를 거치며, 그 시점에
    // Proposal.tacticalDiff 가 이미 갱신돼 있다. Proposals 탭(Impact Map·Diff)이 항목을
    // 다시 클릭하지 않아도 최신 상태를 보이도록 앱 레벨로 알린다(App.vue 가 currentProposal 재적재).
    const ps = usePreviewSession()
    if (ps.proposalId) {
      window.dispatchEvent(new CustomEvent('robo:proposal-diff-changed', {
        detail: { proposalId: ps.proposalId },
      }))
    }
  }

  // Update aggregate enumerations and value objects
  async function updateAggregateEnumVo(aggregateId, enumerations, valueObjects) {
    // 040 — 미리보기 중에는 라이브가 아니라 제안 diff 에 반영.
    if (isPreviewFor('data')) {
      return _savePreviewAggregateEdit(aggregateId, { enumerations: enumerations || [], valueObjects: valueObjects || [] })
    }
    try {
      const response = await fetch(`/api/contexts/aggregates/${aggregateId}/enumerations-valueobjects`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          enumerations: enumerations || [],
          value_objects: valueObjects || [],
        }),
      })
      if (!response.ok) {
        throw new Error(`Failed to update aggregate: ${response.statusText}`)
      }
      const updated = await response.json()
      
      // Update local state
      for (const bc of boundedContexts.value) {
        const agg = bc.aggregates?.find(a => a.id === aggregateId)
        if (agg) {
          agg.enumerations = updated.enumerations || []
          agg.valueObjects = updated.valueObjects || []
          break
        }
      }
      
      return updated
    } catch (err) {
      console.error('Failed to update aggregate:', err)
      throw err
    }
  }

  // Update aggregate properties
  async function updateAggregateProperties(aggregateId, properties) {
    // 040 — 미리보기 중에는 라이브가 아니라 제안 diff 에 반영.
    if (isPreviewFor('data')) {
      return _savePreviewAggregateEdit(aggregateId, { properties: properties || [] })
    }
    try {
      const response = await fetch(`/api/contexts/aggregates/${aggregateId}/properties`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          properties: properties || [],
        }),
      })
      if (!response.ok) {
        throw new Error(`Failed to update aggregate properties: ${response.statusText}`)
      }
      const updated = await response.json()
      
      // Update local state
      for (const bc of boundedContexts.value) {
        const agg = bc.aggregates?.find(a => a.id === aggregateId)
        if (agg) {
          agg.properties = updated.properties || []
          break
        }
      }
      
      return updated
    } catch (err) {
      console.error('Failed to update aggregate properties:', err)
      throw err
    }
  }

  // 043-fix — Aggregate 기본 속성(이름/표시이름/설명/Root Entity) 수정.
  // 미리보기 중에는 제안 diff(reconcile_aggregate_edit)로, 아니면 라이브 그래프(chat/confirm)로.
  async function updateAggregateBasic(aggregateId, basic) {
    // 변경된 필드만 전송한다(불변 필드를 다시 보내면 불필요한 nodeTitle 재기록이 일어난다).
    const cur = getAggregateById(aggregateId)?.aggregate || {}
    const patch = {}
    for (const k of ['name', 'displayName', 'description', 'rootEntity']) {
      if (basic[k] !== undefined && basic[k] !== null && String(basic[k]) !== String(cur[k] ?? '')) {
        patch[k] = basic[k]
      }
    }
    if (!Object.keys(patch).length) return
    if (isPreviewFor('data')) {
      return _savePreviewAggregateEdit(aggregateId, patch)
    }
    // 라이브: 이름은 rename, 나머지는 update draft 로 model_modifier 에 반영.
    const drafts = []
    if (patch.name && patch.name !== cur.name) {
      drafts.push({ changeId: `rename-${aggregateId}-${Date.now()}`, action: 'rename',
        targetId: aggregateId, targetName: patch.name, targetType: 'Aggregate', updates: {} })
    }
    const updates = {}
    for (const k of ['displayName', 'description', 'rootEntity']) {
      if (patch[k] !== undefined && String(patch[k] ?? '') !== String(cur[k] ?? '')) updates[k] = patch[k]
    }
    if (Object.keys(updates).length) {
      drafts.push({ changeId: `update-${aggregateId}-${Date.now()}`, action: 'update',
        targetId: aggregateId, targetName: patch.name || cur.name || '', targetType: 'Aggregate', updates })
    }
    if (!drafts.length) return
    const response = await fetch('/api/chat/confirm', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drafts, approvedChangeIds: drafts.map(d => d.changeId) }),
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data?.detail || `Failed to update aggregate: ${response.status}`)
    }
    await fetchAllAggregates()
  }

  // Get aggregate by ID
  function getAggregateById(aggregateId) {
    for (const bc of boundedContexts.value) {
      const agg = bc.aggregates?.find(a => a.id === aggregateId)
      if (agg) {
        return { aggregate: agg, boundedContext: bc }
      }
    }
    return null
  }

  // Select node for editing
  function selectNode(nodeId, nodeType) {
    selectedNodeId.value = nodeId
    selectedNodeType.value = nodeType
  }

  function clearSelection() {
    selectedNodeId.value = null
    selectedNodeType.value = null
  }

  // Computed: total aggregates count
  const totalAggregates = computed(() => {
    return boundedContexts.value.reduce((sum, bc) => sum + (bc.aggregates?.length || 0), 0)
  })

  // Computed: total enumerations count
  const totalEnumerations = computed(() => {
    return boundedContexts.value.reduce((sum, bc) => {
      const bcEnums = bc.aggregates?.reduce((aggSum, agg) => {
        return aggSum + (agg.enumerations?.length || 0)
      }, 0) || 0
      return sum + bcEnums
    }, 0)
  })

  // Computed: total value objects count
  const totalValueObjects = computed(() => {
    return boundedContexts.value.reduce((sum, bc) => {
      const bcVos = bc.aggregates?.reduce((aggSum, agg) => {
        return aggSum + (agg.valueObjects?.length || 0)
      }, 0) || 0
      return sum + bcVos
    }, 0)
  })

  return {
    boundedContexts,
    loading,
    error,
    selectedBcIds,
    visibleAggregateIds,
    pendingFocus,
    selectedNodeId,
    selectedNodeType,
    filteredBoundedContexts,
    totalAggregates,
    totalEnumerations,
    totalValueObjects,
    fetchAllAggregates,
    fetchAggregatesForBC,
    fetchAggregate,
    focusAggregate,
    consumeFocus,
    removeBC,
    clearAllBCs,
    beginPreview,
    endPreview,
    applyPreviewTree,
    updateAggregateEnumVo,
    updateAggregateProperties,
    updateAggregateBasic,
    getAggregateById,
    selectNode,
    clearSelection,
  }
})
