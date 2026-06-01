<script setup>
import { ref, watch, onBeforeUnmount, computed, nextTick } from 'vue'
import { EditorState, Compartment } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { syntaxHighlighting, HighlightStyle, bracketMatching, indentOnInput } from '@codemirror/language'
import { tags as t } from '@lezer/highlight'
import { markdown } from '@codemirror/lang-markdown'
import { json } from '@codemirror/lang-json'
import { yaml } from '@codemirror/lang-yaml'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { vue as vueLang } from '@codemirror/lang-vue'

// Tokyo Night-aligned palette so the editor matches the Claude Code terminal.
const tokyoNightHighlight = HighlightStyle.define([
  { tag: t.keyword, color: 'var(--ccw-purple)' },
  { tag: [t.controlKeyword, t.moduleKeyword, t.operatorKeyword], color: 'var(--ccw-purple)' },
  { tag: [t.string, t.special(t.string)], color: 'var(--ccw-green)' },
  { tag: t.regexp, color: 'var(--ccw-cyan)' },
  { tag: t.escape, color: 'var(--ccw-cyan)' },
  { tag: t.number, color: 'var(--ccw-orange)' },
  { tag: t.bool, color: 'var(--ccw-orange)' },
  { tag: t.null, color: 'var(--ccw-orange)' },
  { tag: [t.comment, t.lineComment, t.blockComment], color: 'var(--ccw-text-dim)', fontStyle: 'italic' },
  { tag: t.atom, color: 'var(--ccw-purple)' },
  { tag: t.heading, color: 'var(--ccw-accent)', fontWeight: 'bold' },
  { tag: t.strong, color: 'var(--ccw-text)', fontWeight: 'bold' },
  { tag: t.emphasis, color: 'var(--ccw-text)', fontStyle: 'italic' },
  { tag: t.link, color: 'var(--ccw-teal)', textDecoration: 'underline' },
  { tag: t.url, color: 'var(--ccw-teal)', textDecoration: 'underline' },
  { tag: t.list, color: 'var(--ccw-accent)' },
  { tag: t.quote, color: 'var(--ccw-green)' },
  { tag: [t.variableName, t.propertyName], color: 'var(--ccw-text)' },
  { tag: t.function(t.variableName), color: 'var(--ccw-accent)' },
  { tag: t.definition(t.variableName), color: 'var(--ccw-text)' },
  { tag: [t.typeName, t.className], color: 'var(--ccw-cyan)' },
  { tag: t.operator, color: 'var(--ccw-cyan)' },
  { tag: [t.bracket, t.punctuation, t.separator], color: 'var(--ccw-text-muted)' },
  { tag: t.tagName, color: 'var(--ccw-red)' },
  { tag: t.attributeName, color: 'var(--ccw-yellow)' },
  { tag: t.attributeValue, color: 'var(--ccw-green)' },
  { tag: t.meta, color: 'var(--ccw-accent)' },
  { tag: t.invalid, color: 'var(--ccw-red)' },
])

const tokyoNightEditorTheme = EditorView.theme(
  {
    '&': {
      height: '100%',
      fontSize: '13px',
      color: 'var(--ccw-text)',
      backgroundColor: 'var(--ccw-bg)',
    },
    '.cm-content': {
      caretColor: 'var(--ccw-text)',
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
    },
    '.cm-scroller': {
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
    },
    '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--ccw-text)' },
    '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
      backgroundColor: 'var(--ccw-selection)',
    },
    '.cm-activeLine': { backgroundColor: 'var(--ccw-hover)' },
    '.cm-gutters': {
      backgroundColor: 'var(--ccw-bg)',
      color: 'var(--ccw-gutter)',
      border: 'none',
      borderRight: '1px solid var(--ccw-border)',
    },
    '.cm-lineNumbers .cm-gutterElement': {
      color: 'var(--ccw-gutter)',
      padding: '0 12px 0 8px',
    },
    '.cm-activeLineGutter': {
      backgroundColor: 'var(--ccw-hover)',
      color: 'var(--ccw-accent)',
    },
    '.cm-matchingBracket, .cm-nonmatchingBracket': {
      backgroundColor: 'var(--ccw-active)',
      color: 'inherit',
    },
  },
  { dark: true },
)

import { fetchFile, saveFile, WorkspaceApiError } from '../workspace.api.js'

const props = defineProps({
  root: { type: String, required: true },
  path: { type: String, default: null },
})

const emit = defineEmits(['saved'])

const editorHost = ref(null)
let view = null
const languageCompartment = new Compartment()

const loading = ref(false)
const errorMessage = ref(null)
const tooLarge = ref(null)            // { size } when 413
const isBinary = ref(false)
const originalContent = ref('')
const currentContent = ref('')
const mtimeNs = ref(null)              // string
const saving = ref(false)
const lastSavedAt = ref(0)
const pendingExternalReload = ref(null) // { newMtimeNs, newSize }
const reloadInfo = ref(null)            // transient toast for clean-buffer auto-reload

const dirty = computed(() => !isBinary.value && originalContent.value !== currentContent.value)

