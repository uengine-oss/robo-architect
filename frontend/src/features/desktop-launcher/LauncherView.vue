<!--
  Real launcher view (spec 032 — US1 T027/T030, US2 T039/T040/T041, US3 T046/T047).

  Single-file by design — the MVP launcher is small enough to read top-to-bottom
  in one component. Sub-views (welcome banner, connection list, add form,
  project-root picker, enter button) are inline sections rather than separate
  files; if the launcher grows past ~400 LOC we'll split.

  Wires:
    - identity:resolve on mount, and again whenever projectRoot changes
    - connections:list on mount
    - projectRoot:listRecent on mount
    - connections:save / test as the user interacts with the add form
    - projectRoot:choose / validate when the user picks/types a folder
    - launcher:enter when the user clicks Enter, then session.commitProfile
-->

<script setup>
import { computed, onMounted, ref, toRaw, watch } from 'vue'
import { useSessionStore } from './stores/session-store.js'
import { useLauncherStore } from './stores/launcher-store.js'

const session = useSessionStore()
const launcher = useLauncherStore()
const desktop = window.desktop

// --- form state for "Add connection" ---
const formLabel = ref('')
const formUri = ref('bolt://localhost:7687')
const formUser = ref('neo4j')
const formDatabase = ref('')
const formPassword = ref('')
const testResult = ref(null) // {kind: 'success'|'error', message, serverVersion?}
const testing = ref(false)
const saving = ref(false)

// --- project root state ---
const rootPath = ref('')
const rootValid = ref(false)
const rootBasename = ref('')
const rootParent = ref('')
const rootError = ref(null)

const entering = ref(false)
const enterError = ref(null)

// --- git identity form (shown when source === 'unknown-fallback') ---
const gitFormName = ref('')
const gitFormEmail = ref('')
const gitFormSaving = ref(false)
const gitFormError = ref(null)


const hasIdentity = computed(() => session.user && session.user.source !== 'unknown-fallback')
const canEnter = computed(() => {
  if (!launcher.selectedConnectionId) return false
  if (!rootValid.value) return false
  return !entering.value
})

// ---------------------------------------------------------------------------
// On-mount: identity, saved connections, recent project roots
// ---------------------------------------------------------------------------

async function reloadConnections() {
  const r = await desktop.connections.list()
  if (r.ok) {
    launcher.setSavedConnections(r.data)
  }
}

async function reloadRecentRoots() {
  const r = await desktop.projectRoot.listRecent()
  if (r.ok && r.data.length > 0) {
    // Pre-fill the most-recent root and validate it.
    const first = r.data[0]
    rootPath.value = first.path
    await revalidateRoot()
  }
}

async function reresolveIdentity(rootForCwd) {
  const r = await desktop.identity.resolve({ projectRoot: rootForCwd })
  if (r.ok) {
    session.setIdentity(r.data)
  }
}

onMounted(async () => {
  await Promise.all([reresolveIdentity(null), reloadConnections(), reloadRecentRoots()])
})

// Re-resolve identity whenever the project root changes (FR-008).
watch(rootPath, async (next) => {
  if (next && rootValid.value) {
    await reresolveIdentity(next)
  }
})

// ---------------------------------------------------------------------------
// Add-connection form
// ---------------------------------------------------------------------------

async function onTest() {
  testResult.value = null
  testing.value = true
  try {
    const r = await desktop.connections.test({
      uri: formUri.value,
      user: formUser.value,
      password: formPassword.value,
      database: formDatabase.value,
    })
    if (r.ok) {
      testResult.value = { kind: 'success', message: 'Connection successful', serverVersion: r.data.serverVersion }
    } else {
      testResult.value = { kind: 'error', message: explainNeo4jError(r.error) }
    }
  } finally {
    testing.value = false
  }
}

function explainNeo4jError(err) {
  switch (err.code) {
    case 'NEO4J_AUTH_FAILED': return 'Wrong username or password.'
    case 'NEO4J_UNREACHABLE': return 'Host unreachable — check the Bolt URI and that Neo4j is running.'
    case 'NEO4J_TIMEOUT': return 'Connection timed out after 5 seconds.'
    case 'NEO4J_TLS_ERROR': return 'TLS error — check the scheme (bolt:// vs neo4j+s://) and certificate.'
    case 'VALIDATION': return err.message
    default: return err.message || 'Unknown connection error.'
  }
}

