<script setup>
import { ref, computed, onMounted, onBeforeUnmount, onActivated, watch, inject, nextTick } from 'vue'
import ClaudeCodeTerminal from './ClaudeCodeTerminal.vue'
import FileTreePane from './FileTreePane.vue'
import FileEditorPane from './FileEditorPane.vue'
import SessionManagerPopover from './SessionManagerPopover.vue'
import { closeTerminalSession, fetchGlobalSkillsStatus, installGlobalSkills } from '../workspace.api.js'

const props = defineProps({
  workdir: { type: String, default: '' },
})

// Persistence keys for the last-opened project root and file.
const ROOT_KEY = 'claude_code_workspace_root'
const ACTIVE_PATH_KEY = 'claude_code_workspace_active_path'

function readPersisted(key) {
  try {
    return localStorage.getItem(key) || ''
  } catch {
    return ''
  }
}

// ─── Multi-session model ───
// Each session is an INDEPENDENT claude PTY terminal living on a worktree, all
// kept alive concurrently (v-show switching, never unmounted) so multiple
// proposals can implement in parallel without killing each other's session.
//   kind 'main'     → the user's project (claude_code_workspace_root)
//   kind 'proposal' → a proposal worktree (<projectRoot>/.sandbox/proposal/PRO)
//   kind 'shell'    → an extra manual shell the user opened with '＋'
const SESSIONS_KEY = 'claude_code_workspace_sessions'
const ACTIVE_SESSION_KEY = 'claude_code_workspace_active_session'

function basename(p) {
  if (!p) return '세션'
  const parts = String(p).replace(/\/+$/, '').split('/')
  return parts[parts.length - 1] || p
}

// worktree 경로에서 Proposal id를 추출한다. 중첩(.../proposal/PRO-005/.sandbox/
// proposal/PRO-032)이면 가장 안쪽(실제 Proposal)을 취한다.
function deriveProposalId(workdir) {
  if (!workdir) return null
  const m = String(workdir).match(/\/proposal\/(PRO-\d+)/g)
  if (!m || !m.length) return null
  return m[m.length - 1].split('/').pop()
}
// 한 Proposal에는 worktree 경로가 바뀌어도 항상 하나의 세션만 — id를 proposalId로
// 고정해 경로 변경(오염 경로 → 정상 경로)이 중복 탭/죽은 경로를 만들지 않게 한다.
function proposalSid(pid) {
  return `proposal:${pid}`
}
function sandboxDepth(p) {
  return (String(p || '').match(/\.sandbox\//g) || []).length
}
// 같은 Proposal의 중복 세션을 하나로 접는다. worktree가 더 얕은(중첩 없는) 쪽을
// 정상으로 보고 유지한다. 과거(경로 키) 세션도 proposalId 기준으로 흡수한다.
function dedupeProposalSessions(list) {
  const byPid = new Map()
  const out = []
  for (const s of list) {
    if (s.kind !== 'proposal') { out.push(s); continue }
    const pid = s.proposalId || deriveProposalId(s.workdir)
    if (!pid) { out.push(s); continue }
    const prev = byPid.get(pid)
    if (!prev) {
      const canon = { ...s, id: proposalSid(pid), proposalId: pid }
      byPid.set(pid, canon)
      out.push(canon)
    } else if (sandboxDepth(s.workdir) < sandboxDepth(prev.workdir)) {
      // 더 깨끗한(중첩 없는) 경로로 교체
      prev.workdir = s.workdir
      prev.epoch = Math.max(prev.epoch || 0, s.epoch || 0)
    }
  }
  return out
}

function loadSessions() {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY)
    const arr = raw ? JSON.parse(raw) : null
    if (Array.isArray(arr)) {
      // initialCommand is intentionally NOT restored — a reload must not re-run
      // a proposal's implement instruction; restored sessions just reconnect.
      // epoch IS restored so the backend session_id (id#epoch) matches the live
      // PTY and a reload re-attaches to it instead of spawning a fresh claude.
      const mapped = arr
        .filter((s) => s && s.id)
        .map((s) => ({ id: s.id, label: s.label || basename(s.workdir), workdir: s.workdir || '', kind: s.kind || 'shell', activePath: null, initialCommand: '', epoch: s.epoch || 0, proposalId: s.proposalId || (s.kind === 'proposal' ? deriveProposalId(s.workdir) : null) }))
      return dedupeProposalSessions(mapped)
    }
  } catch {}
  return []
}

