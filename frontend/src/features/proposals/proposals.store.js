import { defineStore } from 'pinia'
import { ref } from 'vue'

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
  let _intentEs = null
  let _tasksEs = null
  let _validateEs = null
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

  async function createProposal(originalPrompt, title = null) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`${BASE}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ originalPrompt, title }),
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
        error: (d) => { tasksStream.value.active = false; tasksStream.value.error = d.message; finish(reject, new Error(d.message || '작업 분해 실패')) },
      }
      Object.entries(handlers).forEach(([evt, h]) => {
        es.addEventListener(evt, (e) => { try { h(JSON.parse(e.data)) } catch {} })
      })
      es.onerror = () => {
        tasksStream.value.active = false
        // 정상 done 이후의 close가 아니면 실패로 처리한다.
        finish(reject, new Error('작업 분해 연결이 끊겼습니다.'))
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
      if (!res.ok) throw new Error(`Update diff failed: ${res.status}`)
      currentProposal.value = await res.json()
    } catch (e) {
      error.value = e.message
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
          const err = new Error(d.message || '대상 프로젝트가 Git 저장소가 아닙니다.')
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
          finish(reject, new Error(d.message || '검증 실패'))
        },
      }
      Object.entries(handlers).forEach(([evt, h]) => {
        es.addEventListener(evt, (e) => { try { h(JSON.parse(e.data)) } catch {} })
      })
      es.onerror = () => {
        // 사용자가 중지(close)한 경우엔 settled 처리가 끝나 onerror가 무시된다.
        if (settled) return
        validationStream.value.active = false
        finish(reject, new Error('검증 연결이 끊겼습니다.'))
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

  function _syncListItem(proposalId) {
    const idx = proposals.value.findIndex(p => p.id === proposalId)
    if (idx >= 0 && currentProposal.value) proposals.value[idx] = currentProposal.value
  }

  return {
    proposals, currentProposal, loading, error,
    intentStream, sandboxStream, tasksStream, validationStream, testResults,
    fetchProposals, fetchProposal, createProposal,
    subscribeToIntent, stopIntent, answerClarification, submitIntentFeedback,
    subscribeToTasks, stopTasks, fetchTasks,
    updateDiff, submitProposal,
    implementProposal, completeImplementation, fetchProgress,
    fetchTestResults, runValidation, subscribeToValidation, stopValidation,
    acceptProposal, destroyProposal, revokeProposal, retryMerge,
  }
})
