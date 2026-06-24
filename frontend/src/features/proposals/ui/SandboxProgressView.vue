<template>
  <div class="sandbox-view">
    <!-- Sandbox metadata -->
    <div class="sandbox-meta" v-if="proposal?.sandboxBranch">
      <span class="meta-label">{{ t('proposals.sandbox.branchLabel') }}</span>
      <code>{{ proposal.sandboxBranch }}</code>
      <span class="meta-label">{{ t('proposals.sandbox.pathLabel') }}</span>
      <code>{{ proposal.sandboxWorktreePath }}</code>
      <span :class="['sandbox-status', `sandbox-status--${(proposal.sandboxStatus || '').toLowerCase()}`]">
        {{ proposal.sandboxStatus }}
      </span>
    </div>

    <!-- 대상 프로젝트(Claude Code 탭) 경로 안내 -->
    <div class="project-root-line">
      <span class="meta-label">{{ t('proposals.sandbox.targetProjectLabel') }}</span>
      <code v-if="projectRoot">{{ projectRoot }}</code>
      <span v-else class="project-root-missing">
        ⚠ {{ t('proposals.sandbox.projectRootMissing') }}
      </span>
    </div>

    <!-- 시작 전 안내 (SUBMITTED) -->
    <p v-if="proposal?.status === 'SUBMITTED'" class="sandbox-empty">
      {{ t('proposals.sandbox.submittedGuidePre') }} <strong>{{ t('proposals.sandbox.submittedGuideTaskList') }}</strong>{{ t('proposals.sandbox.submittedGuideMid') }}
      <code>{{ branchPreview }}</code>{{ t('proposals.sandbox.submittedGuidePost') }}
    </p>

    <!-- 작업 분해 — 셸이 아니라 proposal 쪽에서 미리 작업을 뽑아 보여준다.
         SUBMITTED 미리보기 + "구현하기"가 작업 목록을 즉석 생성하는 과정도 노출. -->
    <section v-if="proposal?.status === 'SUBMITTED' || tasksStream.active" class="tasks-block">
      <header class="progress-head">
        <span class="progress-title">{{ t('proposals.sandbox.taskListTitle') }}</span>
        <span v-if="tasks.length" class="progress-badge progress-badge--done">{{ t('proposals.sandbox.taskCountBadge', { n: tasks.length }) }}</span>
        <span v-else-if="tasksStream.active" class="progress-badge progress-badge--running">
          <span class="spinner spinner--xs" /> {{ t('proposals.sandbox.decomposing') }}
        </span>
      </header>

      <!-- 스트리밍 narration (분해 과정 실시간) -->
      <pre v-if="tasksStream.active && narrationText" class="task-narration">{{ narrationText }}</pre>

      <!-- 분해된 작업 목록 -->
      <div v-if="tasks.length" class="tasks-preview">
        <div v-for="(sec, i) in taskSections" :key="i" class="task-sec">
          <div class="task-sec-head">
            <span class="sec-title">{{ sec.title }}</span>
            <span class="sec-count">{{ sec.items.length }}</span>
          </div>
          <ul class="task-list">
            <li v-for="(it, j) in sec.items" :key="j">
              <span class="task-check">○</span>
              <span class="task-text"><strong>{{ it.id }}</strong> {{ it.text }}
                <em v-if="it.files && it.files.length" class="task-files">{{ it.files.join(', ') }}</em>
              </span>
            </li>
          </ul>
        </div>
      </div>

      <div class="tasks-actions">
        <button v-if="!tasksStream.active && !tasks.length" @click="genTasks" class="btn btn--primary">
          {{ t('proposals.sandbox.generateTasks') }}
        </button>
        <button v-else-if="!tasksStream.active" @click="regenTasks" class="btn btn--outline">
          {{ t('proposals.sandbox.regenerateTasks') }}
        </button>
        <button v-if="tasksStream.active" @click="store.stopTasks()" class="btn btn--outline btn--sm">{{ t('proposals.common.stop') }}</button>
      </div>
      <p v-if="tasks.length && !tasksStream.active" class="tasks-hint">
        {{ t('proposals.sandbox.regenHint', { n: tasks.length }) }}
      </p>
      <p v-if="tasksStream.error" class="error-msg">{{ tasksStream.error }}</p>
    </section>

    <!-- 구현 중 안내 (IMPLEMENTING) — 다음 단계로 가려면 반드시 거쳐야 하므로 info 박스로 강조 -->
    <div v-else-if="proposal?.status === 'IMPLEMENTING'" class="running-note">
      <!-- 진행 중이면 스피너, 아니면 info 아이콘 -->
      <span v-if="!pendingLaunch && progressState.tone === 'running'" class="spinner spinner--sm running-note__icon" />
      <span v-else class="running-note__icon">ℹ️</span>
      <p class="running-note__text">
        {{ t('proposals.sandbox.implementingNote') }}<template v-if="pendingLaunch"> {{ t('proposals.sandbox.implementingNotePending') }} <strong>"{{ t('proposals.sandbox.goToShell') }}"</strong>{{ t('proposals.sandbox.implementingNotePendingPost') }} <code>/robo-implement {{ proposalId }}</code> {{ t('proposals.sandbox.implementingNoteCommand') }}</template>
      </p>
    </div>

    <!-- 구현 진행 상황 — 워크트리 tasks.md 모니터링 (IMPLEMENTING/TESTING) -->
    <section v-if="showProgress" class="progress-block">
      <header class="progress-head">
        <span class="progress-title">{{ t('proposals.sandbox.progressTitle') }}</span>
        <span :class="['progress-badge', `progress-badge--${progressState.tone}`]">
          <span v-if="progressState.tone === 'running'" class="spinner spinner--xs" />
          {{ progressState.label }}
        </span>
        <code class="progress-file" v-if="progress?.file">{{ progress.file }}</code>
      </header>

      <template v-if="progress?.exists">
        <div class="progress-bar">
          <div class="progress-bar__fill" :style="{ width: progress.percent + '%' }" />
          <span class="progress-bar__text">{{ progress.done }}/{{ progress.total }} ({{ progress.percent }}%)</span>
        </div>

        <div class="progress-sections">
          <details v-for="(sec, i) in progress.sections" :key="i" class="progress-section" :open="sec.done < sec.total">
            <summary>
              <span class="sec-title">{{ sec.title }}</span>
              <span class="sec-count">{{ sec.done }}/{{ sec.total }}</span>
            </summary>
            <ul class="task-list">
              <li v-for="(it, j) in itemsOf(sec.title)" :key="j" :class="{ done: it.done }">
                <span class="task-check">{{ it.done ? '✓' : '○' }}</span>
                <span class="task-text">{{ it.text }}</span>
              </li>
            </ul>
          </details>
        </div>
      </template>
      <p v-else class="progress-empty">
        {{ t('proposals.sandbox.progressEmptyPre') }}<code>{{ progress?.file || 'tasks.md' }}</code>{{ t('proposals.sandbox.progressEmptyPost') }}
      </p>
    </section>

    <!-- 준비 완료(pendingLaunch) — 자동 이동 안 함. 안내 멘트에 연결된 이 버튼을
         눌러야 셀로 진입하며 /robo-implement 명령으로 구현이 시작된다. -->
    <div class="sandbox-actions" v-if="pendingLaunch">
      <button @click="goToShell" class="btn btn--primary">{{ t('proposals.sandbox.goToShell') }}</button>
    </div>

    <!-- 액션 버튼들 — tasks.md 진행 상태로 결정:
         없음 → 구현하기 / 부분 → 미구현부분 완료하기 / 완료 → 다시 구현하기 -->
    <div class="sandbox-actions" v-else-if="actionMode || proposal?.sandboxWorktreePath">
      <button
        v-if="actionMode === 'start'"
        @click="startImplement(false)"
        class="btn btn--primary"
        :disabled="!projectRoot || starting"
      >{{ starting ? t('proposals.sandbox.preparing') : t('proposals.sandbox.startImplement') }}</button>

      <button
        v-else-if="actionMode === 'complete'"
        @click="completeImplement"
        class="btn btn--primary"
        :disabled="completing"
        :title="tasksAllDone
          ? t('proposals.sandbox.tooltipCompleteAllDone')
          : t('proposals.sandbox.tooltipCompletePartial')"
      >{{ completing ? t('proposals.sandbox.completing') : (tasksAllDone ? t('proposals.sandbox.completeToVerify') : t('proposals.sandbox.completePartial')) }}</button>

      <!-- 구현 완료(TESTING 이후) — 검증은 언제든 추가로 다시 돌릴 수 있다. -->
      <button
        v-if="actionMode === 'reimplement'"
        @click="emit('validate')"
        class="btn btn--primary"
        :title="t('proposals.sandbox.tooltipVerify')"
      >{{ t('proposals.sandbox.verify') }}</button>

      <button
        v-if="actionMode === 'reimplement'"
        @click="startImplement(true)"
        class="btn btn--outline"
        :disabled="!projectRoot || starting"
        :title="t('proposals.sandbox.tooltipReimplementFromDone')"
      >{{ starting ? t('proposals.sandbox.preparing') : t('proposals.sandbox.reimplement') }}</button>

      <!-- IMPLEMENTING 보조: 다시 구현하기 (검증으로 넘어가지 않고 처음부터) -->
      <button
        v-if="actionMode === 'complete'"
        @click="startImplement(true)"
        class="btn btn--outline"
        :disabled="!projectRoot || starting"
        :title="t('proposals.sandbox.tooltipReimplementFromImplementing')"
      >{{ t('proposals.sandbox.reimplement') }}</button>

      <button
        v-if="proposal?.sandboxWorktreePath"
        @click="goToShell"
        class="btn btn--outline"
      >{{ t('proposals.sandbox.goToShell') }}</button>
    </div>

    <p v-if="actionMode === 'complete' && tasksAllDone" class="reimplement-hint">
      ✅ {{ t('proposals.sandbox.allDoneHintPre') }} <strong>"{{ t('proposals.sandbox.completeToVerify') }}"</strong>{{ t('proposals.sandbox.allDoneHintPost') }}
    </p>
    <p v-else-if="actionMode === 'reimplement'" class="reimplement-hint">
      ✅ {{ t('proposals.sandbox.reimplementHintPre') }} <strong>"{{ t('proposals.sandbox.verify') }}"</strong>{{ t('proposals.sandbox.reimplementHintMid') }}
      <strong>"{{ t('proposals.sandbox.reimplement') }}"</strong>{{ t('proposals.sandbox.reimplementHintPost') }}
      {{ t('proposals.sandbox.reimplementHintAccept') }}
    </p>

    <p v-if="store.sandboxStream.error" class="error-msg">{{ store.sandboxStream.error }}</p>
  </div>