const sessions = ref(loadSessions())
const activeSessionId = ref(readPersisted(ACTIVE_SESSION_KEY) || null)

// Ensure a 'main' session exists for the persisted/incoming project root.
const _initialRoot = props.workdir || readPersisted(ROOT_KEY)
;(function ensureMainSession() {
  let main = sessions.value.find((s) => s.kind === 'main')
  if (_initialRoot) {
    if (!main) {
      main = { id: 'main', label: '프로젝트', workdir: _initialRoot, kind: 'main', activePath: null, initialCommand: '', epoch: 0 }
      sessions.value.unshift(main)
    } else if (!main.workdir) {
      main.workdir = _initialRoot
    }
  }
  if (!activeSessionId.value || !sessions.value.find((s) => s.id === activeSessionId.value)) {
    activeSessionId.value = (main && main.id) || sessions.value[0]?.id || null
  }
})()

const activeSession = computed(() => sessions.value.find((s) => s.id === activeSessionId.value) || null)
const mainSession = computed(() => sessions.value.find((s) => s.kind === 'main') || null)

// activeRoot drives the file tree + editor → they follow the active session's worktree.
const activeRoot = computed(() => activeSession.value?.workdir || '')

// Per-session open file (proposal files are transient; main session's is persisted).
const persistedActivePath = readPersisted(ACTIVE_PATH_KEY)
if (mainSession.value && persistedActivePath && mainSession.value.workdir) {
  mainSession.value.activePath = persistedActivePath
}
const activePath = computed({
  get: () => activeSession.value?.activePath ?? null,
  set: (v) => { if (activeSession.value) activeSession.value.activePath = v },
})

// 029 — appWorkdirRef (App.vue's claudeCodeWorkdir) tracks ONLY the MAIN session
// workdir: it is the project root used for cross-feature path resolution
// (InspectorPanel source viewer) and as the default projectRoot for new proposals.
// Proposal worktree sessions must NOT overwrite it.
const appWorkdirRef = inject('claudeCodeWorkdir', null)
function syncMainRoot() {
  const root = mainSession.value?.workdir || ''
  try {
    if (root) localStorage.setItem(ROOT_KEY, root)
  } catch {}
  if (appWorkdirRef && root && appWorkdirRef.value !== root) appWorkdirRef.value = root
}
syncMainRoot()

function persistSessions() {
  try {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(
      sessions.value.map((s) => ({ id: s.id, label: s.label, workdir: s.workdir, kind: s.kind, epoch: s.epoch || 0, proposalId: s.proposalId || null })),
    ))
    if (activeSessionId.value) localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId.value)
  } catch {}
}

watch(sessions, persistSessions, { deep: true })
watch(() => mainSession.value?.workdir, syncMainRoot)
watch(activeSessionId, () => {
  persistSessions()
  // The newly-shown terminal had display:none (0px) while hidden — re-fit it.
  nextTick(() => terminalRefs[activeSessionId.value]?.refit?.())
})

watch(activePath, (v) => {
  if (activeSession.value?.kind !== 'main') return
  try {
    if (v) localStorage.setItem(ACTIVE_PATH_KEY, v)
    else localStorage.removeItem(ACTIVE_PATH_KEY)
  } catch {}
})

// React to App.vue's claudeCodeWorkdir prop (main project changes from wizard / cold load).
watch(
  () => props.workdir,
  (w) => {
    if (!w) return
    let main = mainSession.value
    if (!main) {
      main = { id: 'main', label: '프로젝트', workdir: w, kind: 'main', activePath: null, initialCommand: '', epoch: 0 }
      sessions.value.unshift(main)
    } else if (main.workdir !== w) {
      main.workdir = w
      main.activePath = null
    }
    activeSessionId.value = main.id
  },
)

