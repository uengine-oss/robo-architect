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

  // Generalized tree selection (034 US2): which node kind is in the detail pane.
  const selectedNode = ref({ type: null, id: null }) // type: 'epic'|'feature'|'userStory'

  const designTrace = ref({ nodes: [], relationships: [], empty: false })
  const designTraceLoading = ref(false)

  const impactReport = ref(null)
  let impactPollTimer = null

  // 034 — recoverable deletion history (option B snapshot)
  const deletionRecords = ref([])
  const lastDeletion = ref(null) // { restoreBatchId, scope, ... } of the most recent delete

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

  function findEpic(id) {
    return (tree.value.epics || []).find((e) => e.id === id) || null
  }
  function findFeature(id) {
    for (const epic of tree.value.epics || []) {
      const features = [...(epic.features || [])]
      if (epic.unassignedFeature) features.push(epic.unassignedFeature)
      const hit = features.find((f) => f.id === id)
      if (hit) return hit
    }
    return null
  }

  // Computed so they re-resolve from the freshest tree after edits/refreshes.
  const selectedEpic = computed(() =>
    selectedNode.value.type === 'epic' ? findEpic(selectedNode.value.id) : null,
  )
  const selectedFeature = computed(() =>
    selectedNode.value.type === 'feature' ? findFeature(selectedNode.value.id) : null,
  )

  function _clearUserStorySelection() {
    selectedUserStoryId.value = null
    selectedUserStory.value = null
    designTrace.value = { nodes: [], relationships: [], empty: false }
  }

  async function selectUserStory(usId) {
    selectedNode.value = { type: 'userStory', id: usId }
    selectedUserStoryId.value = usId
    selectedUserStory.value = findUserStory(usId)
    // Radar returns to project scope when viewing an individual story (US4).
    fetchClarityScores('project', '*')
    await fetchDesignTrace(usId)
  }

  /** Select an Epic (BoundedContext) → shows EpicDetail + BC-scoped radar (034 US2/US4). */
  function selectEpic(id) {
    selectedNode.value = { type: 'epic', id }
    _clearUserStorySelection()
    fetchClarityScores('bounded_context', id)
  }

  /** Select a Feature → shows FeatureDetail + feature-scoped radar (034 US2/US4). */
  function selectFeature(id) {
    selectedNode.value = { type: 'feature', id }
    _clearUserStorySelection()
    fetchClarityScores('feature', id)
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

  // ── Epic(BC) create + Epic/Feature edit (034) ─────────────────────────

  /** Build a readable error from a failed response (surfaces 422/404 detail). */
  async function _httpError(res, fallback) {
    let detail = ''
    try {
      const body = await res.json()
      detail = typeof body?.detail === 'string' ? body.detail : ''
    } catch {
      /* no JSON body */
    }
    return new Error(detail || `${fallback}: ${res.status}`)
  }

  /** Propose Epic candidates from a natural-language description (034 US1). */
  async function proposeEpic(text) {
    const res = await fetch('/api/requirements/epic/propose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    if (!res.ok) throw await _httpError(res, 'propose epic failed')
    return res.json() // { proposals: [{name, description}] }
  }

  /** Propose Feature candidates from a natural-language description (034 US1). */
  async function proposeFeature(text, boundedContextId = null) {
    const res = await fetch('/api/requirements/feature/propose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, boundedContextId }),
    })
    if (!res.ok) throw await _httpError(res, 'propose feature failed')
    return res.json() // { proposals: [{name, description, boundedContextId}] }
  }

  /** Create an Epic — i.e. a BoundedContext (034 US1). */
  async function createEpic(name, description = null) {
    const res = await fetch('/api/requirements/bounded-context', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description }),
    })
    if (!res.ok) throw await _httpError(res, 'create epic failed')
    await fetchTree()
    return res.json()
  }

  /** Rename / re-describe an Epic (034 US3). Relationships preserved server-side. */
  async function updateEpic(boundedContextId, { name = null, description = null } = {}) {
    const res = await fetch('/api/requirements/bounded-context', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ boundedContextId, name, description }),
    })
    if (!res.ok) throw await _httpError(res, 'update epic failed')
    await fetchTree()
    return res.json()
  }

  /** Rename / re-describe a Feature (034 US3). Child user stories stay attached. */
  async function updateFeature(featureId, { name = null, description = null } = {}) {
    const res = await fetch('/api/requirements/feature', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ featureId, name, description }),
    })
    if (!res.ok) throw await _httpError(res, 'update feature failed')
    await fetchTree()
    return res.json()
  }

  // ── 생성 엔진 설정 (034 US5) ──────────────────────────────────────────
  // 'in-process' (백엔드 LLM) | 'claude-ide' (로컬 Claude + speckit). 설정은
  // 도구 환경 설정이므로 그래프가 아닌 localStorage에 저장한다.
  const generationEngine = ref(
    (() => {
      try {
        return localStorage.getItem('req_gen_engine') || 'in-process'
      } catch {
        return 'in-process'
      }
    })(),
  )
  function setGenerationEngine(v) {
    generationEngine.value = v
    try {
      localStorage.setItem('req_gen_engine', v)
    } catch {}
  }

  /** Check whether local Claude/speckit are installed (for the claude-ide engine). */
  async function checkLocalTooling() {
    const res = await fetch('/api/requirements/local-tooling/status')
    if (!res.ok) throw await _httpError(res, 'tooling status failed')
    return res.json() // { claudeInstalled, speckitInstalled, missing, installHint }
  }

  // ── 하위 User Story 자동 생성 (034 US5, in-process 엔진) ───────────────

  /**
   * Epic → Feature(spec.md) 자동 생성 (034). 각 Feature = US들 + edge cases + 가정.
   * deepagents(speckit-specify 방법론). 제안만 반환(미확정).
   */
  async function generateFeatures(boundedContextId) {
    const res = await fetch(`/api/requirements/epic/${boundedContextId}/generate-features`, {
      method: 'POST',
    })
    if (!res.ok) throw await _httpError(res, 'generate features failed')
    return res.json() // { boundedContextId, features: [{name, description, edgeCases, assumptions, userStories}] }
  }

  /** 선택된 Feature들(+US, edge cases)을 영속한다. */
  async function confirmFeatures({ boundedContextId, features }) {
    const res = await fetch('/api/requirements/features/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ boundedContextId, features }),
    })
    if (!res.ok) throw await _httpError(res, 'confirm features failed')
    const data = await res.json()
    await fetchTree()
    return data
  }

  /** Generate (propose) child user stories for an Epic/Feature via the LLM. */
  async function generateChildStories(scopeType, scopeId, engine = null) {
    const eng = engine || generationEngine.value
    const qs = new URLSearchParams({ engine: eng }).toString()
    const res = await fetch(`/api/requirements/generate-stories/${scopeType}/${scopeId}?${qs}`, {
      method: 'POST',
    })
    if (!res.ok) throw await _httpError(res, 'generate stories failed')
    return res.json() // { scopeType, scopeId, boundedContextId, featureId, proposals }
  }

  /** Persist the user-selected generated stories under their BC (+Feature). */
  async function confirmChildStories({ boundedContextId, featureId = null, stories }) {
    const res = await fetch('/api/requirements/child-stories/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ boundedContextId, featureId, stories }),
    })
    if (!res.ok) throw await _httpError(res, 'confirm stories failed')
    const data = await res.json()
    await fetchTree()
    return data
  }

  // ── 설계 미반영 User Story 식별 (034 US7) ─────────────────────────────

  /** Fetch user stories that have no design yet (no IMPLEMENTS→Command). */
  async function fetchPendingDesign(scopeType = 'project', scopeId = '*') {
    const qs = new URLSearchParams({ scopeType, scopeId }).toString()
    const res = await fetch(`/api/requirements/user-stories/pending-design?${qs}`)
    if (!res.ok) throw await _httpError(res, 'pending-design failed')
    return res.json() // { pending: [...] }
  }

  /**
   * Fill the requirements→design gap for the given user stories by running the
   * EXISTING ingestion design phases (events→aggregate→command→readmodel) on
   * just those US — same loop, same progress UI, same order (034 US7).
   * Returns { session_id } for the ingestion SSE stream.
   */
  async function requestDesignForUserStories(userStoryIds) {
    const res = await fetch('/api/ingest/user-stories/design', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userStoryIds }),
    })
    if (!res.ok) throw await _httpError(res, 'design request failed')
    return res.json() // { session_id, userStoryCount }
  }

  // ── DDD 적합성·정합성 검증 (034 US6) ──────────────────────────────────

  /** Validate a requirement's BC placement / granularity / spec conflicts. */
  async function validateRequirement(payload) {
    const res = await fetch('/api/requirements/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) throw await _httpError(res, 'validate failed')
    return res.json() // { ok, findings, source }
  }

  async function deleteFeature(featureId, userStoryDisposition = 'unassign', removeDesign = false) {
    const res = await fetch('/api/requirements/feature', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ featureId, userStoryDisposition, removeDesign }),
    })
    if (!res.ok) throw await _httpError(res, 'delete feature failed')
    const data = await res.json()
    if (selectedNode.value.type === 'feature' && selectedNode.value.id === featureId) {
      selectedNode.value = { type: null, id: null }
      selectedFeature.value = null
    }
    await fetchTree()
    lastDeletion.value = { ...data, scope: 'feature' }
    if (data.impactReportId) watchImpactReport(data.impactReportId)
    return data
  }

  async function deleteEpic(boundedContextId, removeDesign = false) {
    const res = await fetch('/api/requirements/bounded-context', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ boundedContextId, removeDesign }),
    })
    if (!res.ok) throw await _httpError(res, 'delete epic failed')
    const data = await res.json()
    if (selectedNode.value.type === 'epic' && selectedNode.value.id === boundedContextId) {
      selectedNode.value = { type: null, id: null }
      selectedEpic.value = null
    }
    await fetchTree()
    lastDeletion.value = { ...data, scope: 'epic' }
    if (data.impactReportId) watchImpactReport(data.impactReportId)
    return data
  }

  // ── Deletion history / recovery (034 — option B snapshot) ──────────────
  async function fetchDeletionRecords() {
    const res = await fetch('/api/requirements/deletion-records')
    if (!res.ok) throw await _httpError(res, 'list deletion records failed')
    const data = await res.json()
    deletionRecords.value = data.records || []
    return deletionRecords.value
  }

  async function restoreDeletion(batchId) {
    const res = await fetch(`/api/requirements/deletion-records/${batchId}/restore`, {
      method: 'POST',
    })
    if (!res.ok) throw await _httpError(res, 'restore failed')
    const data = await res.json()
    await Promise.all([fetchTree(), fetchDeletionRecords()])
    return data
  }

  async function purgeDeletion(batchId) {
    const res = await fetch(`/api/requirements/deletion-records/${batchId}`, {
      method: 'DELETE',
    })
    if (!res.ok) throw await _httpError(res, 'purge failed')
    await fetchDeletionRecords()
  }

  // ── Conversational (chat) edit + collaborative history (035) ───────────
  /** SSE URL for streaming a chat-edit proposal (consumed by ChatEditPanel). */
  function chatEditStreamUrl(scope, id, feedback, history) {
    const qs = new URLSearchParams({ feedback })
    if (history && history.length) qs.set('history', JSON.stringify(history))
    return `/api/requirements/chat-edit/${scope}/${id}/stream?${qs.toString()}`
  }

  async function chatEditApply(scope, id, payload) {
    const res = await fetch(`/api/requirements/chat-edit/${scope}/${id}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (res.status === 409) {
      const body = await res.json().catch(() => ({}))
      const err = new Error('편집 충돌: 다른 사용자가 먼저 수정했습니다.')
      err.conflict = body?.detail
      throw err
    }
    if (!res.ok) throw await _httpError(res, 'chat edit apply failed')
    const data = await res.json()
    await fetchTree()
    if (scope === 'user-story' && selectedUserStoryId.value === id) await selectUserStory(id)
    return data
  }

  async function fetchChatEditLog(scope, id) {
    const res = await fetch(`/api/requirements/chat-edit/${scope}/${id}/log`)
    if (!res.ok) throw await _httpError(res, 'chat log failed')
    return (await res.json()).entries || []
  }

  async function fetchItemHistory(scope, id) {
    const res = await fetch(`/api/requirements/chat-edit/${scope}/${id}/history`)
    if (!res.ok) throw await _httpError(res, 'history failed')
    return (await res.json()).items || []
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

  async function deleteUserStory(userStoryId, removeDesign = false) {
    const res = await fetch('/api/requirements/user-story', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userStoryId, removeDesign }),
    })
    if (!res.ok) throw await _httpError(res, 'delete user story failed')
    const data = await res.json()
    lastDeletion.value = { ...data, scope: 'user_story' }
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

  // ── Clarification (spec 030) ─────────────────────────────────────────

  const clarificationSession = ref(null)
  const clarificationProposal = ref(null)
  const clarificationSummary = ref(null)
  const clarificationLog = ref([])
  const clarificationError = ref(null)
  const clarificationDisambiguation = ref(null)
  const clarificationFlags = ref({}) // { [userStoryId]: FlagInfo }
  const clarityScores = ref(null) // ClarityScoresResponse | null
  let clarificationEventSource = null

  function _closeClarificationStream() {
    if (clarificationEventSource) {
      try { clarificationEventSource.close() } catch {}
      clarificationEventSource = null
    }
  }

  function _subscribeClarification(sessionId) {
    _closeClarificationStream()
    clarificationEventSource = new EventSource(
      `/api/requirements/clarification/sessions/${sessionId}/stream`,
    )
    clarificationEventSource.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data)
        if (event.phase === 'questions_ready') {
          fetchClarificationSession(sessionId)
          // Backend recorded flags during the scan — refresh tree badges + radar.
          fetchClarificationFlags()
          fetchClarityScores()
        } else if (event.phase === 'error') {
          clarificationError.value = event.message || '분석 실패'
          fetchClarificationSession(sessionId)
        } else if (event.phase === 'completed') {
          if (event.data && event.data.summary) {
            clarificationSummary.value = event.data.summary
          }
          fetchClarificationSession(sessionId)
        } else if (event.phase === 'edit_ready' && event.data) {
          clarificationProposal.value = event.data.proposal
        }
        if (clarificationSession.value) {
          clarificationSession.value = {
            ...clarificationSession.value,
            progress: {
              ...(clarificationSession.value.progress || {}),
              phase: event.phase,
              message: event.message,
            },
          }
        }
      } catch (e) {
        log.warn('clarif_event_parse', 'Failed to parse SSE event', { error: String(e) })
      }
    }
  }

  async function fetchClarificationSession(sessionId) {
    try {
      const res = await fetch(`/api/requirements/clarification/sessions/${sessionId}`)
      if (!res.ok) throw new Error(`session fetch failed: ${res.status}`)
      clarificationSession.value = await res.json()
    } catch (e) {
      log.error('clarif_fetch_session', 'Clarification session fetch failed', { error: String(e) })
    }
  }

  async function startClarification(scopeType, scopeId) {
    clarificationError.value = null
    clarificationSummary.value = null
    clarificationProposal.value = null
    clarificationDisambiguation.value = null
    try {
      const res = await fetch('/api/requirements/clarification/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scopeType, scopeId }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        if (res.status === 409 && body?.detail?.sessionId) {
          await fetchClarificationSession(body.detail.sessionId)
          _subscribeClarification(body.detail.sessionId)
          return clarificationSession.value
        }
        const detail = typeof body?.detail === 'string'
          ? body.detail
          : (body?.detail?.code || `start failed: ${res.status}`)
        throw new Error(detail)
      }
      clarificationSession.value = body
      _subscribeClarification(body.sessionId)
      return body
    } catch (e) {
      clarificationError.value = String(e.message || e)
      log.error('clarif_start', 'Clarification start failed', { error: String(e) })
      throw e
    }
  }

  async function answerQuestion(questionId, payload) {
    if (!clarificationSession.value) return null
    clarificationDisambiguation.value = null
    const body = {
      questionId,
      mode: payload.mode,
      optionKey: payload.optionKey ?? null,
      text: payload.text ?? null,
    }
    const sid = clarificationSession.value.sessionId
    const res = await fetch(`/api/requirements/clarification/sessions/${sid}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(`answer failed: ${res.status}`)
    const proposal = await res.json()
    if (proposal.needsDisambiguation) {
      clarificationDisambiguation.value = proposal.disambiguationPrompt || '답변을 다시 입력해 주세요.'
      return proposal
    }
    clarificationProposal.value = proposal
    await fetchClarificationSession(sid)
    return proposal
  }

  async function skipQuestion(questionId) {
    return answerQuestion(questionId, { mode: 'skip' })
  }

  async function applyEdit(questionId) {
    if (!clarificationSession.value) return null
    const sid = clarificationSession.value.sessionId
    const res = await fetch(`/api/requirements/clarification/sessions/${sid}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ questionId }),
    })
    if (!res.ok) throw new Error(`apply failed: ${res.status}`)
    const data = await res.json()
    if (data.conflict) {
      clarificationError.value = data.conflict.message || '요구사항이 외부에서 변경되었습니다.'
    }
    clarificationProposal.value = null
    await fetchClarificationSession(sid)
    if (Array.isArray(data.impactReportIds) && data.impactReportIds.length > 0) {
      watchImpactReport(data.impactReportIds[data.impactReportIds.length - 1])
    }
    await fetchTree()
    // Backend cleared the flag on the applied requirement — re-sync.
    await fetchClarificationFlags()
    await fetchClarityScores()
    return data
  }

  async function endSession() {
    if (!clarificationSession.value) return null
    const sid = clarificationSession.value.sessionId
    const res = await fetch(`/api/requirements/clarification/sessions/${sid}/end`, {
      method: 'POST',
    })
    if (!res.ok) throw new Error(`end failed: ${res.status}`)
    clarificationSummary.value = await res.json()
    await fetchClarificationSession(sid)
    _closeClarificationStream()
    return clarificationSummary.value
  }

  async function fetchSummary(sessionId) {
    const sid = sessionId || clarificationSession.value?.sessionId
    if (!sid) return null
    const res = await fetch(`/api/requirements/clarification/sessions/${sid}/summary`)
    if (!res.ok) throw new Error(`summary failed: ${res.status}`)
    clarificationSummary.value = await res.json()
    return clarificationSummary.value
  }

  async function revertChange(requirementId) {
    if (!clarificationSession.value) return null
    const sid = clarificationSession.value.sessionId
    const res = await fetch(`/api/requirements/clarification/sessions/${sid}/revert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirementId }),
    })
    if (!res.ok) throw new Error(`revert failed: ${res.status}`)
    clarificationSummary.value = await res.json()
    await fetchTree()
    await fetchClarificationFlags()
    await fetchClarityScores()
    return clarificationSummary.value
  }

  async function fetchClarificationFlags() {
    try {
      const res = await fetch('/api/requirements/clarification/flags')
      if (!res.ok) throw new Error(`flags fetch failed: ${res.status}`)
      const data = await res.json()
      clarificationFlags.value = data.userStoryFlags || {}
    } catch (e) {
      log.warn('clarif_fetch_flags', 'Clarification flags fetch failed', { error: String(e) })
    }
  }

  function isUserStoryFlagged(userStoryId) {
    return !!clarificationFlags.value[userStoryId]
  }

  async function fetchClarityScores(scopeType = 'project', scopeId = '*') {
    try {
      const qs = new URLSearchParams({ scopeType, scopeId }).toString()
      const res = await fetch(`/api/requirements/clarification/clarity?${qs}`)
      if (!res.ok) throw new Error(`clarity fetch failed: ${res.status}`)
      clarityScores.value = await res.json()
      return clarityScores.value
    } catch (e) {
      log.warn('clarif_fetch_clarity', 'Clarity fetch failed', { error: String(e) })
      return null
    }
  }

  async function fetchClarificationLog(scopeType, scopeId) {
    const qs = new URLSearchParams({ scopeType, scopeId }).toString()
    const res = await fetch(`/api/requirements/clarification/log?${qs}`)
    if (!res.ok) throw new Error(`log fetch failed: ${res.status}`)
    const data = await res.json()
    clarificationLog.value = data.entries || []
    return data
  }

  function closeClarification() {
    _closeClarificationStream()
    clarificationSession.value = null
    clarificationProposal.value = null
    clarificationSummary.value = null
    clarificationError.value = null
    clarificationDisambiguation.value = null
  }

  // ── Direct edit + history (spec 033) ────────────────────────────────────

  const editHistory = ref([])
  const editHistoryLoading = ref(false)
  const editSaving = ref(false)
  const editError = ref(null)

  async function updateUserStory(userStoryId, fields, baseUpdatedAt = null) {
    editSaving.value = true
    editError.value = null
    try {
      const res = await fetch(`/api/requirements/user-story/${encodeURIComponent(userStoryId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...fields, baseUpdatedAt }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const msg = data?.detail?.code === 'EDIT_CONFLICT'
          ? '다른 사용자가 이미 수정했습니다. 새로고침 후 다시 시도하세요.'
          : `저장 실패: ${res.status}`
        throw new Error(msg)
      }
      // Refresh tree so the left panel reflects the new text
      await fetchTree()
      // Update selected story in memory
      if (selectedUserStoryId.value === userStoryId) {
        selectedUserStory.value = data.userStory
      }
      return data
    } catch (e) {
      editError.value = String(e.message || e)
      log.error('us_update', 'User story update failed', { error: String(e) })
      throw e
    } finally {
      editSaving.value = false
    }
  }

  async function fetchHistory(userStoryId) {
    editHistoryLoading.value = true
    try {
      const res = await fetch(`/api/requirements/user-story/${encodeURIComponent(userStoryId)}/history`)
      if (!res.ok) throw new Error(`history fetch failed: ${res.status}`)
      const data = await res.json()
      editHistory.value = data.items || []
    } catch (e) {
      editHistory.value = []
      log.warn('us_history', 'Edit history fetch failed', { error: String(e) })
    } finally {
      editHistoryLoading.value = false
    }
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
    selectedNode,
    selectedEpic,
    selectedFeature,
    designTrace,
    designTraceLoading,
    impactReport,
    hasImpactFindings,
    fetchTree,
    selectUserStory,
    selectEpic,
    selectFeature,
    fetchDesignTrace,
    proposeUserStory,
    confirmUserStory,
    createFeature,
    createEpic,
    proposeEpic,
    proposeFeature,
    updateEpic,
    updateFeature,
    generationEngine,
    setGenerationEngine,
    checkLocalTooling,
    generateFeatures,
    confirmFeatures,
    generateChildStories,
    confirmChildStories,
    validateRequirement,
    fetchPendingDesign,
    requestDesignForUserStories,
    deleteFeature,
    deleteEpic,
    moveUserStory,
    deleteUserStory,
    deletionRecords,
    lastDeletion,
    fetchDeletionRecords,
    restoreDeletion,
    purgeDeletion,
    chatEditStreamUrl,
    chatEditApply,
    fetchChatEditLog,
    fetchItemHistory,
    watchImpactReport,
    dismissImpactReport,
    clearAllData,
    // ── Direct edit + history (033) ───────────────────────────────────
    editHistory,
    editHistoryLoading,
    editSaving,
    editError,
    updateUserStory,
    fetchHistory,
    // ── Clarification (030) ────────────────────────────────────────────
    clarificationSession,
    clarificationProposal,
    clarificationSummary,
    clarificationLog,
    clarificationError,
    clarificationDisambiguation,
    clarificationFlags,
    clarityScores,
    startClarification,
    fetchClarificationSession,
    answerQuestion,
    skipQuestion,
    applyEdit,
    endSession,
    fetchSummary,
    revertChange,
    fetchClarificationLog,
    fetchClarificationFlags,
    fetchClarityScores,
    isUserStoryFlagged,
    closeClarification,
  }
})
