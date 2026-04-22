import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useBpmnStore = defineStore('bpmn', () => {
  const loading = ref(false)
  const error = ref(null)

  // 프로세스 흐름 목록 (Navigator용)
  const processFlows = ref([])

  // 현재 캔버스에 렌더링된 프로세스 흐름들
  const renderedFlows = ref([]) // [{id, bpmnXml, structured, startCommand, ...}]

  // 선택된 프로세스 흐름 ID
  const selectedFlowId = ref(null)

  // 현재 활성 BPMN XML (Viewer에 표시할 것)
  const activeBpmnXml = ref(null)
  const activeStructured = ref(null)

  // Inspector: 선택된 노드 데이터
  const selectedNodeData = ref(null)
  const selectedNodeUi = ref(null)

  const renderedFlowIds = computed(() => new Set(renderedFlows.value.map(f => f.id)))

  // 프로세스 흐름 목록 조회
  async function fetchProcessFlows() {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/graph/bpmn/process-flows')
      if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`)
      const data = await res.json()
      processFlows.value = data.flows || []
    } catch (e) {
      error.value = e.message
      console.error('Failed to fetch BPMN process flows:', e)
    } finally {
      loading.value = false
    }
  }

  // 특정 프로세스 흐름 데이터 가져오기 + 캔버스에 추가
  async function addFlow(startCommandId) {
    if (renderedFlowIds.value.has(startCommandId)) return

    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/graph/bpmn/process-flow/${startCommandId}`)
      if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`)
      const data = await res.json()

      const flowData = {
        id: startCommandId,
        bpmnXml: data.bpmnXml,
        structured: data.structured,
        startCommand: data.startCommand,
        nodes: data.nodes,
        relations: data.relations,
        uiMap: data.uiMap || {},
      }

      renderedFlows.value.push(flowData)
      selectedFlowId.value = startCommandId
      activeBpmnXml.value = data.bpmnXml
      activeStructured.value = data.structured
    } catch (e) {
      error.value = e.message
      console.error('Failed to fetch BPMN flow:', e)
    } finally {
      loading.value = false
    }
  }

  // 프로세스 흐름 선택 (이미 렌더링된 것 중에서)
  function selectFlow(flowId) {
    const flow = renderedFlows.value.find(f => f.id === flowId)
    if (flow) {
      selectedFlowId.value = flowId
      activeBpmnXml.value = flow.bpmnXml
      activeStructured.value = flow.structured
    }
  }

  // 프로세스 흐름 제거
  function removeFlow(flowId) {
    renderedFlows.value = renderedFlows.value.filter(f => f.id !== flowId)
    if (selectedFlowId.value === flowId) {
      const next = renderedFlows.value[0]
      if (next) {
        selectFlow(next.id)
      } else {
        selectedFlowId.value = null
        activeBpmnXml.value = null
        activeStructured.value = null
      }
    }
  }

  // BPMN 요소 ID로부터 노드 데이터 찾기
  function findNodeByBpmnElementId(bpmnElementId) {
    const flow = renderedFlows.value.find(f => f.id === selectedFlowId.value)
    if (!flow || !flow.nodes) return null

    // Task_{safe_id} → Command, IntEvent_{safe_id} → Event
    let prefix = null
    let safeSuffix = null

    if (bpmnElementId.startsWith('Task_')) {
      prefix = 'Command'
      safeSuffix = bpmnElementId.slice('Task_'.length)
    } else if (bpmnElementId.startsWith('IntEvent_')) {
      prefix = 'Event'
      safeSuffix = bpmnElementId.slice('IntEvent_'.length)
    } else {
      return null
    }

    // 노드의 id를 safe_id로 변환하여 비교
    function toSafeId(id) {
      return id.replace(/-/g, '_').replace(/\./g, '_').replace(/@/g, '_at_').replace(/ /g, '_')
    }

    const node = flow.nodes.find(n => {
      if (n.label !== prefix) return false
      return toSafeId(n.id) === safeSuffix
    })

    return node || null
  }

  // 노드 선택 (더블클릭 시)
  function selectNodeForInspector(bpmnElementId) {
    const node = findNodeByBpmnElementId(bpmnElementId)
    selectedNodeData.value = node
    selectedNodeUi.value = null

    if (!node) {
      console.warn('[BPMN Inspector] No node found for BPMN element:', bpmnElementId)
      return
    }

    // Command인 경우 uiMap에서 UI wireframe 조회
    if (node.label === 'Command') {
      const flow = renderedFlows.value.find(f => f.id === selectedFlowId.value)
      const ui = flow?.uiMap?.[node.id]
      if (ui) {
        selectedNodeUi.value = ui
      } else {
        console.info('[BPMN Inspector] No UI wireframe for command:', node.id, 'uiMap keys:', Object.keys(flow?.uiMap || {}))
      }
    }
  }

  // Inspector 닫기
  function clearInspectorSelection() {
    selectedNodeData.value = null
    selectedNodeUi.value = null
  }

  // ---------------------------------------------------------------------------
  // Hybrid ingestion state (Document + Code → BPM-first)
  // DB is the source of truth. localStorage only tracks the active session id
  // so a page refresh can re-fetch everything from /session/{sid}/snapshot.
  // ---------------------------------------------------------------------------
  const HYBRID_SID_KEY = 'hybrid.session_id'
  const LEGACY_LS_KEYS = ['hybrid.bpmn.v1']  // cleaned up on first load

  function _loadSessionId() {
    try { return localStorage.getItem(HYBRID_SID_KEY) || null } catch { return null }
  }
  function _saveSessionId(sid) {
    try {
      if (sid) localStorage.setItem(HYBRID_SID_KEY, sid)
      else localStorage.removeItem(HYBRID_SID_KEY)
      for (const k of LEGACY_LS_KEYS) localStorage.removeItem(k)
    } catch { /* quota or disabled — fine */ }
  }

  const hybridActive = ref(false)
  const hybridProcesses = ref([])  // [{id, name, domain_keywords, task_ids, actor_ids, source_pdf_name, bpmn_xml}]
  // Which process's BPMN XML is currently shown on the canvas (null = none rendered).
  // Multi-process documents don't auto-render — user drags/double-clicks a process row.
  const activeHybridProcessId = ref(null)
  const hybridActors = ref([])
  const hybridTasks = ref([])
  const hybridBpmnXml = ref(null)
  const hybridRules = ref([])
  const hybridGlossary = ref([])
  const hybridReviewQueue = ref([])
  // Rules in this session with zero REALIZED_BY edges anywhere. Surfaced
  // alongside review queue in the unified "미매핑 / Review" pool.
  const hybridUnassignedRuleIds = ref([])
  const hybridSessionId = ref(_loadSessionId())
  const reviewModalItem = ref(null)
  // BC name for the "Rules by Context" modal — null means modal is closed.
  const bcRulesModalCluster = ref(null)
  const selectedHybridTaskId = ref(null)
  const isHybridRehydrating = ref(false)
  // Currently running SSE re-retrieval (🔄 재탐색). Navigator reads this to
  // show a spinner/badge on the task being explored. null = idle.
  const activeExploringTaskId = ref(null)
  function setActiveExploringTaskId(taskId) {
    activeExploringTaskId.value = taskId || null
  }
  function clearActiveExploringTaskId() {
    activeExploringTaskId.value = null
  }

  // §8.7 — cross-process arbitration highlight. During Step 4 the Navigator
  // wraps competing tasks in a purple "under review" wash + shows a banner
  // ("중복 rule 우선순위 검증 중"). Cleared when HybridArbitrationEnd arrives.
  const arbitratingTaskIds = ref([])       // array for reactivity; checked via Array.includes
  const isArbitrating = ref(false)
  function setArbitratingTaskIds(ids) {
    arbitratingTaskIds.value = Array.isArray(ids) ? [...ids] : []
    isArbitrating.value = arbitratingTaskIds.value.length > 0
  }
  function clearArbitrating() {
    arbitratingTaskIds.value = []
    isArbitrating.value = false
  }

  /** Remove a rule from a task's `rules` array when arbitration rejects it.
   *  Used on HybridArbitrationDecision losing_task_ids so the Inspector/Navigator
   *  drop the invalidated mapping without waiting for full rehydrate. */
  function removeRuleFromTask(taskId, ruleId) {
    const idx = hybridTasks.value.findIndex(t => t.id === taskId)
    if (idx < 0) return
    const t = hybridTasks.value[idx]
    const nextRules = (t.rules || []).filter(r => r.id !== ruleId)
    if (nextRules.length === (t.rules || []).length) return
    const nextTask = { ...t, rules: nextRules }
    hybridTasks.value = [
      ...hybridTasks.value.slice(0, idx),
      nextTask,
      ...hybridTasks.value.slice(idx + 1),
    ]
  }

  // --- Agent Reasoning SSE lifecycle (§2.C) ---
  // Managed here (not inside HybridTaskInspector) so closing the panel doesn't
  // abort a running re-retrieval. Backend's `asyncio.create_task(runner_task)`
  // already survives request disconnect; the frontend just needs to keep the
  // EventSource listener alive across panel open/close to see progress.
  const agentEvents = ref([])
  const agentState = ref('idle')      // 'idle' | 'running' | 'done' | 'cached' | 'error'
  const agentError = ref(null)
  const agentTaskId = ref(null)       // which task the stream is for
  let _agentSource = null

  function closeAgentStream() {
    if (_agentSource) {
      try { _agentSource.close() } catch {}
      _agentSource = null
    }
    clearActiveExploringTaskId()
  }

  function startAgentStream(sessionId, taskId) {
    if (!sessionId || !taskId) return
    closeAgentStream()
    agentEvents.value = []
    agentError.value = null
    agentState.value = 'running'
    agentTaskId.value = taskId
    setActiveExploringTaskId(taskId)
    _agentSource = new EventSource(`/api/ingest/hybrid/task/${sessionId}/${taskId}/retrieve`)
    _agentSource.addEventListener('agent', (e) => {
      try {
        const payload = JSON.parse(e.data)
        agentEvents.value = [...agentEvents.value, payload]
        if (payload.type === 'AgentDone') agentState.value = 'done'
        if (payload.type === 'AgentPersisted') {
          // Refresh snapshot so the newly saved mappings appear in the UI.
          rehydrateHybrid().catch(() => {})
          clearActiveExploringTaskId()
        }
        if (payload.type === 'AgentError') {
          agentState.value = 'error'
          agentError.value = payload.error
          clearActiveExploringTaskId()
        }
      } catch { /* ignore malformed */ }
    })
    _agentSource.addEventListener('error', () => {
      if (agentState.value === 'running') agentState.value = 'error'
      closeAgentStream()
    })
  }

  function markAgentCached(taskId) {
    // Inspector opens a task that already has cached Phase 3 results —
    // display state without starting a stream.
    agentTaskId.value = taskId
    agentState.value = 'cached'
    agentEvents.value = []
    agentError.value = null
  }

  const selectedHybridTask = computed(() =>
    hybridTasks.value.find(t => t.id === selectedHybridTaskId.value) || null
  )
  function selectHybridTask(taskId) {
    selectedHybridTaskId.value = taskId
  }
  function clearHybridTaskSelection() {
    selectedHybridTaskId.value = null
  }

  function beginHybrid() {
    hybridActive.value = true
    hybridProcesses.value = []
    activeHybridProcessId.value = null
    hybridActors.value = []
    hybridTasks.value = []
    hybridBpmnXml.value = null
    hybridRules.value = []
    hybridGlossary.value = []
    hybridReviewQueue.value = []
    hybridUnassignedRuleIds.value = []
    hybridSessionId.value = null
    reviewModalItem.value = null
    renderedFlows.value = []
    selectedFlowId.value = null
    activeBpmnXml.value = null
    activeStructured.value = null
    _saveSessionId(null)
  }

  /** Switch the canvas to a specific process's XML. Called on drag/dblclick. */
  function selectHybridProcess(processId) {
    const p = hybridProcesses.value.find(x => x.id === processId)
    if (!p) return
    activeHybridProcessId.value = processId
    if (p.bpmn_xml) {
      activeBpmnXml.value = p.bpmn_xml
      hybridBpmnXml.value = p.bpmn_xml
    }
  }

  /** Clear canvas when no process is picked. */
  function clearHybridProcessSelection() {
    activeHybridProcessId.value = null
    activeBpmnXml.value = null
  }

  /** Fetch the full hybrid snapshot from Neo4j and populate the store. */
  async function rehydrateHybrid(sid = hybridSessionId.value) {
    if (!sid) return { ok: false, reason: 'no-session' }
    isHybridRehydrating.value = true
    try {
      const res = await fetch(`/api/ingest/hybrid/session/${sid}/snapshot`)
      if (!res.ok) return { ok: false, reason: `http-${res.status}` }
      const data = await res.json()
      hybridProcesses.value = data.processes || []
      hybridActors.value = data.actors || []
      hybridTasks.value = data.tasks || []
      hybridRules.value = data.rules || []
      hybridGlossary.value = data.glossary || []
      hybridReviewQueue.value = data.review_queue || []
      hybridUnassignedRuleIds.value = data.unassigned_rule_ids || []
      hybridBpmnXml.value = data.bpmn_xml || null
      // Cold-load canvas policy (see 개선&재구조화.md §A.0):
      //  · Multi-process session → canvas starts EMPTY; user picks a process.
      //  · Single-process session → auto-render that one process's own XML
      //    (not the merged one, so lanes reflect per-process actor set).
      //
      // Mid-session rehydrate (e.g. triggered by AgentPersisted after 🔄
      // re-retrieval) must NOT wipe the currently rendered process — otherwise
      // the user loses their view every time a task gets new mappings.
      const procs = data.processes || []
      const prevActiveId = activeHybridProcessId.value
      const prevActive = prevActiveId
        ? procs.find(p => p.id === prevActiveId)
        : null
      if (prevActive && prevActive.bpmn_xml) {
        // Preserve user's current process selection across rehydrate.
        activeHybridProcessId.value = prevActive.id
        activeBpmnXml.value = prevActive.bpmn_xml
      } else if (procs.length === 1 && procs[0].bpmn_xml) {
        activeHybridProcessId.value = procs[0].id
        activeBpmnXml.value = procs[0].bpmn_xml
      } else {
        activeHybridProcessId.value = null
        activeBpmnXml.value = null
      }
      hybridSessionId.value = sid
      _saveSessionId(sid)
      return { ok: true }
    } catch (e) {
      return { ok: false, reason: String(e) }
    } finally {
      isHybridRehydrating.value = false
    }
  }

  function addHybridRule(rule) {
    if (!rule) return
    const idx = hybridRules.value.findIndex(r => r.id === rule.id)
    if (idx === -1) hybridRules.value = [...hybridRules.value, rule]
    else hybridRules.value = hybridRules.value.map((r, i) => i === idx ? rule : r)
  }

  function setHybridRules(rules) {
    if (!Array.isArray(rules)) return
    hybridRules.value = rules
  }

  function setHybridGlossary(terms) {
    if (!Array.isArray(terms)) return
    hybridGlossary.value = terms
  }

  function setHybridReviewQueue(items) {
    if (!Array.isArray(items)) return
    hybridReviewQueue.value = items
  }

  function setHybridSessionId(sid) {
    hybridSessionId.value = sid || null
    _saveSessionId(sid || null)
  }

  function openBcRulesModal(cluster) {
    bcRulesModalCluster.value = cluster || null
  }
  function closeBcRulesModal() {
    bcRulesModalCluster.value = null
  }

  function openReviewModal(item) {
    reviewModalItem.value = item || null
  }
  function closeReviewModal() {
    reviewModalItem.value = null
  }

  async function acceptReview(item) {
    if (!item || !hybridSessionId.value) return { ok: false }
    const url = `/api/ingest/hybrid/review/${hybridSessionId.value}/${item.task_id}/${item.rule_id}/accept`
    const res = await fetch(url, { method: 'POST' })
    if (!res.ok) return { ok: false, error: await res.text() }
    // Local update: remove from review queue + add rule to the task
    hybridReviewQueue.value = hybridReviewQueue.value.filter(
      x => !(x.task_id === item.task_id && x.rule_id === item.rule_id)
    )
    const rule = hybridRules.value.find(r => r.id === item.rule_id)
    if (rule) {
      const idx = hybridTasks.value.findIndex(t => t.id === item.task_id)
      if (idx !== -1) {
        const t = hybridTasks.value[idx]
        const rules = Array.isArray(t.rules) ? [...t.rules] : []
        if (!rules.some(r => r.id === rule.id)) {
          rules.push({ ...rule, confidence: item.score, match_method: item.method, reviewed: true })
        }
        hybridTasks.value = [
          ...hybridTasks.value.slice(0, idx),
          { ...t, rules },
          ...hybridTasks.value.slice(idx + 1),
        ]
      }
    }
    // Rule is now attached to a task — remove from unassigned pool too.
    hybridUnassignedRuleIds.value = hybridUnassignedRuleIds.value.filter(id => id !== item.rule_id)
    return { ok: true }
  }

  async function rejectReview(item) {
    if (!item || !hybridSessionId.value) return { ok: false }
    const url = `/api/ingest/hybrid/review/${hybridSessionId.value}/${item.task_id}/${item.rule_id}/reject`
    const res = await fetch(url, { method: 'POST' })
    if (!res.ok) return { ok: false, error: await res.text() }
    hybridReviewQueue.value = hybridReviewQueue.value.filter(
      x => !(x.task_id === item.task_id && x.rule_id === item.rule_id)
    )
    return { ok: true }
  }

  // ----------------------------------------------------------------
  // BL manual control — §8.2.4 operations. Optimistic UI updates are
  // applied after the backend 200s so the Inspector stays in sync
  // without waiting for a full snapshot refetch.
  // ----------------------------------------------------------------

  function _updateTaskRules(taskId, transform) {
    const idx = hybridTasks.value.findIndex(t => t.id === taskId)
    if (idx === -1) return
    const t = hybridTasks.value[idx]
    const rules = Array.isArray(t.rules) ? t.rules : []
    const nextRules = transform(rules)
    hybridTasks.value = [
      ...hybridTasks.value.slice(0, idx),
      { ...t, rules: nextRules },
      ...hybridTasks.value.slice(idx + 1),
    ]
  }

  // Returns true if a rule still has at least one REALIZED_BY across tasks.
  function _ruleHasAnyTask(ruleId) {
    return hybridTasks.value.some(t =>
      Array.isArray(t.rules) && t.rules.some(r => r.id === ruleId),
    )
  }

  async function unassignRuleFromTask(ruleId, taskId) {
    if (!hybridSessionId.value || !ruleId || !taskId) return { ok: false }
    const url = `/api/ingest/hybrid/rule/${hybridSessionId.value}/${ruleId}/unassign/${taskId}`
    const res = await fetch(url, { method: 'POST' })
    if (!res.ok) return { ok: false, error: await res.text() }
    _updateTaskRules(taskId, rules => rules.filter(r => r.id !== ruleId))
    // If rule is now orphaned (no task), surface it in the unassigned pool.
    if (!_ruleHasAnyTask(ruleId) && !hybridUnassignedRuleIds.value.includes(ruleId)) {
      hybridUnassignedRuleIds.value = [...hybridUnassignedRuleIds.value, ruleId]
    }
    return await res.json()
  }

  async function assignRuleToTask(ruleId, taskId) {
    if (!hybridSessionId.value || !ruleId || !taskId) return { ok: false }
    const url = `/api/ingest/hybrid/rule/${hybridSessionId.value}/${ruleId}/assign/${taskId}`
    const res = await fetch(url, { method: 'POST' })
    if (!res.ok) return { ok: false, error: await res.text() }
    const rule = hybridRules.value.find(r => r.id === ruleId)
    if (rule) {
      _updateTaskRules(taskId, rules =>
        rules.some(r => r.id === ruleId)
          ? rules
          : [...rules, { ...rule, confidence: 1.0, match_method: 'manual', reviewed: true }],
      )
    }
    // Rule is now attached — strip from unassigned pool.
    hybridUnassignedRuleIds.value = hybridUnassignedRuleIds.value.filter(id => id !== ruleId)
    return await res.json()
  }

  async function moveRuleBetweenTasks(ruleId, fromTaskId, toTaskId) {
    if (!hybridSessionId.value || !ruleId || !fromTaskId || !toTaskId) return { ok: false }
    if (fromTaskId === toTaskId) return { ok: false, error: 'same task' }
    const url = `/api/ingest/hybrid/rule/${hybridSessionId.value}/${ruleId}/move/${fromTaskId}/${toTaskId}`
    const res = await fetch(url, { method: 'POST' })
    if (!res.ok) return { ok: false, error: await res.text() }
    // Optimistic: strip from source task, append to destination task.
    const rule = hybridRules.value.find(r => r.id === ruleId)
    _updateTaskRules(fromTaskId, rules => rules.filter(r => r.id !== ruleId))
    if (rule) {
      _updateTaskRules(toTaskId, rules =>
        rules.some(r => r.id === ruleId)
          ? rules
          : [...rules, { ...rule, confidence: 1.0, match_method: 'manual', reviewed: true }],
      )
    }
    return await res.json()
  }

  async function setRuleEsRole(ruleId, esRole) {
    if (!hybridSessionId.value || !ruleId || !esRole) return { ok: false }
    const url = `/api/ingest/hybrid/rule/${hybridSessionId.value}/${ruleId}/es-role`
    const res = await fetch(url, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ es_role: esRole }),
    })
    if (!res.ok) return { ok: false, error: await res.text() }
    // Optimistic: bump es_role in both flat rules list and every task's rules[].
    hybridRules.value = hybridRules.value.map(r =>
      r.id === ruleId ? { ...r, es_role: esRole, es_role_confidence: 1.0 } : r,
    )
    hybridTasks.value = hybridTasks.value.map(t => ({
      ...t,
      rules: Array.isArray(t.rules)
        ? t.rules.map(r => r.id === ruleId ? { ...r, es_role: esRole, es_role_confidence: 1.0 } : r)
        : t.rules,
    }))
    return await res.json()
  }

  function addHybridProcess(process, bpmnXml = null) {
    if (!process || !process.id) return
    const payload = bpmnXml ? { ...process, bpmn_xml: bpmnXml } : process
    const idx = hybridProcesses.value.findIndex(p => p.id === process.id)
    if (idx === -1) {
      hybridProcesses.value = [...hybridProcesses.value, payload]
    } else {
      // Merge so we preserve task_ids/actor_ids that may have been appended
      // elsewhere; incoming payload wins on scalar fields. Keep prior bpmn_xml
      // if incoming doesn't carry one (incremental events may send None early).
      const prev = hybridProcesses.value[idx]
      const merged = { ...prev, ...payload }
      if (!payload.bpmn_xml && prev.bpmn_xml) merged.bpmn_xml = prev.bpmn_xml
      hybridProcesses.value = hybridProcesses.value.map((p, i) =>
        i === idx ? merged : p,
      )
    }
  }

  /** Ensure a task's id is listed on its owning process. Used on incremental
   *  HybridTask events so navigator groupings fill in before the final complete
   *  event arrives. */
  function _attachTaskToProcess(processId, taskId) {
    if (!processId || !taskId) return
    const idx = hybridProcesses.value.findIndex(p => p.id === processId)
    if (idx === -1) return
    const p = hybridProcesses.value[idx]
    const task_ids = Array.isArray(p.task_ids) ? p.task_ids : []
    if (task_ids.includes(taskId)) return
    hybridProcesses.value = hybridProcesses.value.map((x, i) =>
      i === idx ? { ...x, task_ids: [...task_ids, taskId] } : x,
    )
  }

  function _attachActorToProcess(processId, actorId) {
    if (!processId || !actorId) return
    const idx = hybridProcesses.value.findIndex(p => p.id === processId)
    if (idx === -1) return
    const p = hybridProcesses.value[idx]
    const actor_ids = Array.isArray(p.actor_ids) ? p.actor_ids : []
    if (actor_ids.includes(actorId)) return
    hybridProcesses.value = hybridProcesses.value.map((x, i) =>
      i === idx ? { ...x, actor_ids: [...actor_ids, actorId] } : x,
    )
  }

  function addHybridActor(actor, processId = null) {
    if (!actor) return
    const pid = processId || actor.process_id || null
    if (!hybridActors.value.some(a => a.id === actor.id)) {
      hybridActors.value = [...hybridActors.value, { ...actor, process_id: pid || actor.process_id }]
    }
    if (pid) _attachActorToProcess(pid, actor.id)
  }

  function addHybridTask(task, bpmnXml, processId = null) {
    if (!task) return
    const pid = processId || task.process_id || null
    const stampedTask = pid ? { ...task, process_id: pid } : task
    const existing = hybridTasks.value.findIndex(t => t.id === task.id)
    if (existing === -1) {
      hybridTasks.value = [...hybridTasks.value, stampedTask]
    } else {
      hybridTasks.value = hybridTasks.value.map((t, i) =>
        i === existing ? { ...t, ...stampedTask } : t,
      )
    }
    if (pid) _attachTaskToProcess(pid, task.id)
    // Live-growing per-process XML updates the process's stored xml so the
    // user can see incremental task reveal when they switch to it mid-ingest.
    if (bpmnXml && pid) {
      const idx = hybridProcesses.value.findIndex(p => p.id === pid)
      if (idx !== -1) {
        const updated = { ...hybridProcesses.value[idx], bpmn_xml: bpmnXml }
        hybridProcesses.value = [
          ...hybridProcesses.value.slice(0, idx),
          updated,
          ...hybridProcesses.value.slice(idx + 1),
        ]
        // If this process is the active one, push to canvas immediately.
        if (activeHybridProcessId.value === pid) {
          activeBpmnXml.value = bpmnXml
          hybridBpmnXml.value = bpmnXml
        }
      }
    }
  }

  function setHybridBpmn({ bpmnXml, processes, actors, tasks }) {
    if (Array.isArray(processes)) {
      // Merge, preserving existing bpmn_xml if incoming is empty (defensive).
      const prevById = new Map(hybridProcesses.value.map(p => [p.id, p]))
      hybridProcesses.value = processes.map(p => {
        const prev = prevById.get(p.id)
        return prev ? { ...prev, ...p } : p
      })
    }
    if (Array.isArray(actors)) hybridActors.value = actors
    if (Array.isArray(tasks)) hybridTasks.value = tasks
    // Global bpmn_xml — kept as a fallback. We do NOT auto-push it to the canvas
    // for multi-process docs; the user picks a process to render.
    if (bpmnXml) {
      hybridBpmnXml.value = bpmnXml
    }
  }

  /** Navigator-friendly view: each process with its own tasks/actors + the
   *  global glossary terms matched to its domain_keywords. The match is a
   *  simple substring check in either direction so terms like "자동이체" hit
   *  a process with keyword "자동이체" or keyword "자동이체 계좌".
   */
  const hybridProcessTrees = computed(() => {
    const glossaryTerms = hybridGlossary.value || []
    const glossaryFor = (kws) => {
      if (!glossaryTerms.length) return []
      const keys = (kws || []).map(k => (k || '').trim()).filter(Boolean)
      if (!keys.length) return []
      return glossaryTerms.filter(g => {
        const term = (g.term || '').trim()
        const aliases = Array.isArray(g.aliases) ? g.aliases : []
        const haystacks = [term, ...aliases].map(x => (x || '').toLowerCase())
        return keys.some(k => {
          const low = k.toLowerCase()
          return haystacks.some(h => h && (h.includes(low) || low.includes(h)))
        })
      })
    }

    if (!hybridProcesses.value.length) {
      if (!hybridTasks.value.length) return []
      return [{
        id: 'proc_legacy',
        name: '(프로세스 미지정)',
        domain_keywords: [],
        tasks: hybridTasks.value,
        actors: hybridActors.value,
        glossary: glossaryTerms,
        bpmn_xml: hybridBpmnXml.value,
      }]
    }
    const tasksById = Object.fromEntries(hybridTasks.value.map(t => [t.id, t]))
    const actorsById = Object.fromEntries(hybridActors.value.map(a => [a.id, a]))
    return hybridProcesses.value.map(p => {
      const tasks = (p.task_ids || [])
        .map(tid => tasksById[tid])
        .filter(Boolean)
        .sort((a, b) => (a.sequence_index || 0) - (b.sequence_index || 0))
      // Keep actors that actually perform at least one task in this process —
      // the Phase 1 LLM over-declares actors ("고객센터", "외부 기관" etc.)
      // that never end up executing a step. Showing them adds noise.
      const usedActorIds = new Set()
      for (const t of tasks) {
        for (const aid of (t.actor_ids || [])) usedActorIds.add(aid)
      }
      return {
        ...p,
        tasks,
        actors: (p.actor_ids || [])
          .map(aid => actorsById[aid])
          .filter(Boolean)
          .filter(a => usedActorIds.has(a.id)),
        glossary: glossaryFor(p.domain_keywords || []),
      }
    })
  })

  function endHybrid() {
    hybridActive.value = false
    // Defensive: clear any stuck spinner from a mid-phase error where the
    // "end" event never arrived.
    clearActiveExploringTaskId()
  }

  // 전체 초기화
  function clear() {
    renderedFlows.value = []
    selectedFlowId.value = null
    activeBpmnXml.value = null
    activeStructured.value = null
    selectedNodeData.value = null
    selectedNodeUi.value = null
    hybridActive.value = false
    hybridProcesses.value = []
    hybridActors.value = []
    hybridTasks.value = []
    hybridBpmnXml.value = null
    hybridRules.value = []
    hybridGlossary.value = []
    hybridReviewQueue.value = []
    hybridUnassignedRuleIds.value = []
    hybridSessionId.value = null
    reviewModalItem.value = null
    _saveSessionId(null)
  }

  return {
    loading,
    error,
    processFlows,
    renderedFlows,
    selectedFlowId,
    activeBpmnXml,
    activeStructured,
    selectedNodeData,
    selectedNodeUi,
    renderedFlowIds,
    fetchProcessFlows,
    addFlow,
    selectFlow,
    removeFlow,
    clear,
    findNodeByBpmnElementId,
    selectNodeForInspector,
    clearInspectorSelection,
    // hybrid
    hybridActive,
    hybridProcesses,
    hybridProcessTrees,
    activeHybridProcessId,
    selectHybridProcess,
    clearHybridProcessSelection,
    hybridActors,
    hybridTasks,
    hybridBpmnXml,
    hybridRules,
    hybridGlossary,
    hybridReviewQueue,
    hybridUnassignedRuleIds,
    hybridSessionId,
    reviewModalItem,
    isHybridRehydrating,
    rehydrateHybrid,
    selectedHybridTaskId,
    selectedHybridTask,
    selectHybridTask,
    clearHybridTaskSelection,
    activeExploringTaskId,
    setActiveExploringTaskId,
    clearActiveExploringTaskId,
    arbitratingTaskIds,
    isArbitrating,
    setArbitratingTaskIds,
    clearArbitrating,
    removeRuleFromTask,
    agentEvents,
    agentState,
    agentError,
    agentTaskId,
    startAgentStream,
    closeAgentStream,
    markAgentCached,
    beginHybrid,
    addHybridProcess,
    addHybridActor,
    addHybridTask,
    setHybridBpmn,
    addHybridRule,
    setHybridRules,
    setHybridGlossary,
    setHybridReviewQueue,
    setHybridSessionId,
    openReviewModal,
    closeReviewModal,
    bcRulesModalCluster,
    openBcRulesModal,
    closeBcRulesModal,
    acceptReview,
    rejectReview,
    unassignRuleFromTask,
    assignRuleToTask,
    moveRuleBetweenTasks,
    setRuleEsRole,
    endHybrid,
  }
})