// ─── Session controls ───
const terminalRefs = {}
function setTerminalRef(id, el) {
  if (el) terminalRefs[id] = el
  else delete terminalRefs[id]
}
function setActiveSession(id) {
  if (sessions.value.find((s) => s.id === id)) activeSessionId.value = id
}
function closeSession(id) {
  const idx = sessions.value.findIndex((s) => s.id === id)
  if (idx < 0) return
  const wasActive = activeSessionId.value === id
  // ws 종료만으로는 백엔드 PTY가 살아있으므로(새로고침 재어태치용), 명시적으로 종료한다.
  closeTerminalSession(backendId(sessions.value[idx]))
  sessions.value.splice(idx, 1) // unmount → ws closes
  delete terminalRefs[id]
  if (wasActive) {
    activeSessionId.value = mainSession.value?.id || sessions.value[0]?.id || null
  }
}
function addShellSession() {
  const base = mainSession.value?.workdir || ''
  const id = `shell-${Date.now()}`
  sessions.value.push({ id, label: base ? basename(base) : '셸', workdir: base, kind: 'shell', activePath: null, initialCommand: '', epoch: 0 })
  activeSessionId.value = id
}

// ─── Session manager (백엔드 권위 기반 프로세스 정리) ───
const showSessionManager = ref(false)

// 매니저가 백엔드 세션(backendId = id#epoch)을 종료하면, 그 세션을 가리키던 로컬 탭도
// 함께 제거해 "죽은 탭"이 남지 않게 한다. payload 는 단일 id 또는 id 배열.
function onManagerChanged(payload) {
  const killed = new Set(Array.isArray(payload) ? payload : [payload])
  for (const s of [...sessions.value]) {
    if (killed.has(backendId(s))) closeSession(s.id)
  }
}

// 백엔드 PTY 세션 레지스트리 키 — 논리 id(worktree 경로 등) + epoch.
// epoch는 "다시 구현하기"로 세션을 재시작할 때 증가시켜, 종료된 옛 세션과 충돌
// 없이 새 PTY를 띄우게 한다(새로고침 재어태치를 위해 persist된다).
function backendId(s) {
  return `${s.id}#${s.epoch || 0}`
}

// ─── Layout state ───
const TREE_KEY_WIDTH = 'claude_code_workspace_tree_width'
const EDITOR_KEY_WIDTH = 'claude_code_workspace_editor_width'
const TREE_KEY_COLLAPSED = 'claude_code_workspace_tree_collapsed'
const EDITOR_KEY_COLLAPSED = 'claude_code_workspace_editor_collapsed'

const treeWidth = ref(280)
const editorWidth = ref(560)
const treeCollapsed = ref(false)
const editorCollapsed = ref(false)
const savedTreeWidth = ref(280)
const savedEditorWidth = ref(560)

const TREE_MIN = 180
const EDITOR_MIN = 320
const TERMINAL_MIN = 320

let activeResizer = null

function startResize(which, e) {
  activeResizer = which
  e.preventDefault()
  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
}

function onResize(e) {
  if (!activeResizer) return
  const container = document.querySelector('.ccw-root')
  if (!container) return
  const rect = container.getBoundingClientRect()
  const total = rect.width
  if (activeResizer === 'tree') {
    if (treeCollapsed.value) return
    let next = Math.round(e.clientX - rect.left)
    next = Math.max(TREE_MIN, next)
    // Keep enough room for editor + terminal.
    const reserved = (editorCollapsed.value ? 0 : EDITOR_MIN) + TERMINAL_MIN + 8
    next = Math.min(next, total - reserved)
    treeWidth.value = next
    persistWidths()
  } else if (activeResizer === 'editor') {
    if (editorCollapsed.value) return
    const treeNow = treeCollapsed.value ? 0 : treeWidth.value
    let next = Math.round(e.clientX - rect.left - treeNow)
    next = Math.max(EDITOR_MIN, next)
    next = Math.min(next, total - treeNow - TERMINAL_MIN - 8)
    editorWidth.value = next
    persistWidths()
  }
}

function stopResize() {
  activeResizer = null
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
}

function persistWidths() {
  try {
    localStorage.setItem(TREE_KEY_WIDTH, String(treeWidth.value))
    localStorage.setItem(EDITOR_KEY_WIDTH, String(editorWidth.value))
  } catch {}
}

function persistCollapsed() {
  try {
    localStorage.setItem(TREE_KEY_COLLAPSED, String(treeCollapsed.value))
    localStorage.setItem(EDITOR_KEY_COLLAPSED, String(editorCollapsed.value))
  } catch {}
}