async function onSave() {
  if (!testResult.value || testResult.value.kind !== 'success') {
    enterError.value = 'Run Test first and make sure it succeeds before saving.'
    return
  }
  saving.value = true
  try {
    const r = await desktop.connections.save({
      label: formLabel.value || `${formUser.value}@${formUri.value}`,
      uri: formUri.value,
      user: formUser.value,
      database: formDatabase.value || undefined,
      source: 'manual',
      passwordPlaintext: formPassword.value,
    })
    if (r.ok) {
      // Clear form, reload list, select the new entry, drop back to list view.
      formLabel.value = ''
      formPassword.value = ''
      testResult.value = null
      await reloadConnections()
      launcher.select(r.data.id)
      launcher.showForm('list')
    } else {
      enterError.value = `Save failed: ${r.error.message}`
    }
  } finally {
    saving.value = false
  }
}

// ---------------------------------------------------------------------------
// Project root picker
// ---------------------------------------------------------------------------

async function pickRoot() {
  rootError.value = null
  const r = await desktop.projectRoot.choose()
  if (!r.ok) {
    rootError.value = r.error.message
    return
  }
  if ('cancelled' in r.data) return
  rootPath.value = r.data.path
  rootValid.value = r.data.valid
  rootBasename.value = r.data.basename
  rootParent.value = r.data.parent
}

async function revalidateRoot() {
  if (!rootPath.value) {
    rootValid.value = false
    return
  }
  const r = await desktop.projectRoot.validate({ path: rootPath.value })
  if (r.ok) {
    rootValid.value = r.data.valid
    if (!r.data.valid) {
      rootError.value = r.data.reason === 'not-found'
        ? 'Folder not found.'
        : r.data.reason === 'unreadable'
          ? 'Folder is not readable.'
          : r.data.reason === 'not-a-directory'
            ? 'Path is not a directory.'
            : 'Invalid path.'
      rootBasename.value = ''
      rootParent.value = ''
    } else {
      // basename/parent 는 백엔드(Node path)가 계산 — OS 구분자(\·/) 모두 정확. 프론트 문자열 분리 금지.
      rootBasename.value = r.data.basename || rootPath.value
      rootParent.value = r.data.parent || ''
      rootError.value = null
    }
  }
}

// ---------------------------------------------------------------------------
// Git identity setup
// ---------------------------------------------------------------------------

async function onSaveGitConfig() {
  gitFormError.value = null
  const name = gitFormName.value.trim()
  const email = gitFormEmail.value.trim()
  if (!name || !email) {
    gitFormError.value = '이름과 이메일을 모두 입력해주세요.'
    return
  }
  gitFormSaving.value = true
  try {
    const r = await desktop.identity.setGitConfig({ name, email })
    if (r.ok) {
      session.setIdentity(r.data)
      gitFormName.value = ''
      gitFormEmail.value = ''
    } else {
      gitFormError.value = r.error.message || 'git config 저장에 실패했습니다.'
    }
  } finally {
    gitFormSaving.value = false
  }
}

// ---------------------------------------------------------------------------
// Enter
// ---------------------------------------------------------------------------

async function onEnter() {
  if (!canEnter.value) {
    if (!launcher.selectedConnectionId) enterError.value = '커넥션을 선택해주세요.'
    else if (!rootValid.value) enterError.value = '프로젝트 폴더를 선택해주세요.'
    return
  }
  entering.value = true
  enterError.value = null
  try {
    const r = await desktop.launcher.enter({
      connectionId: launcher.selectedConnectionId,
      projectRoot: rootPath.value,
      identity: toRaw(session.user),
    })
    if (r.ok) {
      session.commitProfile({
        identity: r.data.identity,
        activeConnectionId: r.data.activeConnectionId,
        projectRoot: rootPath.value,
      })
      // Persist projectRoot for the existing Claude Code workspace integration.
      try { localStorage.setItem('claude_code_workspace_root', rootPath.value) } catch { /* ignore */ }
      // session.entered flips true → App.vue gate dissolves automatically.
    } else {
      enterError.value = explainEnterError(r.error)
    }
  } finally {
    entering.value = false
  }
}

function explainEnterError(err) {
  switch (err.code) {
    case 'NEO4J_AUTH_FAILED':
      return 'The stored password no longer works for this connection. Edit it and try again.'
    case 'NEO4J_UNREACHABLE':
      return 'The Neo4j server is not reachable. Check the host/port and try again.'
    case 'NEO4J_TIMEOUT':
      return 'Neo4j took too long to respond.'
    case 'PROJECT_ROOT_INVALID':
    case 'PROJECT_ROOT_UNREADABLE':
      return `Project root: ${err.message}`
    case 'CONNECTION_NOT_FOUND':
      return 'That saved connection is gone. Refreshing the list.'
    default:
      return err.message || 'Could not enter.'
  }
}
</script>