</template>

<script setup>
import { computed, ref, inject, watch, onUnmounted } from 'vue'
import { useProposalsStore } from '../proposals.store'
import { useI18n } from '../../../app/i18n'

const props = defineProps({ proposalId: { type: String, required: true } })
const emit = defineEmits(['validate'])  // 검증(TESTING)으로 전환됨 → 부모가 탭 전환
const store = useProposalsStore()
const { t } = useI18n()

// Claude Code 탭 경로 = Worktree 원천(projectRoot). App.vue가 provide.
const claudeCodeWorkdir = inject('claudeCodeWorkdir', null)
const openClaudeCode = inject('openClaudeCode', null)

const proposal = computed(() => store.currentProposal)
const starting = ref(false)
const completing = ref(false)
// 구현하기로 준비된(worktree+tasks) 직후, 아직 셀로 진입하지 않은 상태.
// 존재하면 'Claude Code 셀로 이동'이 dominant 액션이 되고, 그 클릭이 셀 진입+명령 주입.
const pendingLaunch = ref(null)  // { worktreePath, command, restart } | null

// 샌드박스 worktree 경로(.../.sandbox/proposal/<id>)를 실제 루트로 끌어올린다.
function stripSandbox(p) {
  if (!p) return p
  const i = p.indexOf('/.sandbox/')
  return i >= 0 ? p.slice(0, i) : p
}
function readProjectRoot() {
  const fromInject = claudeCodeWorkdir?.value
  if (fromInject) return stripSandbox(fromInject)
  try { return stripSandbox(localStorage.getItem('claude_code_workspace_root') || '') } catch { return '' }
}
// 워크트리 원천 = 현재 Code 탭에 '설정된' 프로젝트 루트를 우선한다(사용자 지시).
// 저장된 proposal.projectRoot는 폴백일 뿐 — 과거에 오염 저장된 값이 우선되지 않도록.
const projectRoot = computed(() => readProjectRoot() || stripSandbox(proposal.value?.projectRoot))
const branchPreview = computed(() => `proposal/${props.proposalId}`)