function toggleTree() {
  if (treeCollapsed.value) {
    treeCollapsed.value = false
    treeWidth.value = savedTreeWidth.value
  } else {
    savedTreeWidth.value = treeWidth.value
    treeCollapsed.value = true
  }
  persistCollapsed()
  persistWidths()
}

function toggleEditor() {
  if (editorCollapsed.value) {
    editorCollapsed.value = false
    editorWidth.value = savedEditorWidth.value
  } else {
    savedEditorWidth.value = editorWidth.value
    editorCollapsed.value = true
    activePath.value = null  // Nothing useful to keep open when the pane is gone
  }
  persistCollapsed()
  persistWidths()
}

// ─── Unsaved-changes guard ───
const editorRef = ref(null)
const treeRef = ref(null)

// Send a command into the ACTIVE session's terminal as if the user typed it.
function sendTerminalCommand(command) {
  terminalRefs[activeSessionId.value]?.sendInput(command + '\r')
}

defineExpose({ sendTerminalCommand })

// Legacy cross-component dispatch (Changes → Code tab): send into the active session.
function _onTerminalSend(e) {
  const cmd = e.detail?.command
  if (cmd) sendTerminalCommand(cmd)
}

// Open/activate a session for a workdir, optionally running a command.
//   kind 'main'     → reuse the single main-project session (Changes/Inspector flow)
//   kind 'proposal' → one persistent session per proposal worktree (039 multi-session)
// A NEW proposal session passes the command as the terminal's initialCommand, which
// runs ~6s after `claude` starts. An EXISTING session just gets the command typed in.
function _onTerminalOpen(e) {
  const { workdir, command, label, kind, restart } = e.detail || {}
  const k = kind || 'proposal'

  if (k === 'main') {
    let main = mainSession.value
    if (!main) {
      // 새 메인 세션: 명령을 initialCommand 로 실어 보낸다 → 터미널이 claude 부팅 후
      // (~6s) 실행. nextTick sendInput 은 claude 준비 전이라 실행이 누락되던 콜드스타트
      // 레이스(C6)를 피한다.
      main = { id: 'main', label: '프로젝트', workdir: workdir || '', kind: 'main', activePath: null, initialCommand: command || '', epoch: 0 }
      sessions.value.unshift(main)
      activeSessionId.value = main.id
      return
    }
    if (workdir && main.workdir !== workdir) {
      // 다른 프로젝트로 핸드오프(PRD 열기·프로젝트 전환 등): PTY 는 claude 를 직접
      // 실행하므로 셸 cd 로 못 옮긴다 → 기존 PTY 종료 + epoch++ 로 새 cwd 에서 respawn
      // 해야 실제 터미널이 새 프로젝트로 간다(C7 핸드오프 경로). 명령은 initialCommand 로.
      closeTerminalSession(backendId(main))
      main.epoch = (main.epoch || 0) + 1
      main.workdir = workdir
      main.activePath = null
      main.initialCommand = command || ''
      activeSessionId.value = main.id
      return
    }
    // 같은 workdir 의 기존 세션: claude 가 이미 떠 있으므로 명령만 주입.
    activeSessionId.value = main.id
    if (command) nextTick(() => terminalRefs[main.id]?.sendInput(command + '\r'))
    return
  }

  // proposal session — keyed by Proposal id(경로가 아니라)so 경로가 바뀌어도(오염 →
  // 정상) 중복 탭/죽은 경로가 생기지 않는다. 과거 경로-키 세션도 proposalId로 흡수.
  if (!workdir) {
    if (command) sendTerminalCommand(command)
    return
  }
  const pid = e.detail?.proposalId || deriveProposalId(workdir)
  const sid = pid ? proposalSid(pid) : workdir
  const existing = sessions.value.find(
    (s) => s.kind === 'proposal' && (s.id === sid || (pid && (s.proposalId || deriveProposalId(s.workdir)) === pid)),
  )

  // 재구현: 기존 세션을 종료(백엔드 PTY kill)한 뒤 epoch를 올려 새 셀로 재생성.
  // worktree가 재생성되므로 이전 claude(삭제된 디렉터리 cwd)를 살려두면 안 된다.
  // 새 backendId(id#epoch)라 종료 DELETE와 재연결 사이 레이스가 없다.
  if (existing && restart) {
    const nextEpoch = (existing.epoch || 0) + 1
    closeSession(existing.id)
    nextTick(() => {
      sessions.value.push({ id: sid, label: label || pid || basename(workdir), workdir, kind: 'proposal', activePath: null, initialCommand: command || '', epoch: nextEpoch, proposalId: pid })
      activeSessionId.value = sid
    })
    return
  }

  if (existing) {
    // 경로가 정정되었으면(중첩 → 정상) 세션 id/workdir를 정규 값으로 갱신 →
    // 파일 트리/에디터(activeRoot)가 살아있는 worktree를 따라간다.
    existing.id = sid
    existing.proposalId = pid
    if (workdir && existing.workdir !== workdir) {
      existing.workdir = workdir
      existing.activePath = null
    }
    activeSessionId.value = sid
    if (command) nextTick(() => terminalRefs[sid]?.sendInput(command + '\r'))
  } else {
    sessions.value.push({ id: sid, label: label || pid || basename(workdir), workdir, kind: 'proposal', activePath: null, initialCommand: command || '', epoch: 0, proposalId: pid })
    activeSessionId.value = sid
  }
}