<template>
  <div class="launcher">
    <!-- Brand — same style as TopBar (global .top-bar__logo classes) -->
    <div class="top-bar__logo launcher-brand">
      <div class="top-bar__logo-icon">RA</div>
      <span>Robo Architect</span>
    </div>

    <!-- WelcomeBanner -->
    <header class="welcome">
      <h1>Welcome, {{ session.user?.displayName || 'unknown user' }}</h1>
      <p v-if="hasIdentity" class="source-badge">
        Identity from <code>{{ session.user.source }}</code> — <code>{{ session.user.email }}</code>
      </p>

      <!-- Git identity setup form — shown when no git user is configured -->
      <div v-if="!hasIdentity" class="git-identity-form">
        <p class="git-identity-hint">
          Git 사용자 정보가 설정되지 않았습니다. 변경 이력에 이름이 기록됩니다.
        </p>
        <div class="git-identity-fields">
          <input
            v-model="gitFormName"
            type="text"
            placeholder="이름 (예: Kim Minsu)"
            autocomplete="name"
          />
          <input
            v-model="gitFormEmail"
            type="email"
            placeholder="이메일 (예: minsu@example.com)"
            autocomplete="email"
          />
          <button
            type="button"
            class="git-identity-save"
            :disabled="gitFormSaving || !gitFormName.trim() || !gitFormEmail.trim()"
            @click="onSaveGitConfig"
          >
            {{ gitFormSaving ? '저장 중…' : 'Git 정보 저장' }}
          </button>
        </div>
        <p v-if="gitFormError" class="msg err">{{ gitFormError }}</p>
      </div>
    </header>

    <!-- Saved connections list -->
    <section class="section">
      <h2>Neo4j connection</h2>

      <div v-if="launcher.savedConnections.length > 0" class="connection-list">
        <button
          v-for="c in launcher.savedConnections"
          :key="c.id"
          type="button"
          class="connection-item"
          :class="{ selected: launcher.selectedConnectionId === c.id }"
          @click="launcher.select(c.id)"
        >
          <div class="connection-label">{{ c.label }}</div>
          <div class="connection-uri">{{ c.user }}@{{ c.uri }}</div>
        </button>
      </div>

      <!-- Add new entry: always available; expanded by default in empty state -->
      <details class="add-form" :open="launcher.savedConnections.length === 0 || launcher.formMode === 'add'">
        <summary>+ Add a new connection</summary>

        <div class="form-grid">
          <label>Label
            <input v-model="formLabel" type="text" placeholder="e.g. Local Dev" />
          </label>
          <label>Bolt URI
            <input v-model="formUri" type="text" />
          </label>
          <label>User
            <input v-model="formUser" type="text" />
          </label>
          <label>Database (optional)
            <input v-model="formDatabase" type="text" placeholder="default" />
          </label>
          <label>Password
            <input v-model="formPassword" type="password" autocomplete="current-password" />
          </label>
        </div>

        <div class="form-actions">
          <button type="button" :disabled="testing || !formPassword" @click="onTest">
            {{ testing ? 'Testing…' : 'Test' }}
          </button>
          <button type="button" :disabled="saving || !testResult || testResult.kind !== 'success'" @click="onSave">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </div>

        <p v-if="testResult && testResult.kind === 'success'" class="msg ok">
          ✓ {{ testResult.message }}<span v-if="testResult.serverVersion"> ({{ testResult.serverVersion }})</span>
        </p>
        <p v-if="testResult && testResult.kind === 'error'" class="msg err">
          ✗ {{ testResult.message }}
        </p>
      </details>
    </section>

    <!-- Project root picker -->
    <section class="section">
      <h2>Project root</h2>
      <div class="root-row">
        <button type="button" class="root-pick" @click="pickRoot">폴더 선택…</button>
        <div v-if="rootPath" class="root-display" :class="{ invalid: !rootValid }">
          <div class="root-basename">{{ rootBasename || rootPath }}</div>
          <div v-if="rootParent" class="root-parent">{{ rootParent }}</div>
        </div>
        <div v-else class="root-display empty">폴더를 선택해주세요</div>
      </div>
      <p v-if="rootError" class="msg err">{{ rootError }}</p>
    </section>

    <!-- Enter -->
    <section class="enter-section">
      <div class="enter-hints">
        <span v-if="!launcher.selectedConnectionId" class="enter-hint">커넥션을 선택해주세요</span>
        <span v-else-if="!rootValid" class="enter-hint">프로젝트 폴더를 선택해주세요</span>
      </div>
      <button type="button" class="enter" :disabled="!canEnter" @click="onEnter">
        {{ entering ? 'Entering…' : 'Enter →' }}
      </button>
      <p v-if="enterError" class="msg err">{{ enterError }}</p>
    </section>
  </div>