// 재구현 허용 상태 — ACCEPTED(머지 완료)·DESTROYED(폐기)·DRAFT(미제출)는 불가.
const REIMPLEMENTABLE = ['SUBMITTED', 'IMPLEMENTING', 'TESTING', 'PENDING_ACCEPTANCE', 'MERGE_FAILED']
const canImplement = computed(() => REIMPLEMENTABLE.includes(proposal.value?.status))

// ── 작업 분해 (구현 전 미리 뽑아 보여주기) ──
const tasksStream = computed(() => store.tasksStream)
const tasks = computed(() => store.tasksStream.tasks || [])
const narrationText = computed(() => (store.tasksStream.logLines || []).join('\n'))
// phase별 그룹핑 (등장 순서 유지)
const taskSections = computed(() => {
  const out = []; const idx = {}
  for (const t of tasks.value) {
    const key = t.phase || 'Tasks'
    if (!idx[key]) { idx[key] = { title: key, items: [] }; out.push(idx[key]) }
    idx[key].items.push(t)
  }
  return out
})

function genTasks() {
  store.subscribeToTasks(props.proposalId).catch(() => {})
}

// 이미 작업 목록이 있는 상태에서 재생성 — 기존 목록을 버리므로 확인을 받는다.
function regenTasks() {
  const ok = window.confirm(t('proposals.sandbox.confirmRegen', { n: tasks.value.length }))
  if (!ok) return
  store.subscribeToTasks(props.proposalId).catch(() => {})
}