// 홈(~/.claude/skills) 스킬 설치 점검 — Code 탭 진입(최초 mount + KeepAlive 재활성)
// 시 1회. 서버가 같은 세션 동안 점검 결과를 기억하므로, 한 번 설치 확인/완료되면
// 이후 진입에서는 즉시 통과한다. 이 in-flight 가드는 동시 호출만 막는다.
let _globalSkillsChecking = false
async function checkGlobalSkills() {
  if (_globalSkillsChecking) return
  _globalSkillsChecking = true
  try {
    const st = await fetchGlobalSkillsStatus()
    if (!st || !st.needInstall) return // verified or nothing missing
    const list = (st.missing || []).join(', ')
    const ok = window.confirm(
      `이 프로젝트의 Claude 스킬이 홈 폴더(~/.claude/skills)에 설치되어 있지 않습니다.\n` +
      `인터랙티브 Claude Code 셀에서 robo 슬래시 커맨드를 쓰려면 설치가 필요합니다.\n\n` +
      `누락된 스킬 ${st.missing?.length ?? 0}개: ${list}\n\n지금 설치하시겠습니까?`,
    )
    if (!ok) return
    const res = await installGlobalSkills()
    window.alert(`스킬 ${res.installed?.length ?? 0}개를 ~/.claude/skills 에 설치했습니다.`)
  } catch (e) {
    // 비치명적 — 점검/설치 실패해도 Code 탭 사용은 계속 가능.
    console.warn('[claude-code] global skills check failed', e)
  } finally {
    _globalSkillsChecking = false
  }
}

onMounted(() => {
  window.addEventListener('claude-terminal-send', _onTerminalSend)
  window.addEventListener('claude-terminal-open', _onTerminalOpen)
  checkGlobalSkills()
})

onActivated(() => {
  // KeepAlive: process any queued command when this tab is re-activated
  // (the event may have fired before onActivated, so re-check is a no-op)
  checkGlobalSkills()
})

onBeforeUnmount(() => {
  window.removeEventListener('claude-terminal-send', _onTerminalSend)
  window.removeEventListener('claude-terminal-open', _onTerminalOpen)
})

function isDirty() {
  // The defineExpose'd `dirty` is a ref; .value gets the boolean.
  const d = editorRef.value?.dirty
  return !!(d && d.value)
}

async function confirmDiscardOrSave(message) {
  if (!isDirty()) return 'continue'
  // Use window.confirm as v1 minimum: OK = save then continue, Cancel = abort.
  // For the discard option we add a second prompt only when saving fails.
  const wantSave = window.confirm(`${message}\n\n저장 후 진행하려면 OK, 취소하려면 Cancel을 누르세요.`)
  if (!wantSave) {
    const discard = window.confirm('변경사항을 버리시겠습니까? OK = 버리고 진행, Cancel = 머무름.')
    return discard ? 'discard' : 'cancel'
  }
  try {
    await editorRef.value.triggerSave()
    if (isDirty()) {
      // Save failed (e.g. 409 conflict left buffer dirty).
      window.alert('저장에 실패했습니다. 변경사항이 유지됩니다.')
      return 'cancel'
    }
    return 'continue'
  } catch {
    window.alert('저장 중 오류가 발생했습니다. 변경사항이 유지됩니다.')
    return 'cancel'
  }
}