</template>

<style scoped>
.launcher {
  max-width: 720px;
  margin: 2rem auto;
  padding: 1.5rem;
  font-family: system-ui, sans-serif;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* Brand — extends global .top-bar__logo with launcher-specific bottom border */
.launcher-brand {
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(128, 128, 128, 0.15);
}

/* Git identity form */
.git-identity-form {
  margin-top: 0.75rem;
  padding: 0.75rem;
  border: 1px dashed rgba(74, 140, 255, 0.4);
  border-radius: 6px;
  background: rgba(74, 140, 255, 0.04);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.git-identity-hint {
  margin: 0;
  font-size: 0.82rem;
  color: #aaa;
}
.git-identity-fields {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}
.git-identity-fields input {
  flex: 1;
  min-width: 140px;
  padding: 0.35rem 0.5rem;
  border: 1px solid rgba(128, 128, 128, 0.4);
  background: transparent;
  color: inherit;
  font-size: 0.85rem;
  border-radius: 3px;
}
.git-identity-save {
  padding: 0.35rem 0.8rem;
  border: 1px solid #4a8cff;
  background: rgba(74, 140, 255, 0.15);
  color: inherit;
  cursor: pointer;
  border-radius: 3px;
  font-size: 0.85rem;
  white-space: nowrap;
}
.git-identity-save:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.git-identity-save:not(:disabled):hover {
  background: rgba(74, 140, 255, 0.25);
}

.welcome h1 {
  margin: 0 0 0.5rem;
  font-size: 1.5rem;
}
.welcome .hint {
  color: #b66;
  margin: 0;
  font-size: 0.875rem;
}
.welcome .source-badge {
  color: #666;
  margin: 0;
  font-size: 0.8rem;
}
.section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.section h2 {
  margin: 0;
  font-size: 1rem;
  color: #888;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.connection-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.connection-item {
  display: block;
  text-align: left;
  background: transparent;
  border: 1px solid rgba(128, 128, 128, 0.3);
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  color: inherit;
  cursor: pointer;
}
.connection-item:hover {
  background: rgba(128, 128, 128, 0.1);
}
.connection-item.selected {
  border-color: #4a8cff;
  background: rgba(74, 140, 255, 0.1);
}
.connection-label {
  font-weight: 500;
}
.connection-uri {
  font-size: 0.8rem;
  color: #888;
  font-family: monospace;
}
.add-form {
  border: 1px dashed rgba(128, 128, 128, 0.4);
  border-radius: 4px;
  padding: 0.5rem 0.75rem;
}
.add-form summary {
  cursor: pointer;
  color: #888;
  user-select: none;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
  color: #888;
}
.form-grid input {
  padding: 0.35rem 0.5rem;
  border: 1px solid rgba(128, 128, 128, 0.4);
  background: transparent;
  color: inherit;
  font-size: 0.9rem;
  border-radius: 3px;
}
.form-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
.form-actions button,
.root-pick,
.enter {
  padding: 0.4rem 0.9rem;
  border: 1px solid rgba(128, 128, 128, 0.5);
  background: transparent;
  color: inherit;
  cursor: pointer;
  border-radius: 3px;
}
.form-actions button:disabled,
.enter:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.root-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.root-display {
  flex: 1;
  min-width: 0;
}
.root-display.empty {
  color: #888;
  font-style: italic;
}
.root-display.invalid {
  color: #c66;
}
.root-basename {
  font-weight: 500;
}
.root-parent {
  font-size: 0.75rem;
  color: #888;
  font-family: monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.enter-section {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.5rem;
}
.enter-hints {
  min-height: 1.2rem;
}
.enter-hint {
  font-size: 0.8rem;
  color: #f0a040;
}
.enter {
  padding: 0.5rem 1.5rem;
  font-size: 1rem;
  border-color: #4a8cff;
  background: rgba(74, 140, 255, 0.15);
}
.enter:not(:disabled):hover {
  background: rgba(74, 140, 255, 0.25);
}
.msg {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
}
.msg.ok {
  color: #5cb85c;
}
.msg.err {
  color: #d9534f;
}
</style>