// ── 구현 버튼 상태 = 워크트리 tasks.md 진행으로 결정 ──
// 없음 → '구현하기' / 부분 체크 → '구현 완료하기' / 전부 체크 → '다시 구현하기'.
const tasksAllDone = computed(() => {
  const p = progress.value
  return !!(p?.exists && p.total > 0 && p.done >= p.total)
})
// 버튼은 워크트리 tasks.md(체크리스트) **존재 여부**로 결정한다. '미구현부분 완료하기'가
// 뜨면 그 체크리스트가 진행 블록에 함께 보여야 하므로, hasWorktree가 아니라 파일 존재 기준.
const tasksFileExists = computed(() => !!progress.value?.exists)
const actionMode = computed(() => {
  if (!canImplement.value) return null
  const status = proposal.value?.status
  if (tasksFileExists.value) {
    // IMPLEMENTING + tasks.md 있음 → '검증으로 진행'(완료) 또는 '미구현부분 완료'(부분).
    // 둘 다 completeImplement(IMPLEMENTING→TESTING)로 검증·승인 단계로 넘어간다.
    // '다시 구현하기'는 보조 버튼으로 함께 제공한다.
    if (status === 'IMPLEMENTING') return 'complete'
    return 'reimplement'  // TESTING 이후 — 검증/승인은 탭에서, 샌드박스는 재구현만.
  }
  // tasks.md 없음 = 체크리스트가 아직 없음 → 그냥 구현하기
  if (status === 'SUBMITTED' && tasks.value.length === 0) return 'gated'  // 작업 목록 먼저 생성
  return 'start'
})