async function onOpenFile(path) {
  if (path === activePath.value) return
  if (isDirty()) {
    const decision = await confirmDiscardOrSave('현재 파일에 저장되지 않은 변경사항이 있습니다.')
    if (decision === 'cancel') return
  }
  activePath.value = path
}

function onTreeExternalCheck() {
  editorRef.value?.checkExternalModification()
}

// Backstop for the file tree's live SSE watch: when the active terminal's
// output settles (claude likely finished writing), re-list the tree. Debounced
// so the SSE-driven refresh and this don't pile up. Harmless if the SSE already
// caught the change — it's just a cheap re-list of the loaded directories.
let activityRefreshTimer = null
function onTerminalActivity() {
  if (activityRefreshTimer) clearTimeout(activityRefreshTimer)
  activityRefreshTimer = setTimeout(() => {
    activityRefreshTimer = null
    treeRef.value?.refresh()
  }, 300)
}

function isUnderPath(target, parent) {
  if (!target || !parent) return false
  return target === parent || target.startsWith(parent + '/')
}

function rewriteActivePath(fromPath, toPath) {
  // Called when a rename/move succeeded. If the open file is the moved
  // entry itself or sits inside a moved directory, rewrite its path so
  // the editor keeps tracking the same content.
  const cur = activePath.value
  if (!cur) return
  if (cur === fromPath) {
    activePath.value = toPath
  } else if (cur.startsWith(fromPath + '/')) {
    activePath.value = toPath + cur.slice(fromPath.length)
  }
}

function onTreeRenamed({ fromPath, toPath }) {
  rewriteActivePath(fromPath, toPath)
}

function onTreeMoved({ fromPath, toPath }) {
  rewriteActivePath(fromPath, toPath)
}

function onTreeDeleted({ path }) {
  if (isUnderPath(activePath.value, path)) {
    activePath.value = null
  }
}

function onEditorDeleted({ path }) {
  // Editor-initiated delete: close the buffer and refresh the tree so the
  // removed entry disappears from the left pane.
  if (isUnderPath(activePath.value, path)) {
    activePath.value = null
  }
  treeRef.value?.refresh()
}

function onTerminalWorkdirPicked(path) {
  // The folder picker lives in the active terminal — repoint THAT session.
  const s = activeSession.value
  if (!path || !s || s.workdir === path) return
  // PTY는 셸이 아니라 claude를 직접 execvpe로 띄우므로 셸 `cd`로 옮길 수 없다 →
  // 새 폴더에서 터미널을 다시 띄워야(respawn) 실제 cwd가 따라온다(C7/I16).
  // 현재 claude 세션/스크롤백은 사라지므로 사용자 확인을 받는다.
  const ok = window.confirm(
    `터미널을 새 폴더로 다시 시작할까요?\n\n${path}\n\n현재 터미널 세션(대화·스크롤백)은 종료됩니다.`,
  )
  if (!ok) return
  // 기존 PTY를 명시적으로 종료하고 epoch를 올려, key가 바뀐 ClaudeCodeTerminal이
  // remount → 새 cwd + 새 backendId(id#epoch)로 fresh PTY를 띄운다.
  closeTerminalSession(backendId(s))
  s.epoch = (s.epoch || 0) + 1
  s.workdir = path
  s.label = s.kind === 'main' ? '프로젝트' : basename(path)
  s.activePath = null
}

// Tab-switch-away guard via the injected activeTab ref.
const activeTab = inject('activeTab', null)
let switchingAway = false
watch(
  () => (activeTab ? activeTab.value : null),
  async (newTab, oldTab) => {
    if (oldTab === 'Code' && newTab !== 'Code' && isDirty()) {
      if (switchingAway) return
      switchingAway = true
      try {
        const decision = await confirmDiscardOrSave('Code 워크스페이스를 떠나려고 합니다.')
        if (decision === 'cancel' && activeTab) {
          activeTab.value = 'Code'  // Snap back.
        }
      } finally {
        switchingAway = false
      }
    }
  },
)

// Browser-level beforeunload guard.
function onBeforeUnload(e) {
  if (isDirty()) {
    e.preventDefault()
    e.returnValue = ''
    return ''
  }
}

