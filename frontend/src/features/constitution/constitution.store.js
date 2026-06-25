import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Pinia store for project / Bounded-Context Constitution management (feature 041).
 *
 * The Constitution lives in Neo4j as a project-root node plus optional per-BC
 * override nodes (the graph is the source of truth, Principle I). This store
 * backs the **Design-side** management UI (project 헌장 + per-BC 헌장). It is
 * entirely independent of the Proposals feature — the proposal flow only ever
 * runs the one-time interview gate, never these view/edit endpoints.
 *
 * Fields shape: { designPrinciples, techStack, architectureStyle, repoStrategy, repoMode }.
 */
export const useConstitutionStore = defineStore('constitution', () => {
  // 프로젝트-루트 Constitution: { exists, scope, fields, raw, constitutionHash, updatedAt }
  const project = ref(null)
  // 현재 보고 있는 BC 의 { override, effective } (effective = 프로젝트-루트 + 오버라이드 병합)
  const bc = ref({ bcId: null, override: null, effective: null })
  const loading = ref(false)
  const error = ref(null)

  // ---------------------------------------------------------------------------
  // Project-root Constitution
  // ---------------------------------------------------------------------------

  async function getProjectConstitution() {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/constitution')
      if (!res.ok) throw new Error(`Constitution 조회 실패: ${res.status}`)
      project.value = await res.json()
      return project.value
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  // raw(Markdown) + 선택적 fields 로 프로젝트-루트 Constitution 을 upsert.
  // 저장 시 의존 Proposal plan 들이 stale 처리된다(FR-018, 백엔드 처리).
  async function saveProjectConstitution(raw, fields = null) {
    error.value = null
    const body = { raw }
    if (fields) body.fields = fields
    const res = await fetch('/api/constitution', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || `Constitution 저장 실패: ${res.status}`)
    }
    const data = await res.json() // { constitutionHash }
    await getProjectConstitution()
    return data
  }

  // 042 — 프로젝트 전략 메모리(strategicMemory)만 갱신. 저장 시 plan staleness 유발(FR-021).
  async function saveProjectStrategicMemory(memory) {
    error.value = null
    const res = await fetch('/api/constitution/strategic-memory', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(memory || {}),
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || `전략 메모리 저장 실패: ${res.status}`)
    }
    const data = await res.json()
    await getProjectConstitution()
    return data
  }

  // ---------------------------------------------------------------------------
  // Per-Bounded-Context Constitution (override + effective)
  // ---------------------------------------------------------------------------

  async function getBcConstitution(bcId) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/bounded-contexts/${encodeURIComponent(bcId)}/constitution`)
      if (!res.ok) throw new Error(`BC Constitution 조회 실패: ${res.status}`)
      const data = await res.json() // { override, effective }
      bc.value = { bcId, override: data.override ?? null, effective: data.effective ?? null }
      return bc.value
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  // BC 오버라이드를 upsert. payload: { raw?, fields? }
  async function saveBcConstitution(bcId, { raw = null, fields = null } = {}) {
    error.value = null
    const body = {}
    if (raw != null) body.raw = raw
    if (fields) body.fields = fields
    const res = await fetch(`/api/bounded-contexts/${encodeURIComponent(bcId)}/constitution`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || `BC Constitution 저장 실패: ${res.status}`)
    }
    const data = await res.json() // { constitutionHash }
    await getBcConstitution(bcId)
    return data
  }

  // BC 오버라이드를 제거하고 프로젝트-루트로 폴백.
  async function deleteBcConstitution(bcId) {
    error.value = null
    const res = await fetch(`/api/bounded-contexts/${encodeURIComponent(bcId)}/constitution`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || `BC Constitution 삭제 실패: ${res.status}`)
    }
    await getBcConstitution(bcId)
    return true
  }

  // ---------------------------------------------------------------------------
  // 인터뷰로 프로젝트 루트 헌장 작성
  //  - 게이팅 질문은 백엔드가 결정적으로(즉시) 제공. ← 이전 / 다음 → 네비게이션 + 답 수정.
  //  - 모든 게이팅 결정 후 '헌장 생성'(SSE) 으로 스킬이 Markdown 합성.
  // ---------------------------------------------------------------------------
  // steps: [{ question, answer }]
  const interview = ref({ steps: [], idx: 0, complete: false, busy: false, analyzing: false, synthesizing: false, done: false, error: null, logLines: [] })
  let _interviewEs = null

  async function _post(path, body) {
    const res = await fetch(path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return res.json().catch(() => ({}))
  }

  async function startProjectInterview(proposalId = null) {
    interview.value = { steps: [], idx: 0, complete: false, busy: true, analyzing: false, synthesizing: false, done: false, error: null, logLines: [] }
    // Plan 게이트(proposalId) 진입 → Claude Code 가 제안을 먼저 분석(SSE, 진행 로그) 후 첫 질문.
    if (proposalId) {
      interview.value.analyzing = true
      const es = new EventSource(`/api/constitution/interview/analyze?proposalId=${encodeURIComponent(proposalId)}`)
      const h = {
        log_line: (d) => { if (d?.text) interview.value.logLines.push(d.text) },
        question: (d) => {
          interview.value.steps = d ? [{ question: d, answer: d.recommended ?? null }] : []
          interview.value.idx = 0
          interview.value.complete = !d
        },
        done: () => { es.close(); _interviewEs = null; interview.value.analyzing = false; interview.value.busy = false },
        error: (d) => { es.close(); _interviewEs = null; interview.value.analyzing = false; interview.value.busy = false; interview.value.error = d?.message || '제안 분석 실패' },
      }
      Object.entries(h).forEach(([evt, fn]) => es.addEventListener(evt, (e) => { try { fn(JSON.parse(e.data)) } catch {} }))
      es.onerror = () => { if (!interview.value.analyzing) return; es.close(); _interviewEs = null; interview.value.analyzing = false; interview.value.busy = false }
      _interviewEs = es
      return
    }
    // Design 측(그래프 기반) — 결정적 첫 질문 즉시.
    try {
      const r = await _post('/api/constitution/interview/start')
      const q = r.question
      interview.value.steps = q ? [{ question: q, answer: q.recommended ?? null }] : []
      interview.value.complete = !q
      interview.value.idx = 0
    } catch (e) {
      interview.value.error = e.message
    } finally {
      interview.value.busy = false
    }
  }

  // 현재 질문의 답을 선택(로컬). 기록/다음 질문 산출은 nextInterviewStep 에서.
  function selectInterviewAnswer(val) {
    const s = interview.value.steps[interview.value.idx]
    if (s) s.answer = val
  }

  // 다음으로: 현재 답을 기록 → (상위 변경 시 하위 폐기) → 다음 질문 append, 또는 complete.
  async function nextInterviewStep() {
    const iv = interview.value
    const s = iv.steps[iv.idx]
    if (!s) return
    const val = s.answer ?? s.question.recommended
    if (val == null || val === '') return
    iv.busy = true
    try {
      const r = await _post('/api/constitution/interview/answer', { field: s.question.field, answer: val })
      iv.steps = iv.steps.slice(0, iv.idx + 1) // 상위 변경 시 하위 폐기
      if (r.question) {
        iv.steps.push({ question: r.question, answer: r.question.recommended ?? null })
        iv.idx = iv.steps.length - 1
        iv.complete = false
      } else {
        iv.complete = true // 모든 게이팅 결정 완료 → '헌장 생성' 노출
      }
    } catch (e) {
      iv.error = e.message
    } finally {
      iv.busy = false
    }
  }

  function prevInterviewStep() {
    if (interview.value.idx > 0) interview.value.idx -= 1
  }

  // 모든 결정 확정 후 스킬로 헌장 Markdown 합성(SSE).
  function generateConstitution() {
    interview.value.synthesizing = true
    interview.value.error = null
    interview.value.logLines = []
    const es = new EventSource('/api/constitution/stream')
    const h = {
      // 합성(헌장 본문 작성) 진행 로그 — 백엔드가 흘려보낸 narration 을 그대로 표시.
      log_line: (d) => { if (d?.text) interview.value.logLines.push(d.text) },
      draft: () => {},
      done: async (d) => {
        es.close(); _interviewEs = null
        interview.value.synthesizing = false
        if (d?.pending) return
        await getProjectConstitution()
        interview.value.done = true
      },
      error: (d) => {
        interview.value.synthesizing = false
        interview.value.error = d?.message || '헌장 생성 실패'
        es.close(); _interviewEs = null
      },
    }
    Object.entries(h).forEach(([evt, fn]) => es.addEventListener(evt, (e) => { try { fn(JSON.parse(e.data)) } catch {} }))
    es.onerror = () => { if (interview.value.done) return; interview.value.synthesizing = false; es.close(); _interviewEs = null }
    _interviewEs = es
    return es
  }

  function stopProjectInterview() {
    if (_interviewEs) { _interviewEs.close(); _interviewEs = null }
    interview.value.synthesizing = false
  }

  return {
    project, bc, loading, error, interview,
    getProjectConstitution, saveProjectConstitution, saveProjectStrategicMemory,
    getBcConstitution, saveBcConstitution, deleteBcConstitution,
    startProjectInterview, selectInterviewAnswer, nextInterviewStep,
    prevInterviewStep, generateConstitution, stopProjectInterview,
  }
})
