import { defineStore } from 'pinia'
import { ref } from 'vue'
import { translate } from '../../app/i18n'

const BASE = '/api/proposals'

// 샌드박스 worktree 경로(.../.sandbox/proposal/<id>[/...])를 실제 프로젝트 루트로
// 끌어올린다. 오염된 projectRoot가 새 worktree의 원천이 되어 중첩 생성되는 것을 막는다.
function stripSandbox(p) {
  if (!p) return p
  const i = p.indexOf('/.sandbox/')
  return i >= 0 ? p.slice(0, i) : p
}

export const useProposalsStore = defineStore('proposals', () => {
  const proposals = ref([])
  const currentProposal = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const intentStream = ref({ active: false, events: [] })
  const sandboxStream = ref({ active: false, tasks: [], logs: [] })
  // 작업 분해(헤드리스) 스트림 — narration + 분해된 작업 목록.
  const tasksStream = ref({ active: false, logLines: [], tasks: [], error: null })
  // 검증(runner) 스트림 — 실행 로그(narration·tool) 실시간 표시. 중지 가능.
  const validationStream = ref({ active: false, logLines: [], error: null })
  // 041 — Plan 게이트용 Constitution 상태(존재 여부/architectureStyle). 인터뷰 UI 는
  // Design 측 표준 ConstitutionEditor(constitution 피처)를 재사용하므로 여기엔 없다.
  const constitution = ref(null)
  // 041 — Plan 단계 SSE 스트림(tactical/impact/architecture/done).
  const plan = ref(null)
  const planStream = ref({ active: false, tactical: null, impact: null, architecture: [], constitutionGaps: [], logLines: [], done: false, error: null, constitutionRequired: false })
  // 042 — Detailed DDD 스테이지 스트림(scope/stage 공용).
  const stagedStream = ref({ active: false, stage: null, logLines: [], stagePlan: null, artifact: null, conflicts: [], nextStage: null, done: false, error: null })
  // 042 — 미확정 스테이지 산출물 초안(탭 전환·언마운트에도 보존; 키 `${pid}:${stage}`).
  // 컴포넌트 로컬에만 두면 탭 이동 시 unmount → 스킬 재실행으로 작업이 사라지는 문제를 막는다.
  const stageDrafts = ref({})
  let _intentEs = null
  let _tasksEs = null
  let _validateEs = null
  let _planEs = null
  let _stagedEs = null
  const testResults = ref(null)

  // ---------------------------------------------------------------------------
  // Proposal CRUD
  // ---------------------------------------------------------------------------

  async function fetchProposals(params = {}) {
    loading.value = true
    error.value = null
    try {
      const qs = new URLSearchParams()
      if (params.status) {
        const statuses = Array.isArray(params.status) ? params.status : [params.status]
        statuses.forEach(s => qs.append('status', s))
      }
      if (params.author) qs.set('author', params.author)
      if (params.limit != null) qs.set('limit', params.limit)
      if (params.offset != null) qs.set('offset', params.offset)
      const url = qs.toString() ? `${BASE}/?${qs}` : `${BASE}/`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`Fetch proposals failed: ${res.status}`)
      proposals.value = await res.json()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchProposal(id) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`${BASE}/${id}`)
      if (!res.ok) throw new Error(`Fetch proposal ${id} failed: ${res.status}`)
      currentProposal.value = await res.json()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createProposal(originalPrompt, title = null, decompositionMode = 'SIMPLIFIED') {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`${BASE}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ originalPrompt, title, decompositionMode }),
      })
      if (!res.ok) throw new Error(`Create proposal failed: ${res.status}`)
      const proposal = await res.json()
      proposals.value.unshift(proposal)
      currentProposal.value = proposal
      return proposal
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  // Proposal 영구 삭제 — 확인용으로 id 를 다시 입력해 일치해야 한다(오삭제 방지).
  // 성공 시 목록에서 제거하고, 현재 선택 중이었다면 비운다.
  async function deleteProposal(proposalId, confirmId) {
    const res = await fetch(`${BASE}/${proposalId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmId }),
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      const d = detail.detail
      throw new Error((typeof d === 'string' ? d : d?.message) || `Delete failed: ${res.status}`)
    }
    proposals.value = proposals.value.filter(p => p.id !== proposalId)
    if (currentProposal.value?.id === proposalId) currentProposal.value = null
  }

  // ---------------------------------------------------------------------------
  // Intent SSE
  // ---------------------------------------------------------------------------

  function subscribeToIntent(proposalId) {
    intentStream.value = { active: true, events: [], clarificationQuestions: null, toolLogs: [], logLines: [] }
    const es = new EventSource(`${BASE}/stream/${proposalId}/intent`)

    const handlers = {
      phase: (data) => intentStream.value.events.push({ type: 'phase', data }),
      tool_use: (data) => {
        intentStream.value.toolLogs.push({ tool: data.tool, path: data.path })
        if (intentStream.value.toolLogs.length > 50) intentStream.value.toolLogs.shift()
      },
      log_line: (data) => {
        intentStream.value.logLines.push(data.text)
        if (intentStream.value.logLines.length > 200) intentStream.value.logLines.shift()
      },
      clarification_needed: (data) => {
        intentStream.value.clarificationQuestions = data.questions
        intentStream.value.events.push({ type: 'clarification_needed', data })
      },
      strategic_diff: (data) => {
        intentStream.value.events.push({ type: 'strategic_diff', data })
        if (currentProposal.value?.id === proposalId) {
          currentProposal.value = { ...currentProposal.value, strategicDiff: data.strategicDiff }
        }
      },
      tactical_diff: (data) => {
        intentStream.value.events.push({ type: 'tactical_diff', data })
        if (currentProposal.value?.id === proposalId) {
          currentProposal.value = { ...currentProposal.value, tacticalDiff: data.tacticalDiff }
        }
      },
      impact_map: (data) => {
        intentStream.value.events.push({ type: 'impact_map', data })
        if (currentProposal.value?.id === proposalId) {
          currentProposal.value = { ...currentProposal.value, impactMap: data.impactMap }
        }
      },
      done: (data) => {
        intentStream.value.active = false
        intentStream.value.events.push({ type: 'done', data })
        es.close()
        fetchProposal(proposalId)
      },
      error: (data) => {
        intentStream.value.active = false
        intentStream.value.error = data.message
        es.close()
      },
    }

    Object.entries(handlers).forEach(([evtType, handler]) => {
      es.addEventListener(evtType, (e) => {
        try { handler(JSON.parse(e.data)) } catch {}
      })
    })

    es.onerror = () => {
      intentStream.value.active = false
      es.close()
      _intentEs = null
    }

    _intentEs = es
    return es
  }

  function stopIntent() {
    if (_intentEs) {
      _intentEs.close()
      _intentEs = null
    }
    intentStream.value.active = false
  }

  // ---------------------------------------------------------------------------
  // Tasks 분해 SSE — 셸이 아니라 proposal 쪽에서 미리 작업을 뽑아 스트리밍한다.
  // ---------------------------------------------------------------------------

  // 작업 분해를 스트리밍한다. done이면 분해된 작업 목록으로 resolve, error면 reject.
  // "구현하기"가 작업 목록이 없을 때 이 Promise를 await해 먼저 생성한 뒤 진행한다.
  function subscribeToTasks(proposalId) {
    tasksStream.value = { active: true, logLines: [], tasks: [], error: null }
    return new Promise((resolve, reject) => {
      const es = new EventSource(`${BASE}/stream/${proposalId}/tasks`)
      let settled = false
      const finish = (fn, arg) => { if (settled) return; settled = true; es.close(); _tasksEs = null; fn(arg) }
      const handlers = {
        phase: () => {},
        log_line: (d) => {
          tasksStream.value.logLines.push(d.text)
          if (tasksStream.value.logLines.length > 200) tasksStream.value.logLines.shift()
        },
        tasks: (d) => { tasksStream.value.tasks = d.tasks || [] },
        done: () => { tasksStream.value.active = false; finish(resolve, tasksStream.value.tasks) },
        error: (d) => { tasksStream.value.active = false; tasksStream.value.error = d.message; finish(reject, new Error(d.message || translate('proposals.store.tasksDecomposeFailed'))) },
      }
      Object.entries(handlers).forEach(([evt, h]) => {
        es.addEventListener(evt, (e) => { try { h(JSON.parse(e.data)) } catch {} })
      })
      es.onerror = () => {
        tasksStream.value.active = false
        // 정상 done 이후의 close가 아니면 실패로 처리한다.
        finish(reject, new Error(translate('proposals.store.tasksConnectionDropped')))
      }
      _tasksEs = es
    })
  }

  function stopTasks() {
    if (_tasksEs) { _tasksEs.close(); _tasksEs = null }
    tasksStream.value.active = false
  }

  // 저장된 작업 목록을 불러온다(재방문 시 재표시). { exists, tasks, markdown }
  async function fetchTasks(proposalId) {
    const res = await fetch(`${BASE}/${proposalId}/tasks`)
    if (!res.ok) throw new Error(`tasks ${res.status}`)
    const data = await res.json()
    if (data.exists) tasksStream.value.tasks = data.tasks || []
    return data
  }

  // 인텐트 분해 결과가 잘못됐을 때 보정 피드백을 등록한다(DRAFT 한정).
  // 등록 후 호출자가 subscribeToIntent를 다시 구독하면 피드백+이전 diff로 재생성된다.
  async function submitIntentFeedback(proposalId, feedback) {
    const res = await fetch(`${BASE}/${proposalId}/intent/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback }),
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || `Intent feedback failed: ${res.status}`)
    }
    currentProposal.value = await res.json()
  }

  async function answerClarification(proposalId, answers) {
    try {
      const res = await fetch(`${BASE}/${proposalId}/clarify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
      })
      if (!res.ok) throw new Error(`Clarify failed: ${res.status}`)
      currentProposal.value = await res.json()
    } catch (e) {
      error.value = e.message
    }
  }

  // ---------------------------------------------------------------------------
  // Diff editing & Submit
  // ---------------------------------------------------------------------------

  async function updateDiff(proposalId, { strategicDiff, tacticalDiff }) {
    try {
      const res = await fetch(`${BASE}/${proposalId}/diff`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategicDiff, tacticalDiff }),
      })
      if (!res.ok) {
        // 422(스키마 검증 실패) 등은 백엔드의 한국어 사유를 그대로 노출한다.
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Update diff failed: ${res.status}`)
      }
      currentProposal.value = await res.json()
    } catch (e) {
      // 호출자(saveDiff)가 사유를 표시하고 편집기를 열어둘 수 있도록 재던진다.
      error.value = e.message
      throw e
    }
  }

  async function submitProposal(proposalId) {
    try {
      const res = await fetch(`${BASE}/${proposalId}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Submit failed: ${res.status}`)
      }
      currentProposal.value = await res.json()
      const idx = proposals.value.findIndex(p => p.id === proposalId)
      if (idx >= 0) proposals.value[idx] = currentProposal.value
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  // ---------------------------------------------------------------------------
  // Sandbox implement — Code 탭의 Claude Code 셀(PTY 터미널) 재사용 (FR-007)
  // ---------------------------------------------------------------------------

  // 대상 프로젝트(projectRoot)에 Worktree를 만들고, 셀이 실행할 구현 지시를 받는다.
  // 컴포넌트가 반환값으로 openClaudeCode(worktreePath, command)를 호출해 셀에 위임한다.
  // (실제 구현 로그/중지/피드백은 모두 그 셀에서 이뤄진다.)
  // initGit=true 는 대상 프로젝트가 Git 저장소가 아닐 때 사용자가 다이얼로그로
  // 동의한 뒤의 재시도다. 그러면 백엔드가 git init 후 Worktree를 만든다. (FR-006)
  async function implementProposal(proposalId, projectRoot, initGit = false) {
    sandboxStream.value = { active: true, error: null }
    // 오염된 projectRoot(다른 Proposal의 worktree 경로 등)가 새어 들어와도 Worktree를
    // 그 안에 중첩 생성하지 않도록 가장 바깥 '/.sandbox/' 앞에서 잘라 실제 루트로 보낸다.
    const cleanRoot = stripSandbox(projectRoot)
    try {
      const res = await fetch(`${BASE}/${proposalId}/implement`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectRoot: cleanRoot, initGit }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const d = body.detail
        // 대상이 Git 저장소가 아님 → 컴포넌트가 잡아 git init 다이얼로그를 띄운다.
        if (d && typeof d === 'object' && d.code === 'NOT_A_GIT_REPO') {
          sandboxStream.value.active = false
          const err = new Error(d.message || translate('proposals.store.notAGitRepo'))
          err.code = 'NOT_A_GIT_REPO'
          err.projectRoot = d.projectRoot
          throw err
        }
        throw new Error((typeof d === 'string' ? d : d?.message) || `Implement failed: ${res.status}`)
      }
      const data = await res.json()
      sandboxStream.value.active = false
      if (currentProposal.value?.id === proposalId) {
        currentProposal.value = {
          ...currentProposal.value,
          status: 'IMPLEMENTING',
          sandboxBranch: data.branch,
          sandboxWorktreePath: data.worktreePath,
          sandboxStatus: 'IMPLEMENTING',
          projectRoot: cleanRoot,
        }
      }
      _syncListItem(proposalId)
      return data // { proposalId, status, worktreePath, branch, command }
    } catch (e) {
      sandboxStream.value.active = false
      sandboxStream.value.error = e.message
      throw e
    }
  }

  // 구현 진행 상황 — 워크트리의 tasks.md(체크리스트)를 읽어 진행률을 반환한다.
  // 구현 탭이 주기적으로 폴링한다. (네트워크 오류는 조용히 무시 — 폴링이 계속됨)
  async function fetchProgress(proposalId) {
    const res = await fetch(`${BASE}/${proposalId}/progress`)
    if (!res.ok) throw new Error(`progress ${res.status}`)
    return res.json()
  }

  // 사용자가 셀에서의 구현을 마쳤다고 표시 → IMPLEMENTING → TESTING + 자동 테스트.
  async function completeImplementation(proposalId) {
    try {
      const res = await fetch(`${BASE}/${proposalId}/implement/complete`, { method: 'POST' })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Complete failed: ${res.status}`)
      }
      if (currentProposal.value?.id === proposalId) {
        currentProposal.value = { ...currentProposal.value, status: 'TESTING', sandboxStatus: 'DONE' }
      }
      _syncListItem(proposalId)
      await fetchProposal(proposalId)
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  // ---------------------------------------------------------------------------
  // Test results & Acceptance
  // ---------------------------------------------------------------------------

  // 검증 결과 조회 — 폴링용이라 아직 없으면(404) 조용히 null 반환(전역 error 미설정).
  async function fetchTestResults(proposalId) {
    try {
      const res = await fetch(`${BASE}/${proposalId}/test-results`)
      if (res.status === 404) { testResults.value = null; return null }
      if (!res.ok) return null
      testResults.value = await res.json()
      return testResults.value
    } catch {
      return null
    }
  }

  // 검증 실행/재검증(비스트리밍 폴백) — robo-sync 구조 검증 + GWT를 백그라운드로 트리거.
  async function runValidation(proposalId) {
    const res = await fetch(`${BASE}/${proposalId}/validate`, { method: 'POST' })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || `Validate failed: ${res.status}`)
    }
    return res.json()
  }

  // 검증을 runner(스트리밍)로 실행하며 실행 로그를 받는다. (작업 분해와 동일 방식)
  // 중지 = stopValidation()이 EventSource를 닫으면 서버 서브프로세스도 정리된다.
  function subscribeToValidation(proposalId) {
    validationStream.value = { active: true, logLines: [], error: null }
    testResults.value = null  // 재검증: 이전 결과를 비우고 '검증 중' 상태로
    return new Promise((resolve, reject) => {
      const es = new EventSource(`${BASE}/stream/${proposalId}/validate`)
      let settled = false
      const finish = (fn, arg) => { if (settled) return; settled = true; es.close(); _validateEs = null; fn(arg) }
      const handlers = {
        phase: () => {},
        log_line: (d) => {
          validationStream.value.logLines.push(d.text)
          if (validationStream.value.logLines.length > 300) validationStream.value.logLines.shift()
        },
        results: (d) => { testResults.value = d },
        done: () => {
          validationStream.value.active = false
          fetchProposal(proposalId)  // 상태 PENDING_ACCEPTANCE 반영
          finish(resolve, testResults.value)
        },
        error: (d) => {
          validationStream.value.active = false
          validationStream.value.error = d.message
          finish(reject, new Error(d.message || translate('proposals.store.validationFailed')))
        },
      }
      Object.entries(handlers).forEach(([evt, h]) => {
        es.addEventListener(evt, (e) => { try { h(JSON.parse(e.data)) } catch {} })
      })
      es.onerror = () => {
        // 사용자가 중지(close)한 경우엔 settled 처리가 끝나 onerror가 무시된다.
        if (settled) return
        validationStream.value.active = false
        finish(reject, new Error(translate('proposals.store.validationConnectionDropped')))
      }
      _validateEs = es
    })
  }

  // 검증 중지 — EventSource를 닫아 서버 generator를 취소(서브프로세스 kill)시킨다.
  function stopValidation() {
    if (_validateEs) { _validateEs.close(); _validateEs = null }
    validationStream.value.active = false
  }

  async function acceptProposal(proposalId, { comment = null, forceAcceptWithFailures = false } = {}) {
    try {
      const res = await fetch(`${BASE}/${proposalId}/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment, forceAcceptWithFailures }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Accept failed: ${res.status}`)
      }
      currentProposal.value = await res.json()
      _syncListItem(proposalId)
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  async function destroyProposal(proposalId, { reason = null } = {}) {
    try {
      const res = await fetch(`${BASE}/${proposalId}/destroy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Destroy failed: ${res.status}`)
      }
      currentProposal.value = await res.json()
      _syncListItem(proposalId)
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  async function revokeProposal(proposalId, { revertCode = false, comment = null } = {}) {
    try {
      const res = await fetch(`${BASE}/${proposalId}/revoke`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ revertCode, comment }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Revoke failed: ${res.status}`)
      }
      currentProposal.value = await res.json()
      _syncListItem(proposalId)
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  async function retryMerge(proposalId) {
    sandboxStream.value = { active: true, tasks: [], logs: [], error: null }
    try {
      const res = await fetch(`${BASE}/${proposalId}/retry-merge`, { method: 'POST' })
      if (!res.ok) throw new Error(`Retry merge failed: ${res.status}`)
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      function read() {
        reader.read().then(({ done, value }) => {
          if (done) { sandboxStream.value.active = false; fetchProposal(proposalId); return }
          buffer += decoder.decode(value, { stream: true })
          read()
        })
      }
      read()
    } catch (e) {
      sandboxStream.value.active = false
      sandboxStream.value.error = e.message
    }
  }

  // ---------------------------------------------------------------------------
  // 041 — Constitution (Plan 게이트용 상태 조회만; 인터뷰/수정 UI 는 Design 측 재사용)
  // ---------------------------------------------------------------------------

  // Plan 게이트용 상태 확인 — 프로젝트-루트 Constitution 존재 여부/architectureStyle 등.
  // (인터뷰/보기/수정은 Design 측 constitution 피처의 ConstitutionEditor 가 담당한다.)
  async function getConstitution(proposalId) {
    try {
      const res = await fetch(`${BASE}/${proposalId}/constitution`)
      if (!res.ok) throw new Error(translate('proposals.store.constitutionFetchFailed', { status: res.status }))
      constitution.value = await res.json()
      return constitution.value
    } catch (e) {
      error.value = e.message
      return null
    }
  }

  // ---------------------------------------------------------------------------
  // 041 — Plan 단계 (전략 diff + Constitution → tactical + impact + 아키텍처 결정)
  // ---------------------------------------------------------------------------

  // 저장된 ImplementationPlan 을 조회한다(재방문 시 재표시). { ...implementationPlan, planStale }
  async function getPlan(proposalId) {
    try {
      const res = await fetch(`${BASE}/${proposalId}/plan`)
      if (res.status === 404) { plan.value = null; return null }
      if (!res.ok) throw new Error(translate('proposals.store.planFetchFailed', { status: res.status }))
      const data = await res.json()
      // 응답은 {implementationPlan: {...}|null} 형태로 감싸여 온다. 항상 ImplementationPlan
      // 본체로 정규화해, 라이브 스트림(done)과 새로고침 후가 동일한 모양이 되도록 한다.
      plan.value = data?.implementationPlan ?? null
      return plan.value
    } catch (e) {
      error.value = e.message
      return null
    }
  }

  // 에러 응답을 사람이 읽을 문자열로 환원한다. FastAPI 422 는 detail 이
  // 객체 배열([{loc,msg,...}])이라, 그대로 new Error 에 넣으면 "[object Object]" 가 된다.
  async function _extractError(res, fallback) {
    let body
    try { body = await res.json() } catch { return `${fallback}: ${res.status}` }
    const d = body?.detail ?? body
    if (typeof d === 'string') return d
    if (Array.isArray(d)) return d.map((e) => e?.msg || e?.message || JSON.stringify(e)).join('; ')
    if (d && typeof d === 'object') return d.message || d.msg || JSON.stringify(d)
    return `${fallback}: ${res.status}`
  }

  // Plan 단계를 SSE 로 구동한다(tactical/impact/architecture/done).
  // Constitution 이 없으면 409 {reason:"constitution_required"} → constitutionRequired 플래그를
  // 세워 컴포넌트가 인터뷰로 라우팅한다(FR-010).
  async function runPlan(proposalId) {
    planStream.value = { active: true, tactical: null, impact: null, architecture: [], constitutionGaps: [], logLines: [], done: false, error: null, constitutionRequired: false }
    // SSE 는 GET 이라 409 본문을 미리 확인할 수 없다 → EventSource 연결 직후 즉시 종료되면
    // (onerror, done 미수신) 사전조건 미충족으로 간주하고 /plan 으로 사유를 조회한다.
    return new Promise((resolve, reject) => {
      const es = new EventSource(`${BASE}/${proposalId}/stream/plan`)
      let settled = false
      const finish = (fn, arg) => { if (settled) return; settled = true; es.close(); _planEs = null; fn(arg) }
      const handlers = {
        phase: () => {},
        log_line: (d) => {
          planStream.value.logLines.push(d.text)
          if (planStream.value.logLines.length > 200) planStream.value.logLines.shift()
        },
        tactical: (d) => {
          planStream.value.tactical = d.tacticalDiff ?? d
          if (currentProposal.value?.id === proposalId && (d.tacticalDiff ?? d)) {
            currentProposal.value = { ...currentProposal.value, tacticalDiff: d.tacticalDiff ?? d }
          }
        },
        impact: (d) => {
          planStream.value.impact = d.impactMap ?? d.items ?? d
          if (currentProposal.value?.id === proposalId && (d.impactMap ?? d.items)) {
            currentProposal.value = { ...currentProposal.value, impactMap: d.impactMap ?? d.items }
          }
        },
        architecture: (d) => {
          if (Array.isArray(d.architectureDecisions)) planStream.value.architecture = d.architectureDecisions
          else if (Array.isArray(d.decisions)) planStream.value.architecture = d.decisions
          else if (d.aspect) planStream.value.architecture.push(d)
          if (Array.isArray(d.constitutionGaps)) planStream.value.constitutionGaps = d.constitutionGaps
        },
        done: (d) => {
          planStream.value.active = false
          planStream.value.done = true
          if (d?.implementationPlan) plan.value = d.implementationPlan
          if (d?.implementationPlan?.constitutionGaps) planStream.value.constitutionGaps = d.implementationPlan.constitutionGaps
          if (d?.implementationPlan?.architectureDecisions) planStream.value.architecture = d.implementationPlan.architectureDecisions
          finish(resolve, d)
        },
        error: (d) => {
          planStream.value.active = false
          planStream.value.error = d?.message || translate('proposals.store.planGenerateFailed')
          finish(reject, new Error(d?.message || translate('proposals.store.planGenerateFailed')))
        },
      }
      Object.entries(handlers).forEach(([evt, h]) => {
        es.addEventListener(evt, (e) => { try { h(JSON.parse(e.data)) } catch {} })
      })
      es.onerror = async () => {
        if (settled || planStream.value.done) return
        // 사전조건 미충족(409) 여부를 비스트리밍 GET 으로 확인 — constitution_required 면 라우팅.
        try {
          const res = await fetch(`${BASE}/${proposalId}/stream/plan`, { method: 'GET', headers: { Accept: 'application/json' } })
          if (res.status === 409) {
            const body = await res.json().catch(() => ({}))
            // FastAPI 는 HTTPException detail 을 {detail: {...}} 로 감싼다 → detail.reason 우선.
            const reason = body?.detail?.reason ?? body?.reason
            if (reason === 'constitution_required') {
              planStream.value.constitutionRequired = true
              planStream.value.active = false
              finish(reject, Object.assign(new Error('constitution_required'), { reason: 'constitution_required' }))
              return
            }
          }
        } catch {}
        planStream.value.active = false
        finish(reject, new Error(translate('proposals.store.planConnectionDropped')))
      }
      _planEs = es
    })
  }

  function stopPlan() {
    if (_planEs) { _planEs.close(); _planEs = null }
    planStream.value.active = false
  }

  // 검토한 ImplementationPlan 을 확정 저장한다(Principle IV: confirm). constitutionHash/strategicVersion 스탬프.
  // 확정에 필요한 plan(필수) + tactical/impact 를 현재 스토어 상태에서 모아 보낸다 —
  // 빈 바디면 백엔드가 implementationPlan 누락(422)로 거절한다. tactical/impact 를 함께
  // 영속화해 새로고침 후에도 Plan 결과가 유지되게 한다.
  async function confirmPlan(proposalId) {
    const ip = (plan.value && typeof plan.value === 'object') ? plan.value : {}
    const tacticalDiff = planStream.value.tactical
      ?? currentProposal.value?.tacticalDiff ?? null
    const impactRaw = planStream.value.impact ?? currentProposal.value?.impactMap ?? null
    const impactMap = Array.isArray(impactRaw) ? impactRaw : (impactRaw?.items ?? null)

    const res = await fetch(`${BASE}/${proposalId}/plan/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ implementationPlan: ip, tacticalDiff, impactMap }),
    })
    if (!res.ok) {
      throw new Error(await _extractError(res, 'Plan 확정 실패'))
    }
    currentProposal.value = await res.json()
    _syncListItem(proposalId)
    await getPlan(proposalId)
    return currentProposal.value
  }

  function _syncListItem(proposalId) {
    const idx = proposals.value.findIndex(p => p.id === proposalId)
    if (idx >= 0 && currentProposal.value) proposals.value[idx] = currentProposal.value
  }

  // ---------------------------------------------------------------------------
  // 042 — Staged DDD decomposition (Detailed 모드)
  // ---------------------------------------------------------------------------

  // Simplified → Detailed DDD 업그레이드(plan 미확정 한정). 성공 시 currentProposal 갱신.
  async function upgradeMode(proposalId, decompositionMode = 'DETAILED_DDD') {
    const res = await fetch(`${BASE}/${proposalId}/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decompositionMode }),
    })
    if (!res.ok) throw new Error(await _extractError(res, 'Mode upgrade failed'))
    currentProposal.value = await res.json()
    _syncListItem(proposalId)
    return currentProposal.value
  }

  // 스코프 분류 SSE → stagePlan 제안(FR-009). resolve = 제안된 stagePlan.
  function subscribeToScope(proposalId) {
    stagedStream.value = { active: true, stage: 'SCOPE', logLines: [], stagePlan: null, artifact: null, conflicts: [], nextStage: null, done: false, error: null }
    return new Promise((resolve, reject) => {
      const es = new EventSource(`${BASE}/${proposalId}/stream/scope`)
      let settled = false
      const finish = (fn, arg) => { if (settled) return; settled = true; es.close(); _stagedEs = null; fn(arg) }
      const handlers = {
        phase: () => {},
        log_line: (d) => { stagedStream.value.logLines.push(d.text); if (stagedStream.value.logLines.length > 200) stagedStream.value.logLines.shift() },
        stage_plan: (d) => { stagedStream.value.stagePlan = d.stagePlan; stagedStream.value.active = false; finish(resolve, d.stagePlan) },
        error: (d) => { stagedStream.value.active = false; stagedStream.value.error = d.message; finish(reject, new Error(d.message || 'scope failed')) },
      }
      Object.entries(handlers).forEach(([evt, h]) => es.addEventListener(evt, (e) => { try { h(JSON.parse(e.data)) } catch {} }))
      es.onerror = () => { if (settled) return; stagedStream.value.active = false; finish(reject, new Error('scope connection dropped')) }
      _stagedEs = es
    })
  }

  // 아키텍트가 확정한 스테이지 플랜 저장(FR-010/FR-015).
  async function confirmStagePlan(proposalId, stages) {
    const res = await fetch(`${BASE}/${proposalId}/stage-plan/confirm`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stages }),
    })
    if (!res.ok) throw new Error(await _extractError(res, 'Stage plan confirm failed'))
    currentProposal.value = await res.json()
    _syncListItem(proposalId)
    return currentProposal.value
  }

  // 진행 중인 스테이지 실행을 (pid,stage) 별로 추적 — 컴포넌트가 언마운트돼도 SSE 는 살아 있고,
  // 재마운트 시 새 실행을 시작하지 않고 이 in-flight 실행에 다시 붙는다(재시작 금지).
  const _stageRuns = {}

  // 단일 스테이지 실행 SSE → artifact/conflicts. resolve = {artifact, conflicts, nextStage}.
  // feedback 가 있으면 그 단계를 피드백 반영본으로 재생성한다(단계별 유저 피드백).
  function subscribeToStage(proposalId, stage, feedback = null) {
    const key = `${proposalId}:${stage}`
    // 재생성(feedback)이 아니고 동일 단계 실행이 이미 진행 중이면 그대로 재사용 → 재시작 안 함.
    if (!feedback && _stageRuns[key]) return _stageRuns[key].promise
    // 재생성이면 기존 실행을 정리하고 새로 시작.
    if (_stageRuns[key]?.es) { try { _stageRuns[key].es.close() } catch {} ; delete _stageRuns[key] }

    stagedStream.value = { active: true, stage, logLines: [], stagePlan: stagedStream.value.stagePlan, artifact: null, conflicts: [], nextStage: null, done: false, error: null }
    const qs = feedback ? `?feedback=${encodeURIComponent(feedback)}` : ''
    const promise = new Promise((resolve, reject) => {
      const es = new EventSource(`${BASE}/${proposalId}/stream/stage/${stage.toLowerCase()}${qs}`)
      let settled = false
      const finish = (fn, arg) => { if (settled) return; settled = true; es.close(); _stagedEs = null; delete _stageRuns[key]; fn(arg) }
      const handlers = {
        phase: () => {},
        log_line: (d) => { stagedStream.value.logLines.push(d.text); if (stagedStream.value.logLines.length > 200) stagedStream.value.logLines.shift() },
        // 산출물 도착 즉시 초안으로 보존 → 검토 중 탭 이동/재마운트에도 사라지지 않음.
        artifact: (d) => { stagedStream.value.artifact = d.artifact; setStageDraft(proposalId, stage, d.artifact) },
        conflicts: (d) => { stagedStream.value.conflicts = d.conflicts || [] },
        done: (d) => { stagedStream.value.active = false; stagedStream.value.done = true; stagedStream.value.nextStage = d.nextStage; finish(resolve, { artifact: stagedStream.value.artifact, conflicts: stagedStream.value.conflicts, nextStage: d.nextStage }) },
        error: (d) => { stagedStream.value.active = false; stagedStream.value.error = d.message; finish(reject, new Error(d.message || 'stage failed')) },
      }
      Object.entries(handlers).forEach(([evt, h]) => es.addEventListener(evt, (e) => { try { h(JSON.parse(e.data)) } catch {} }))
      es.onerror = () => { if (settled || stagedStream.value.done) return; stagedStream.value.active = false; finish(reject, new Error('stage connection dropped')) }
      _stageRuns[key] = { es, promise: null }
    })
    if (_stageRuns[key]) _stageRuns[key].promise = promise
    else _stageRuns[key] = { es: null, promise }
    return promise
  }

  function stopStaged() {
    if (_stagedEs) { _stagedEs.close(); _stagedEs = null }
    stagedStream.value.active = false
  }

  // 편집된 산출물 확정(+충돌 해소). 409 unresolved_conflicts 면 conflicts 를 던진다(FR-019).
  async function confirmStage(proposalId, stage, artifact, conflictResolutions = []) {
    const res = await fetch(`${BASE}/${proposalId}/stage/${stage.toLowerCase()}/confirm`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artifact, conflictResolutions }),
    })
    if (res.status === 409) {
      const body = await res.json().catch(() => ({}))
      const err = new Error('unresolved_conflicts')
      err.reason = body?.detail?.reason
      err.conflicts = body?.detail?.conflicts || []
      throw err
    }
    if (!res.ok) throw new Error(await _extractError(res, 'Stage confirm failed'))
    currentProposal.value = await res.json()
    _syncListItem(proposalId)
    clearStageDraft(proposalId, stage)   // 확정 → 초안 정리
    return currentProposal.value
  }

  async function skipStage(proposalId, stage, reason = null) {
    const res = await fetch(`${BASE}/${proposalId}/stage/${stage.toLowerCase()}/skip`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    })
    if (!res.ok) throw new Error(await _extractError(res, 'Stage skip failed'))
    currentProposal.value = await res.json()
    _syncListItem(proposalId)
    clearStageDraft(proposalId, stage)
    return currentProposal.value
  }

  // 미확정 스테이지 초안 보존/복원/삭제.
  function _draftKey(pid, stage) { return `${pid}:${stage}` }
  function getStageDraft(pid, stage) { return stageDrafts.value[_draftKey(pid, stage)] || null }
  function setStageDraft(pid, stage, artifact) {
    if (artifact) stageDrafts.value[_draftKey(pid, stage)] = artifact
  }
  function clearStageDraft(pid, stage) { delete stageDrafts.value[_draftKey(pid, stage)] }

  // 스테이지 산출물을 표준 strategicDiff/tacticalDiff 로 수렴(FR-007). 이후 기존 plan 단계로.
  async function consolidateStaged(proposalId) {
    const res = await fetch(`${BASE}/${proposalId}/staged/consolidate`, { method: 'POST' })
    if (!res.ok) throw new Error(await _extractError(res, 'Consolidate failed'))
    currentProposal.value = await res.json()
    _syncListItem(proposalId)
    return currentProposal.value
  }

  // 042 — 라이프사이클: Intent 완료 = 제출(DRAFT→SUBMITTED=Plan 단계). 전략 산출물을
  // strategicDiff 로 수렴(Detailed; Simplified 는 no-op)한 뒤 제출한다.
  async function proceedToPlan(proposalId) {
    try { await consolidateStaged(proposalId) } catch (e) { /* 산출물 없으면 무시 */ }
    await submitProposal(proposalId)
    return currentProposal.value
  }

  return {
    proposals, currentProposal, loading, error,
    intentStream, sandboxStream, tasksStream, validationStream, testResults,
    constitution, plan, planStream, stagedStream, stageDrafts,
    getStageDraft, setStageDraft, clearStageDraft,
    fetchProposals, fetchProposal, createProposal, deleteProposal,
    subscribeToIntent, stopIntent, answerClarification, submitIntentFeedback,
    subscribeToTasks, stopTasks, fetchTasks,
    updateDiff, submitProposal,
    getConstitution,
    getPlan, runPlan, stopPlan, confirmPlan,
    upgradeMode, subscribeToScope, confirmStagePlan, subscribeToStage,
    stopStaged, confirmStage, skipStage, consolidateStaged, proceedToPlan,
    implementProposal, completeImplementation, fetchProgress,
    fetchTestResults, runValidation, subscribeToValidation, stopValidation,
    acceptProposal, destroyProposal, revokeProposal, retryMerge,
  }
})