onMounted(() => {
  try {
    const tw = Number(localStorage.getItem(TREE_KEY_WIDTH))
    if (Number.isFinite(tw) && tw >= TREE_MIN) {
      treeWidth.value = tw
      savedTreeWidth.value = tw
    }
    const ew = Number(localStorage.getItem(EDITOR_KEY_WIDTH))
    if (Number.isFinite(ew) && ew >= EDITOR_MIN) {
      editorWidth.value = ew
      savedEditorWidth.value = ew
    }
    if (localStorage.getItem(TREE_KEY_COLLAPSED) === 'true') treeCollapsed.value = true
    if (localStorage.getItem(EDITOR_KEY_COLLAPSED) === 'true') editorCollapsed.value = true
  } catch {}
  window.addEventListener('beforeunload', onBeforeUnload)
})

onBeforeUnmount(() => {
  stopResize()
  if (activityRefreshTimer) {
    clearTimeout(activityRefreshTimer)
    activityRefreshTimer = null
  }
  window.removeEventListener('beforeunload', onBeforeUnload)
})
</script>

<template>
  <div class="ccw-root">
    <!-- Left: file tree -->
    <div
      v-if="!treeCollapsed"
      class="ccw-pane ccw-tree"
      :style="{ width: treeWidth + 'px' }"
    >
      <FileTreePane
        ref="treeRef"
        :root="activeRoot"
        :active-path="activePath"
        @open="onOpenFile"
        @external-check="onTreeExternalCheck"
        @renamed="onTreeRenamed"
        @moved="onTreeMoved"
        @deleted="onTreeDeleted"
      />
    </div>
    <button
      class="ccw-toggle ccw-toggle-tree"
      :class="{ 'is-collapsed': treeCollapsed }"
      :title="treeCollapsed ? '파일 트리 펼치기' : '파일 트리 접기'"
      @click="toggleTree"
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline v-if="treeCollapsed" points="9 18 15 12 9 6"></polyline>
        <polyline v-else points="15 18 9 12 15 6"></polyline>
      </svg>
    </button>
    <div
      v-if="!treeCollapsed"
      class="ccw-resizer"
      @mousedown="startResize('tree', $event)"
      title="너비 조절"
    ></div>

    <!-- Middle: editor -->
    <div
      v-if="!editorCollapsed"
      class="ccw-pane ccw-editor"
      :style="{ width: editorWidth + 'px' }"
    >
      <FileEditorPane
        ref="editorRef"
        :root="activeRoot"
        :path="activePath"
        @deleted="onEditorDeleted"
      />
    </div>
    <button
      class="ccw-toggle ccw-toggle-editor"
      :class="{ 'is-collapsed': editorCollapsed }"
      :title="editorCollapsed ? '에디터 펼치기' : '에디터 접기'"
      @click="toggleEditor"
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline v-if="editorCollapsed" points="9 18 15 12 9 6"></polyline>
        <polyline v-else points="15 18 9 12 15 6"></polyline>
      </svg>
    </button>
    <div
      v-if="!editorCollapsed"
      class="ccw-resizer"
      @mousedown="startResize('editor', $event)"
      title="너비 조절"
    ></div>

    <!-- Right: Claude Code terminal(s) — one persistent session per worktree -->
    <div class="ccw-pane ccw-terminal">
      <div class="ccw-session-tabs">
        <button
          v-for="s in sessions"
          :key="s.id"
          class="ccw-session-tab"
          :class="{ 'is-active': s.id === activeSessionId, [`is-${s.kind}`]: true }"
          :title="s.workdir || '(작업 경로 미설정)'"
          @click="setActiveSession(s.id)"
        >
          <span class="ccw-session-tab__dot" :class="`dot-${s.kind}`"></span>
          <span class="ccw-session-tab__label">{{ s.label }}</span>
          <span class="ccw-session-tab__close" title="세션 종료" @click.stop="closeSession(s.id)">×</span>
        </button>
        <button class="ccw-session-add" title="새 셸 세션" @click="addShellSession">＋</button>
        <button class="ccw-session-manage" title="세션 매니저 — 실행 중인 claude 프로세스 정리"
                @click="showSessionManager = true">⚙ 세션</button>
      </div>
      <div class="ccw-terminals">
        <div
          v-for="s in sessions"
          :key="`${s.id}#${s.epoch || 0}`"
          v-show="s.id === activeSessionId"
          class="ccw-terminal-host"
        >
          <ClaudeCodeTerminal
            :ref="(el) => setTerminalRef(s.id, el)"
            :workdir="s.workdir"
            :session-id="backendId(s)"
            :initial-command="s.initialCommand"
            :is-active="s.id === activeSessionId"
            @workdir-picked="onTerminalWorkdirPicked"
            @activity="onTerminalActivity"
          />
        </div>
        <div v-if="!sessions.length" class="ccw-no-session">
          세션이 없습니다. <strong>＋</strong>로 새 셸을 열거나 Proposal에서 "구현 시작"을 누르세요.
        </div>
      </div>
    </div>

    <SessionManagerPopover
      v-if="showSessionManager"
      @close="showSessionManager = false"
      @changed="onManagerChanged"
    />
  </div>