const fileLabel = computed(() => {
  if (!props.path) return ''
  const parts = props.path.split('/')
  return parts[parts.length - 1]
})

function languageForPath(path) {
  if (!path) return []
  const lower = path.toLowerCase()
  if (lower.endsWith('.md') || lower.endsWith('.markdown')) return [markdown()]
  if (lower.endsWith('.json')) return [json()]
  if (lower.endsWith('.yml') || lower.endsWith('.yaml')) return [yaml()]
  if (lower.endsWith('.py')) return [python()]
  if (lower.endsWith('.js') || lower.endsWith('.jsx') || lower.endsWith('.mjs') || lower.endsWith('.cjs')) {
    return [javascript()]
  }
  if (lower.endsWith('.ts') || lower.endsWith('.tsx')) return [javascript({ typescript: true, jsx: lower.endsWith('.tsx') })]
  if (lower.endsWith('.vue')) return [vueLang()]
  return []
}

function mountEditor(content) {
  destroyEditor()
  if (!editorHost.value) return
  const state = EditorState.create({
    doc: content,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      highlightActiveLineGutter(),
      bracketMatching(),
      indentOnInput(),
      history(),
      syntaxHighlighting(tokyoNightHighlight, { fallback: true }),
      keymap.of([
        ...defaultKeymap,
        ...historyKeymap,
        {
          key: 'Mod-s',
          run: () => {
            triggerSave()
            return true
          },
          preventDefault: true,
        },
      ]),
      languageCompartment.of(languageForPath(props.path)),
      EditorView.updateListener.of((u) => {
        if (u.docChanged) {
          currentContent.value = u.state.doc.toString()
        }
      }),
      tokyoNightEditorTheme,
    ],
  })
  view = new EditorView({ state, parent: editorHost.value })
}

function destroyEditor() {
  if (view) {
    view.destroy()
    view = null
  }
}

function setEditorDoc(content) {
  if (!view) {
    mountEditor(content)
    return
  }
  view.dispatch({
    changes: { from: 0, to: view.state.doc.length, insert: content },
    effects: languageCompartment.reconfigure(languageForPath(props.path)),
  })
}

async function loadFile(path) {
  loading.value = true
  errorMessage.value = null
  tooLarge.value = null
  isBinary.value = false
  pendingExternalReload.value = null
  try {
    const r = await fetchFile(props.root, path)
    if (r.binary) {
      isBinary.value = true
      destroyEditor()
      mtimeNs.value = r.mtime_ns
      return
    }
    originalContent.value = r.content || ''
    currentContent.value = r.content || ''
    mtimeNs.value = r.mtime_ns
    // Clear loading first so the editor-host (a v-else branch) renders;
    // wait for the next tick so its ref binds, then mount CodeMirror.
    loading.value = false
    await nextTick()
    mountEditor(originalContent.value)
  } catch (e) {
    if (e instanceof WorkspaceApiError && e.status === 413) {
      tooLarge.value = { size: e.body?.size ?? 0 }
      destroyEditor()
    } else {
      errorMessage.value = e.body?.detail || e.message || 'Failed to open file'
      destroyEditor()
    }
  } finally {
    loading.value = false
  }
}

async function triggerSave() {
  if (!props.path || isBinary.value || tooLarge.value || saving.value) return
  if (!dirty.value && pendingExternalReload.value === null) return
  saving.value = true
  errorMessage.value = null
  try {
    const r = await saveFile({
      root: props.root,
      path: props.path,
      content: currentContent.value,
      expectedMtimeNs: mtimeNs.value,
    })
    originalContent.value = currentContent.value
    mtimeNs.value = r.mtime_ns
    lastSavedAt.value = Date.now()
    emit('saved', { path: props.path, size: r.size, mtimeNs: r.mtime_ns })
  } catch (e) {
    if (e instanceof WorkspaceApiError && e.status === 409) {
      const detail = e.body?.detail
      const cur = typeof detail === 'object' ? detail : e.body
      pendingExternalReload.value = {
        newMtimeNs: cur?.current_mtime_ns ?? null,
        newSize: cur?.current_size ?? 0,
      }
    } else {
      errorMessage.value = e.body?.detail || e.message || 'Save failed'
    }
  } finally {
    saving.value = false
  }
}

async function reloadFromDisk() {
  pendingExternalReload.value = null
  if (props.path) await loadFile(props.path)
}

function keepMyChanges() {
  // Adopt the new mtime so the next save uses it; the buffer stays dirty.
  if (pendingExternalReload.value?.newMtimeNs) {
    mtimeNs.value = pendingExternalReload.value.newMtimeNs
  }
  pendingExternalReload.value = null
}

async function checkExternalModification() {
  if (!props.path || isBinary.value || tooLarge.value) return
  try {
    const r = await fetchFile(props.root, props.path)
    if (r.mtime_ns === mtimeNs.value) return
    if (dirty.value) {
      pendingExternalReload.value = { newMtimeNs: r.mtime_ns, newSize: r.size }
    } else {
      // Clean buffer — silent reload.
      originalContent.value = r.content || ''
      currentContent.value = r.content || ''
      mtimeNs.value = r.mtime_ns
      setEditorDoc(originalContent.value)
      reloadInfo.value = 'Reloaded from disk'
      setTimeout(() => {
        reloadInfo.value = null
      }, 2000)
    }
  } catch {
    // Silent — refresh failures are not actionable here.
  }
}