// SUBMITTED로 들어오면 이미 분해해둔 작업이 있으면 불러와 표시(시작 버튼 노출).
watch(
  () => [props.proposalId, proposal.value?.status],
  ([, status]) => {
    if (status === 'SUBMITTED' && !tasks.value.length && !store.tasksStream.active) {
      store.fetchTasks(props.proposalId).catch(() => {})
    }
  },
  { immediate: true },
)

async function startImplement(restart = false) {
  const root = projectRoot.value
  if (!root) {
    window.alert(t('proposals.sandbox.alertNoProjectRoot'))
    return
  }
  // 재구현(restart)은 기존 샌드박스를 초기화하므로 확인을 받는다.
  if (restart) {
    const ok = window.confirm(t('proposals.sandbox.confirmRestart', { id: props.proposalId }))
    if (!ok) return
  }
  starting.value = true
  try {
    // 작업 목록(tasks.md의 원천)이 없으면 Code 탭으로 바로 넘어가지 않고, 먼저
    // 작업 목록을 분해(생성)한 뒤 진행한다. 재구현(restart)은 기존 목록을 사용.
    if (!restart) {
      let hasTasks = tasks.value.length > 0
      if (!hasTasks) {
        // 상태와 무관하게 백엔드에 저장된 작업 목록 존재 여부를 확인한다.
        const t = await store.fetchTasks(props.proposalId).catch(() => null)
        hasTasks = !!(t && t.exists)
      }
      if (!hasTasks) {
        await store.subscribeToTasks(props.proposalId)  // 없으면 즉석 생성
      }
    }
    await runImplement(root, restart, false)
  } catch (e) {
    window.alert(t('proposals.sandbox.errorStartFailed', { msg: e?.message || e }))
  } finally {
    starting.value = false
  }
}

// 실제 구현 요청. 대상이 Git 저장소가 아니면(NOT_A_GIT_REPO) 다이얼로그로 git init
// 동의를 받아 initGit=true 로 1회 재시도한다. (FR-006)
// 준비만 하고 **자동으로 Code 탭으로 이동하지 않는다** — 'Claude Code 셀로 이동'
// 버튼을 눌렀을 때 그 셀로 진입하며 /robo-implement 명령을 주입한다.
async function runImplement(root, restart, initGit) {
  try {
    const data = await store.implementProposal(props.proposalId, root, initGit)
    if (data?.worktreePath) {
      pendingLaunch.value = { worktreePath: data.worktreePath, command: data.command, restart }
    }
  } catch (e) {
    if (e?.code === 'NOT_A_GIT_REPO' && !initGit) {
      const ok = window.confirm(`${e.message}\n\n${t('proposals.sandbox.gitInitNote')}`)
      if (!ok) return
      await runImplement(root, restart, true)
      return
    }
    throw e
  }
}

// 이 Proposal의 셀 세션이 이미 떠 있는지(=구현이 이미 시작됐는지) 확인한다.
function hasShellSession() {
  try {
    const arr = JSON.parse(localStorage.getItem('claude_code_workspace_sessions') || '[]')
    return Array.isArray(arr) && arr.some(
      (s) => s && s.kind === 'proposal' && (s.proposalId === props.proposalId || String(s.id || '').includes(props.proposalId)),
    )
  } catch { return false }
}

function goToShell() {
  const path = pendingLaunch.value?.worktreePath || proposal.value?.sandboxWorktreePath
  if (!openClaudeCode || !path) return
  // 최초 진입(준비 직후 또는 셀 세션 없음)이면 /robo-implement 명령을 주입해 구현을
  // 시작한다. 이미 세션이 있으면(이어보기) 명령 없이 그 셀로만 전환한다.
  const firstEntry = !!pendingLaunch.value || !hasShellSession()
  const command = firstEntry ? (pendingLaunch.value?.command || `/robo-implement ${props.proposalId}`) : null
  const restart = pendingLaunch.value?.restart || false
  openClaudeCode(path, command, { proposalId: props.proposalId, restart })
  pendingLaunch.value = null
}