</template>

<style scoped>
.ccw-root {
  display: flex;
  flex-direction: row;
  width: 100%;
  height: 100%;
  background: var(--ccw-bg);
  overflow: hidden;
}

.ccw-pane {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}

.ccw-tree {
  border-right: 1px solid var(--ccw-border);
}

.ccw-editor {
  border-right: 1px solid var(--ccw-border);
}

.ccw-terminal {
  flex: 1;
  min-width: 320px;
}

/* ─── Multi-session tabs ─── */
.ccw-session-tabs {
  display: flex;
  align-items: stretch;
  gap: 2px;
  padding: 4px 6px 0;
  background: var(--ccw-bg-elevated);
  border-bottom: 1px solid var(--ccw-border);
  overflow-x: auto;
  flex-shrink: 0;
}
.ccw-session-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 220px;
  padding: 5px 8px;
  background: transparent;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  color: var(--ccw-text-dim);
  font-size: 0.72rem;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.12s, color 0.12s;
}
.ccw-session-tab:hover { background: var(--ccw-hover); color: var(--ccw-text); }
.ccw-session-tab.is-active {
  background: var(--ccw-bg);
  border-color: var(--ccw-border);
  color: var(--ccw-text);
}
.ccw-session-tab__label { overflow: hidden; text-overflow: ellipsis; }
.ccw-session-tab__dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-main { background: var(--ccw-purple, #bb9af7); }
.dot-proposal { background: var(--ccw-green, #9ece6a); }
.dot-shell { background: var(--ccw-text-dim, #888); }
.ccw-session-tab__close {
  display: inline-flex; align-items: center; justify-content: center;
  width: 14px; height: 14px; border-radius: 3px; font-size: 0.95rem; line-height: 1;
  color: var(--ccw-text-dim);
}
.ccw-session-tab__close:hover { background: var(--ccw-active); color: var(--ccw-text); }
.ccw-session-add {
  padding: 4px 9px; background: transparent; border: none;
  color: var(--ccw-text-dim); font-size: 0.95rem; cursor: pointer; border-radius: 4px;
  flex-shrink: 0;
}
.ccw-session-add:hover { background: var(--ccw-hover); color: var(--ccw-text); }
.ccw-session-manage {
  margin-left: auto; padding: 4px 9px; background: transparent; border: none;
  color: var(--ccw-text-dim); font-size: 0.78rem; cursor: pointer; border-radius: 4px;
  flex-shrink: 0; white-space: nowrap;
}
.ccw-session-manage:hover { background: var(--ccw-hover); color: var(--ccw-text); }
.ccw-terminals { flex: 1; position: relative; overflow: hidden; }
.ccw-terminal-host { width: 100%; height: 100%; }
.ccw-no-session {
  display: flex; align-items: center; justify-content: center; height: 100%;
  color: var(--ccw-text-dim); font-size: 0.8rem; padding: 16px; text-align: center;
}

.ccw-resizer {
  width: 4px;
  cursor: col-resize;
  background: transparent;
  flex-shrink: 0;
  transition: background 0.15s ease;
}

.ccw-resizer:hover {
  background: var(--ccw-accent);
}

.ccw-toggle {
  width: 18px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--ccw-bg-elevated);
  border: none;
  color: var(--ccw-text-dim);
  cursor: pointer;
  flex-shrink: 0;
  border-right: 1px solid var(--ccw-border);
  padding: 0;
}

.ccw-toggle:hover {
  background: var(--ccw-hover);
  color: var(--ccw-text);
}
</style>