watch(
  () => props.path,
  (p) => {
    if (p) loadFile(p)
    else {
      destroyEditor()
      originalContent.value = ''
      currentContent.value = ''
      mtimeNs.value = null
      isBinary.value = false
      tooLarge.value = null
      errorMessage.value = null
      pendingExternalReload.value = null
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  destroyEditor()
})

defineExpose({ checkExternalModification, dirty, triggerSave })
</script>

<template>
  <div class="file-editor-pane">
    <div class="editor-tabbar">
      <div v-if="props.path" class="editor-tab is-active">
        <span v-if="dirty" class="dirty-dot" title="Unsaved changes">●</span>
        <span class="editor-tab-label">{{ fileLabel }}</span>
        <span class="editor-tab-path">{{ props.path }}</span>
      </div>
      <div v-else class="editor-tab editor-tab-empty">No file open</div>

      <div class="editor-actions">
        <span v-if="reloadInfo" class="editor-status">{{ reloadInfo }}</span>
        <span v-else-if="saving" class="editor-status">Saving…</span>
        <span v-else-if="lastSavedAt && Date.now() - lastSavedAt < 2000" class="editor-status">Saved</span>
        <button
          class="editor-save"
          :disabled="!props.path || isBinary || !!tooLarge || saving || (!dirty && !pendingExternalReload)"
          :title="dirty ? '저장 (⌘/Ctrl-S)' : '변경사항 없음'"
          @click="triggerSave"
        >
          Save
        </button>
      </div>
    </div>

    <div v-if="pendingExternalReload" class="editor-banner">
      <span>이 파일이 디스크에서 수정되었습니다.</span>
      <button class="banner-btn banner-primary" @click="reloadFromDisk">Reload from disk</button>
      <button class="banner-btn" @click="keepMyChanges">Keep my changes</button>
    </div>

    <div class="editor-body">
      <div v-if="!props.path" class="editor-placeholder">트리에서 파일을 선택하세요</div>
      <div v-else-if="loading" class="editor-placeholder">Loading…</div>
      <div v-else-if="tooLarge" class="editor-placeholder">
        파일이 너무 커서 브라우저 에디터에서 열 수 없습니다 ({{ Math.round(tooLarge.size / 1024) }} KB)
      </div>
      <div v-else-if="isBinary" class="editor-placeholder">바이너리 파일 — 미리보기를 지원하지 않습니다</div>
      <div v-else-if="errorMessage" class="editor-placeholder editor-error">{{ errorMessage }}</div>
      <div v-else ref="editorHost" class="editor-host"></div>
    </div>
  </div>
</template>

<style scoped>
.file-editor-pane {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--ccw-bg);
  color: var(--ccw-text);
  overflow: hidden;
}

.editor-tabbar {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--ccw-border);
  background: var(--ccw-bg-elevated);
  padding-right: 8px;
  min-height: 30px;
}

.editor-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--ccw-bg);
  border-right: 1px solid var(--ccw-border);
  font-size: 12px;
  white-space: nowrap;
  color: var(--ccw-text);
}

.editor-tab.is-active {
  border-bottom: 2px solid var(--ccw-accent);
}

.editor-tab-empty {
  opacity: 0.5;
  font-style: italic;
}

.editor-tab-label {
  font-weight: 600;
}

.editor-tab-path {
  opacity: 0.55;
  font-size: 11px;
  color: var(--ccw-text-muted);
}

.dirty-dot {
  color: var(--ccw-yellow);
  font-size: 14px;
  line-height: 1;
}

.editor-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.editor-status {
  font-size: 11px;
  color: var(--ccw-text-dim);
  font-style: italic;
}

.editor-save {
  font-size: 11px;
  padding: 3px 10px;
  background: var(--ccw-accent);
  color: var(--ccw-bg);
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-weight: 600;
}

.editor-save:hover:not(:disabled) {
  background: var(--ccw-accent-strong);
}

.editor-save:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.editor-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #5c4400;
  color: #fff;
  font-size: 12px;
  border-bottom: 1px solid #886a00;
}

.banner-btn {
  padding: 3px 10px;
  font-size: 11px;
  background: transparent;
  color: #fff;
  border: 1px solid #fff;
  border-radius: 3px;
  cursor: pointer;
}

.banner-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.banner-btn.banner-primary {
  background: #fff;
  color: #5c4400;
  font-weight: 600;
}

.editor-body {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.editor-host {
  height: 100%;
  width: 100%;
}

.editor-host :deep(.cm-editor) {
  height: 100%;
}

.editor-host :deep(.cm-editor.cm-focused) {
  outline: none;
}

.editor-placeholder {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ccw-text-dim);
  font-style: italic;
  padding: 20px;
  text-align: center;
  background: var(--ccw-bg);
}

.editor-error {
  color: var(--ccw-red);
}
</style>