async function completeImplement() {
  completing.value = true
  try {
    await store.completeImplementation(props.proposalId)
    emit('validate')  // TESTING 전환 완료 → 부모가 '검증' 탭으로 이동
  } catch (e) {
    window.alert(t('proposals.sandbox.errorCompleteFailed', { msg: e?.message || e }))
  } finally {
    completing.value = false
  }
}

// ── 구현 진행 상황 폴링 (워크트리 tasks.md 모니터링) ──────────────────────────
const STALE_SECONDS = 90          // 이 시간 넘게 갱신 없으면 '정체'로 표시
const POLL_MS = 4000
const progress = ref(null)
let pollTimer = null

// 워크트리가 생성된(=구현이 시작된) 뒤로는 진행률 블록을 노출·폴링한다.
// 버튼 상태(구현하기/완료하기/다시 구현하기)도 이 폴링 결과로 결정되므로
// IMPLEMENTING/TESTING 뿐 아니라 PENDING_ACCEPTANCE/MERGE_FAILED 에서도 폴링한다.
const showProgress = computed(() => canImplement.value && !!proposal.value?.sandboxWorktreePath)

function itemsOf(sectionTitle) {
  const items = progress.value?.items || []
  return items.filter((it) => (it.section || '기타') === sectionTitle)
}

// 상태 배지: 완료 / 진행 중 / 정체(멈춤 가능) / 준비 중.
const progressState = computed(() => {
  const p = progress.value
  if (!p || !p.exists) return { tone: 'pending', label: t('proposals.sandbox.checklistPending') }
  if (p.total > 0 && p.done >= p.total) return { tone: 'done', label: t('proposals.sandbox.progressDone', { done: p.done, total: p.total }) }
  const since = p.secondsSinceUpdate
  if (since != null && since > STALE_SECONDS) {
    const mins = Math.floor(since / 60)
    const time = mins >= 1 ? t('proposals.sandbox.staleMinutes', { n: mins }) : t('proposals.sandbox.staleSeconds', { n: Math.round(since) })
    return { tone: 'stale', label: t('proposals.sandbox.progressStale', { time }) }
  }
  return { tone: 'running', label: t('proposals.sandbox.progressRunning', { done: p.done, total: p.total }) }
})

async function pollProgress() {
  try {
    progress.value = await store.fetchProgress(props.proposalId)
  } catch { /* 폴링 — 일시 오류는 무시하고 다음 주기에 재시도 */ }
}

