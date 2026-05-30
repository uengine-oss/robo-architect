<script setup>
import { ref, onMounted, onBeforeUnmount, watch, inject } from 'vue'
import ClaudeCodeTerminal from './ClaudeCodeTerminal.vue'
import FileTreePane from './FileTreePane.vue'
import FileEditorPane from './FileEditorPane.vue'

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

// Local working directory state. Mirrors the existing terminal: when no
// workdir is supplied at mount, the terminal will surface its folder picker
// and we react to its `pickedWorkdir` (workdir prop changes via the parent).
// Restore the last project path so a refresh doesn't reset back to the picker.
const activeRoot = ref(props.workdir || readPersisted(ROOT_KEY))
const persistedActivePath = readPersisted(ACTIVE_PATH_KEY)
const activePath = ref(activeRoot.value && persistedActivePath ? persistedActivePath : null)

// 029 — share the active workspace path back up to App.vue's ref so other
// features (e.g. InspectorPanel's source-viewer for ImplementationFile
// nodes) can resolve relative paths even when the user reached this tab
// without going through the wizard (cold reload, manual tab click, etc).
const appWorkdirRef = inject('claudeCodeWorkdir', null)
if (appWorkdirRef && activeRoot.value && appWorkdirRef.value !== activeRoot.value) {
  appWorkdirRef.value = activeRoot.value
}

watch(
  () => props.workdir,
  (w) => {
    if (w && w !== activeRoot.value) {
      activeRoot.value = w
      activePath.value = null
    }
  },
)

watch(activeRoot, (v) => {
  try {
    if (v) localStorage.setItem(ROOT_KEY, v)
    else localStorage.removeItem(ROOT_KEY)
  } catch {}
  if (appWorkdirRef && appWorkdirRef.value !== v) {
    appWorkdirRef.value = v || ''
  }
})

watch(activePath, (v) => {
  try {
    if (v) localStorage.setItem(ACTIVE_PATH_KEY, v)
    else localStorage.removeItem(ACTIVE_PATH_KEY)
  } catch {}
})

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

function onTerminalWorkdirPicked(path) {
  if (path && path !== activeRoot.value) {
    activeRoot.value = path
    activePath.value = null
  }
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

    <!-- Right: existing Claude Code terminal -->
    <div class="ccw-pane ccw-terminal">
      <ClaudeCodeTerminal :workdir="activeRoot" @workdir-picked="onTerminalWorkdirPicked" />
    </div>
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