function startPolling() {
  stopPolling()
  pollProgress()
  pollTimer = setInterval(pollProgress, POLL_MS)
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

watch(showProgress, (on) => { on ? startPolling() : stopPolling() }, { immediate: true })
watch(() => props.proposalId, () => { progress.value = null; if (showProgress.value) startPolling() })
onUnmounted(() => { stopPolling(); store.stopTasks() })
</script>

<style scoped>
.sandbox-view { font-size: 13px; }
.sandbox-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; font-size: 12px; }
.project-root-line { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 12px; flex-wrap: wrap; }
.project-root-missing { color: var(--color-warning); }
.meta-label { color: var(--color-text-light); }
code { background: var(--color-bg-tertiary); color: var(--color-text); padding: 1px 5px; border-radius: 3px; font-family: monospace; }
.sandbox-status { font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; }
.sandbox-status--ready { background: var(--status-green-bg); color: var(--status-green-fg); }
.sandbox-status--implementing { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.sandbox-status--done { background: var(--status-green-bg); color: var(--status-green-fg); }
.sandbox-status--destroyed { background: var(--status-neutral-bg); color: var(--status-neutral-fg); }
.sandbox-empty { color: var(--color-text-light); padding: 8px 0 12px; margin: 0; line-height: 1.5; }
.sandbox-empty code { font-size: 11px; }
.running-note { display: flex; align-items: flex-start; gap: 8px; margin: 0 0 12px; padding: 10px 12px; background: var(--status-blue-bg); border: 1px solid color-mix(in srgb, var(--status-blue-fg) 25%, transparent); border-radius: 6px; }
.running-note__icon { flex-shrink: 0; line-height: 1.6; font-size: 14px; }
.running-note__text { margin: 0; line-height: 1.6; color: var(--color-text); font-size: 13px; }
.running-note__text code { font-family: monospace; background: var(--color-bg-tertiary); padding: 1px 5px; border-radius: 3px; font-size: 12px; }
.sandbox-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.reimplement-hint { color: var(--color-text-light); font-size: 11px; margin: 8px 0 0; }
.spinner { width: 14px; height: 14px; border: 2px solid var(--color-border); border-top-color: var(--color-accent); border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block; }
.spinner--sm { width: 12px; height: 12px; vertical-align: middle; margin-top: 2px; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: var(--color-danger); font-size: 12px; margin-top: 6px; }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 12px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--outline { background: transparent; border: 1px solid var(--color-border); color: var(--color-text); }

/* ── 구현 진행 상황 ── */
.progress-block { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--color-border); }
.progress-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.progress-title { font-weight: 700; font-size: 12px; }
.progress-file { font-size: 10px; color: var(--color-text-light); margin-left: auto; }
.progress-badge { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 10px; }
.progress-badge--running { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.progress-badge--done { background: var(--status-green-bg); color: var(--status-green-fg); }
.progress-badge--stale { background: var(--status-red-bg, #fde8e8); color: var(--status-red-fg, #c0392b); }
.progress-badge--pending { background: var(--status-neutral-bg); color: var(--status-neutral-fg); }
.progress-bar { position: relative; height: 18px; background: var(--color-bg-tertiary); border-radius: 9px; overflow: hidden; margin-bottom: 10px; }
.progress-bar__fill { position: absolute; inset: 0 auto 0 0; background: var(--color-accent); transition: width 0.4s ease; }
.progress-bar__text { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: var(--color-text); mix-blend-mode: difference; }
.progress-sections { display: flex; flex-direction: column; gap: 4px; }
.progress-section > summary { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 12px; padding: 4px 0; list-style: none; }
.progress-section > summary::-webkit-details-marker { display: none; }
.sec-title { font-weight: 600; }
.sec-count { margin-left: auto; font-size: 11px; color: var(--color-text-light); }
.task-list { list-style: none; margin: 2px 0 6px; padding: 0 0 0 4px; }
.task-list li { display: flex; align-items: flex-start; gap: 6px; font-size: 12px; padding: 2px 0; color: var(--color-text); }
.task-list li.done .task-text { color: var(--color-text-light); text-decoration: line-through; }
.task-check { width: 14px; flex-shrink: 0; color: var(--color-text-light); }
.task-list li.done .task-check { color: var(--status-green-fg, #2e7d32); }
.progress-empty { font-size: 12px; color: var(--color-text-light); margin: 4px 0 0; line-height: 1.5; }
.spinner--xs { width: 10px; height: 10px; border-width: 2px; }

/* ── 작업 분해 ── */
.tasks-block { margin: 8px 0 12px; padding: 10px 0 0; border-top: 1px dashed var(--color-border); }
.task-narration { font-size: 11px; line-height: 1.5; color: var(--color-text-light); background: var(--color-bg-tertiary); border-radius: 6px; padding: 8px 10px; margin: 6px 0; max-height: 160px; overflow: auto; white-space: pre-wrap; word-break: break-word; }
.tasks-preview { margin: 6px 0; display: flex; flex-direction: column; gap: 8px; }
.task-sec-head { display: flex; align-items: center; gap: 8px; font-size: 12px; margin-bottom: 2px; }
.task-sec-head .sec-count { margin-left: auto; color: var(--color-text-light); font-size: 11px; }
.task-files { display: block; font-size: 10px; color: var(--color-text-light); font-style: normal; margin-top: 1px; }
.tasks-actions { display: flex; gap: 8px; align-items: center; margin-top: 4px; }
.tasks-hint { color: var(--color-text-light); font-size: 11px; margin: 6px 0 0; }
.btn--sm { padding: 4px 10px; font-size: 11px; }
</style>
