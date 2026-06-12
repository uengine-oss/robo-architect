<script setup>
import { ref, watch, reactive, onMounted, onBeforeUnmount } from 'vue'
import { deleteEntry, fetchTree, fsEventsUrl, moveEntry } from '../workspace.api.js'

const props = defineProps({
  root: { type: String, required: true },
  activePath: { type: String, default: null },
})

const emit = defineEmits(['open', 'externalCheck', 'renamed', 'moved', 'deleted'])

const rootChildren = ref([])
const expanded = reactive(new Map())   // path -> { children, loading, error }
const loadingRoot = ref(false)
const rootError = ref(null)
const refreshing = ref(false)

// Context menu state — single popup at a time, keyed by anchor path.
const menu = reactive({ open: false, x: 0, y: 0, path: '', isDir: false })

// Inline rename state — only one row can be in rename mode at a time.
const renaming = ref({ path: null, value: '', error: null, busy: false })

// Drag state — show a highlight on the folder under the pointer.
const dragOverPath = ref(null)
const dragOverRoot = ref(false)
const draggingPath = ref(null)

// `silent` (used by the live SSE watch / activity backstop) re-fetches in place
// WITHOUT flipping the loading flags — so the tree never blanks to "Loading…"
// on a background refresh. On a silent error we keep the last-good listing
// visible instead of replacing it with an error/blank; the next event retries.
async function loadDir(path, { silent = false } = {}) {
  if (!props.root) return
  if (path === '') {
    if (!silent) {
      loadingRoot.value = true
      rootError.value = null
    }
    try {
      const r = await fetchTree(props.root, '')
      rootChildren.value = r.children
      rootError.value = null
    } catch (e) {
      if (!silent) {
        rootError.value = e.body?.detail || e.message
        rootChildren.value = []
      }
    } finally {
      if (!silent) loadingRoot.value = false
    }
  } else {
    const slot = expanded.get(path) || { children: null, loading: false, error: null }
    if (!silent) {
      slot.loading = true
      slot.error = null
      expanded.set(path, slot)
    }
    try {
      const r = await fetchTree(props.root, path)
      slot.children = r.children
      slot.error = null
    } catch (e) {
      if (!silent) {
        slot.error = e.body?.detail || e.message
        slot.children = []
      }
    } finally {
      if (!silent) slot.loading = false
      expanded.set(path, { ...slot })
    }
  }
}

async function toggleExpand(path) {
  if (expanded.has(path)) {
    const slot = expanded.get(path)
    if (slot.children !== null && !slot.loading) {
      // Collapse — keep children cached so re-expand is instant.
      expanded.delete(path)
      return
    }
  }
  await loadDir(path)
}

function isExpanded(path) {
  const slot = expanded.get(path)
  return !!slot && slot.children !== null
}

function clickFile(path) {
  emit('open', path)
}

// Silent by default so neither the header refresh button nor the activity
// backstop blank the tree — the button still shows feedback via `refreshing`.
async function refresh({ silent = true } = {}) {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const expandedPaths = Array.from(expanded.keys())
    await Promise.all([loadDir('', { silent }), ...expandedPaths.map((p) => loadDir(p, { silent }))])
  } finally {
    refreshing.value = false
    emit('externalCheck')
  }
}

// ─── Context menu ───

function parentPathOf(path) {
  const idx = path.lastIndexOf('/')
  return idx === -1 ? '' : path.slice(0, idx)
}

function basenameOf(path) {
  const idx = path.lastIndexOf('/')
  return idx === -1 ? path : path.slice(idx + 1)
}

function openMenu(event, path, isDir) {
  event.preventDefault()
  event.stopPropagation()
  menu.open = true
  menu.x = event.clientX
  menu.y = event.clientY
  menu.path = path
  menu.isDir = isDir
}

function closeMenu() {
  menu.open = false
  menu.path = ''
}

function onDocClick(e) {
  if (!menu.open) return
  // Click anywhere outside the menu closes it.
  if (!(e.target instanceof Element) || !e.target.closest('.tree-context-menu')) {
    closeMenu()
  }
}

function onDocKey(e) {
  if (e.key === 'Escape') {
    if (renaming.value.path) cancelRename()
    if (menu.open) closeMenu()
  }
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onDocKey)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onDocKey)
})

// ─── Rename ───

function startRename(path) {
  closeMenu()
  renaming.value = {
    path,
    value: basenameOf(path),
    error: null,
    busy: false,
    focused: false,
  }
}

function cancelRename() {
  renaming.value = { path: null, value: '', error: null, busy: false, focused: false }
}

async function commitRename() {
  const oldPath = renaming.value.path
  const newName = renaming.value.value.trim()
  if (!oldPath || !newName) {
    cancelRename()
    return
  }
  if (newName === basenameOf(oldPath)) {
    cancelRename()
    return
  }
  if (newName.includes('/') || newName === '.' || newName === '..') {
    renaming.value.error = '잘못된 이름입니다'
    return
  }
  const parent = parentPathOf(oldPath)
  const newPath = parent ? `${parent}/${newName}` : newName
  renaming.value.busy = true
  try {
    const r = await moveEntry({ root: props.root, fromPath: oldPath, toPath: newPath })
    cancelRename()
    await refreshParent(parent)
    emit('renamed', { fromPath: oldPath, toPath: newPath, kind: r.moved_type })
  } catch (e) {
    renaming.value.error = e.body?.detail || e.message || '이름 변경 실패'
    renaming.value.busy = false
  }
}

async function refreshParent(parentPath) {
  if (parentPath === '') {
    await loadDir('')
  } else if (expanded.has(parentPath)) {
    await loadDir(parentPath)
  } else {
    // Also refresh root in case the change is visible at the top level.
    await loadDir('')
  }
}

// ─── Delete ───

async function confirmDelete(path, isDir) {
  closeMenu()
  const label = isDir ? '폴더' : '파일'
  const ok = window.confirm(
    `이 ${label}을(를) 삭제하시겠습니까?\n\n${path}\n\n${isDir ? '하위 내용까지 모두 삭제됩니다.' : ''}`,
  )
  if (!ok) return
  try {
    const r = await deleteEntry({ root: props.root, path })
    await refreshParent(parentPathOf(path))
    emit('deleted', { path, kind: r.deleted_type })
  } catch (e) {
    window.alert(`삭제 실패: ${e.body?.detail || e.message}`)
  }
}

// ─── Drag & drop ───

function onDragStart(event, path) {
  draggingPath.value = path
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('application/x-ccw-path', path)
    event.dataTransfer.setData('text/plain', path)
  }
}

function onDragEnd() {
  draggingPath.value = null
  dragOverPath.value = null
  dragOverRoot.value = false
}

function isDescendant(parent, child) {
  if (!parent) return false
  return child === parent || child.startsWith(parent + '/')
}

function onDragOverFolder(event, folderPath) {
  if (!draggingPath.value) return
  // Forbid dropping onto self or own descendants.
  if (isDescendant(draggingPath.value, folderPath)) return
  // Forbid dropping into current parent (no-op).
  if (parentPathOf(draggingPath.value) === folderPath) return
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
  dragOverPath.value = folderPath
}

function onDragLeaveFolder(folderPath) {
  if (dragOverPath.value === folderPath) dragOverPath.value = null
}

function onDragOverRoot(event) {
  if (!draggingPath.value) return
  if (parentPathOf(draggingPath.value) === '') return
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
  dragOverRoot.value = true
}

function onDragLeaveRoot() {
  dragOverRoot.value = false
}

async function performDrop(targetFolderPath) {
  const src = draggingPath.value
  draggingPath.value = null
  dragOverPath.value = null
  dragOverRoot.value = false
  if (!src) return
  if (isDescendant(src, targetFolderPath)) return
  const oldParent = parentPathOf(src)
  if (oldParent === targetFolderPath) return
  const base = basenameOf(src)
  const newPath = targetFolderPath ? `${targetFolderPath}/${base}` : base
  try {
    const r = await moveEntry({ root: props.root, fromPath: src, toPath: newPath })
    await Promise.all([
      refreshParent(oldParent),
      refreshParent(targetFolderPath),
    ])
    emit('moved', { fromPath: src, toPath: newPath, kind: r.moved_type })
  } catch (e) {
    window.alert(`이동 실패: ${e.body?.detail || e.message}`)
  }
}

function onDropFolder(event, folderPath) {
  event.preventDefault()
  performDrop(folderPath)
}

function onDropRoot(event) {
  event.preventDefault()
  performDrop('')
}

// ─── Live filesystem watch (SSE) ───
// The backend streams "these directories changed" hints so edits made by the
// embedded claude CLI (or any external tool) reflect without the manual refresh
// button. We reload ONLY directories that are currently visible — the root
// (always loaded) and folders the user has expanded — so the browser cost is
// bounded no matter how large the repo or how busy the watcher.

let es = null
let pendingDirs = new Set()
let flushTimer = null

function applyFsChanges() {
  flushTimer = null
  const dirs = pendingDirs
  pendingDirs = new Set()
  const toReload = []
  for (const d of dirs) {
    if (d === '') toReload.push('')          // root listing is always mounted
    else if (expanded.has(d)) toReload.push(d) // skip collapsed/unloaded dirs
  }
  if (!toReload.length) return
  Promise.all(toReload.map((p) => loadDir(p, { silent: true }))).then(() => emit('externalCheck'))
}

function onFsEvent(event) {
  let data
  try {
    data = JSON.parse(event.data)
  } catch {
    return
  }
  if (!Array.isArray(data?.dirs)) return
  for (const d of data.dirs) pendingDirs.add(d)
  // Coalesce bursts (a single claude tool call can touch many files).
  if (!flushTimer) flushTimer = setTimeout(applyFsChanges, 200)
}

function closeWatch() {
  if (es) {
    es.close()
    es = null
  }
  if (flushTimer) {
    clearTimeout(flushTimer)
    flushTimer = null
  }
  pendingDirs = new Set()
}

async function openWatch(rootAtCall) {
  closeWatch()
  if (!rootAtCall) return
  try {
    const url = await fsEventsUrl(rootAtCall)
    if (props.root !== rootAtCall) return  // root changed while resolving — stale
    es = new EventSource(url)
    es.onmessage = onFsEvent
    // EventSource auto-reconnects on transient errors; nothing to do here.
    es.onerror = () => {}
  } catch {
    // Non-fatal — the manual refresh button still works.
  }
}

// Reload from scratch when the root changes.
watch(
  () => props.root,
  (r) => {
    if (r) {
      rootChildren.value = []
      expanded.clear()
      cancelRename()
      closeMenu()
      loadDir('')
      openWatch(r)
    } else {
      closeWatch()
    }
  },
  { immediate: true },
)

onBeforeUnmount(closeWatch)

defineExpose({ refresh })
</script>

<template>
  <div class="file-tree-pane">
    <div class="tree-header">
      <span class="tree-title">Files</span>
      <button
        class="tree-refresh"
        :disabled="refreshing || loadingRoot"
        :title="refreshing ? '새로고침 중…' : '트리 새로고침'"
        @click="refresh"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"></polyline>
          <polyline points="1 20 1 14 7 14"></polyline>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
        </svg>
      </button>
    </div>

    <div
      class="tree-body"
      :class="{ 'is-drop-root': dragOverRoot }"
      @dragover="onDragOverRoot"
      @dragleave="onDragLeaveRoot"
      @drop="onDropRoot"
    >
      <div v-if="loadingRoot" class="tree-status">Loading…</div>
      <div v-else-if="rootError" class="tree-status tree-error">{{ rootError }}</div>
      <ul v-else class="tree-list">
        <TreeNodeView
          v-for="child in rootChildren"
          :key="child.name"
          :node="child"
          :path="child.name"
          :active-path="activePath"
          :expanded="expanded"
          :is-expanded="isExpanded"
          :toggle-expand="toggleExpand"
          :on-file-click="clickFile"
          :on-context-menu="openMenu"
          :on-drag-start="onDragStart"
          :on-drag-end="onDragEnd"
          :on-drag-over-folder="onDragOverFolder"
          :on-drag-leave-folder="onDragLeaveFolder"
          :on-drop-folder="onDropFolder"
          :drag-over-path="dragOverPath"
          :dragging-path="draggingPath"
          :renaming="renaming"
          :on-rename-input="(v) => renaming.value = v"
          :on-rename-commit="commitRename"
          :on-rename-cancel="cancelRename"
          :depth="0"
        />
      </ul>
    </div>

    <!-- Context menu portal -->
    <div
      v-if="menu.open"
      class="tree-context-menu"
      :style="{ top: menu.y + 'px', left: menu.x + 'px' }"
      @click.stop
    >
      <button class="ctx-item" @click="startRename(menu.path)">이름 변경</button>
      <button class="ctx-item ctx-danger" @click="confirmDelete(menu.path, menu.isDir)">삭제</button>
    </div>
  </div>
</template>

<script>
// Recursive tree node renderer split out so we don't fight Vue's setup
// component name resolution.
import { defineComponent, h } from 'vue'

const INDENT_PX = 18
const ROW_BASE_PX = 8

function fileKind(name) {
  const lower = name.toLowerCase()
  if (lower.endsWith('.md') || lower.endsWith('.markdown')) return 'md'
  if (
    lower === 'dockerfile' ||
    lower.startsWith('dockerfile.') ||
    lower.endsWith('.dockerfile') ||
    lower === 'docker-compose.yml' ||
    lower === 'docker-compose.yaml'
  ) return 'docker'
  return 'generic'
}

function chevronIcon(open) {
  return h(
    'svg',
    {
      class: ['tree-chevron', open ? 'is-open' : null],
      width: 10,
      height: 10,
      viewBox: '0 0 10 10',
      'aria-hidden': 'true',
      style: {
        display: 'block',
        transition: 'transform 120ms ease',
        transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
      },
    },
    [h('path', { d: 'M3 1.5 L7 5 L3 8.5', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.4, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' })],
  )
}

const ICON_BOX_STYLE = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '16px',
  minWidth: '16px',
  height: '16px',
  flexShrink: 0,
}

function folderIcon(open) {
  return h(
    'svg',
    {
      class: ['tree-icon', 'tree-icon-folder', open ? 'is-open' : null],
      width: 14,
      height: 14,
      viewBox: '0 0 16 16',
      'aria-hidden': 'true',
      style: { ...ICON_BOX_STYLE, color: 'var(--ccw-accent)' },
    },
    [
      h('path', {
        d: open
          ? 'M1.5 4.5 V12 a1 1 0 0 0 1 1 H13 a1 1 0 0 0 1-1 V6 a1 1 0 0 0-1-1 H7.5 L6 3.5 H2.5 a1 1 0 0 0-1 1 Z'
          : 'M1.5 4.5 a1 1 0 0 1 1-1 H6 L7.5 5 H13 a1 1 0 0 1 1 1 V12 a1 1 0 0 1-1 1 H2.5 a1 1 0 0 1-1-1 Z',
        fill: 'currentColor',
        opacity: 0.9,
      }),
    ],
  )
}

function fileIconFor(name) {
  const kind = fileKind(name)
  if (kind === 'md') {
    return h(
      'span',
      {
        class: ['tree-icon', 'tree-icon-md'],
        'aria-hidden': 'true',
        style: {
          ...ICON_BOX_STYLE,
          fontSize: '9px',
          fontWeight: 700,
          color: 'var(--ccw-accent)',
          letterSpacing: '-0.5px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        },
      },
      'MD',
    )
  }
  if (kind === 'docker') {
    return h(
      'span',
      {
        class: ['tree-icon', 'tree-icon-docker'],
        'aria-hidden': 'true',
        style: { ...ICON_BOX_STYLE, fontSize: '12px' },
      },
      '🐳',
    )
  }
  return h(
    'span',
    {
      class: ['tree-icon', 'tree-icon-generic'],
      'aria-hidden': 'true',
      style: { ...ICON_BOX_STYLE, color: 'var(--ccw-text-dim)', fontSize: '14px', lineHeight: 1 },
    },
    '·',
  )
}

const TreeNodeView = defineComponent({
  name: 'TreeNodeView',
  props: {
    node: { type: Object, required: true },
    path: { type: String, required: true },
    activePath: { type: String, default: null },
    expanded: { type: Object, required: true },
    isExpanded: { type: Function, required: true },
    toggleExpand: { type: Function, required: true },
    onFileClick: { type: Function, required: true },
    onContextMenu: { type: Function, required: true },
    onDragStart: { type: Function, required: true },
    onDragEnd: { type: Function, required: true },
    onDragOverFolder: { type: Function, required: true },
    onDragLeaveFolder: { type: Function, required: true },
    onDropFolder: { type: Function, required: true },
    dragOverPath: { type: String, default: null },
    draggingPath: { type: String, default: null },
    renaming: { type: Object, required: true },
    onRenameInput: { type: Function, required: true },
    onRenameCommit: { type: Function, required: true },
    onRenameCancel: { type: Function, required: true },
    depth: { type: Number, default: 0 },
  },
  setup(props) {
    return () => {
      const isDir = props.node.type === 'directory'
      const open = isDir && props.isExpanded(props.path)
      const slot = props.expanded.get(props.path)
      const isActive = !isDir && props.activePath === props.path
      const isRenaming = props.renaming.path === props.path
      const isDropTarget = isDir && props.dragOverPath === props.path
      const isDragSource = props.draggingPath === props.path

      const rowChildren = [
        h(
          'span',
          {
            class: 'tree-caret',
            style: {
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '12px',
              minWidth: '12px',
              flexShrink: 0,
              color: 'var(--ccw-text-dim)',
            },
          },
          isDir ? [chevronIcon(open)] : [],
        ),
        isDir ? folderIcon(open) : fileIconFor(props.node.name),
      ]

      if (isRenaming) {
        rowChildren.push(
          h('input', {
            class: 'tree-rename-input',
            value: props.renaming.value,
            disabled: props.renaming.busy,
            ref: (el) => {
              // Only focus on first mount of this input. Re-renders during
              // typing would otherwise yank the cursor back to selection.
              if (el && !props.renaming.focused) {
                props.renaming.focused = true
                queueMicrotask(() => {
                  try {
                    el.focus()
                    const dot = el.value.lastIndexOf('.')
                    el.setSelectionRange(0, dot > 0 ? dot : el.value.length)
                  } catch {}
                })
              }
            },
            style: {
              flex: 1,
              minWidth: 0,
              background: 'var(--ccw-bg-elevated)',
              color: 'var(--ccw-text)',
              border: '1px solid var(--ccw-accent)',
              borderRadius: '3px',
              padding: '1px 4px',
              fontSize: '13px',
              fontFamily: 'inherit',
              outline: 'none',
            },
            onClick: (e) => e.stopPropagation(),
            onInput: (e) => {
              props.renaming.value = e.target.value
              props.renaming.error = null
            },
            onKeydown: (e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                props.onRenameCommit()
              } else if (e.key === 'Escape') {
                e.preventDefault()
                props.onRenameCancel()
              }
            },
            onBlur: () => {
              // Commit on blur unless we're already busy.
              if (!props.renaming.busy) props.onRenameCommit()
            },
          }),
        )
        if (props.renaming.error) {
          rowChildren.push(
            h(
              'span',
              {
                class: 'tree-rename-error',
                style: { fontSize: '11px', color: 'var(--ccw-red)', marginLeft: '6px' },
              },
              props.renaming.error,
            ),
          )
        }
      } else {
        rowChildren.push(
          h(
            'span',
            {
              class: 'tree-name',
              style: { overflow: 'hidden', textOverflow: 'ellipsis' },
            },
            props.node.name,
          ),
        )
      }

      // Inline-style critical layout rules because TreeNodeView is a separate
      // component instance — the parent's <style scoped> rules don't reach
      // these elements without :deep().
      const row = h(
        'div',
        {
          class: [
            'tree-row',
            isDir ? 'tree-row-dir' : 'tree-row-file',
            isActive ? 'is-active' : null,
            isDropTarget ? 'is-drop-target' : null,
            isDragSource ? 'is-drag-source' : null,
          ],
          draggable: !isRenaming,
          style: {
            paddingLeft: `${ROW_BASE_PX + props.depth * INDENT_PX}px`,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            paddingTop: '4px',
            paddingBottom: '4px',
            paddingRight: '8px',
            whiteSpace: 'nowrap',
            userSelect: 'none',
            lineHeight: '1.5',
            opacity: isDragSource ? 0.5 : 1,
            background: isDropTarget ? 'var(--ccw-active)' : undefined,
          },
          onClick: () => {
            if (isRenaming) return
            if (isDir) props.toggleExpand(props.path)
            else props.onFileClick(props.path)
          },
          onContextmenu: (e) => props.onContextMenu(e, props.path, isDir),
          onDragstart: (e) => props.onDragStart(e, props.path),
          onDragend: () => props.onDragEnd(),
          onDragover: isDir ? (e) => props.onDragOverFolder(e, props.path) : null,
          onDragleave: isDir ? () => props.onDragLeaveFolder(props.path) : null,
          onDrop: isDir ? (e) => props.onDropFolder(e, props.path) : null,
        },
        rowChildren,
      )

      const children = []
      if (isDir && open && slot) {
        const childIndent = `${ROW_BASE_PX + (props.depth + 1) * INDENT_PX}px`
        if (slot.loading) {
          children.push(
            h('div', { class: 'tree-status', style: { paddingLeft: childIndent } }, 'Loading…'),
          )
        } else if (slot.error) {
          children.push(
            h(
              'div',
              { class: 'tree-status tree-error', style: { paddingLeft: childIndent } },
              slot.error,
            ),
          )
        } else if (slot.children && slot.children.length > 0) {
          for (const c of slot.children) {
            children.push(
              h(TreeNodeView, {
                key: c.name,
                node: c,
                path: `${props.path}/${c.name}`,
                activePath: props.activePath,
                expanded: props.expanded,
                isExpanded: props.isExpanded,
                toggleExpand: props.toggleExpand,
                onFileClick: props.onFileClick,
                onContextMenu: props.onContextMenu,
                onDragStart: props.onDragStart,
                onDragEnd: props.onDragEnd,
                onDragOverFolder: props.onDragOverFolder,
                onDragLeaveFolder: props.onDragLeaveFolder,
                onDropFolder: props.onDropFolder,
                dragOverPath: props.dragOverPath,
                draggingPath: props.draggingPath,
                renaming: props.renaming,
                onRenameInput: props.onRenameInput,
                onRenameCommit: props.onRenameCommit,
                onRenameCancel: props.onRenameCancel,
                depth: props.depth + 1,
              }),
            )
          }
        } else {
          children.push(
            h(
              'div',
              { class: 'tree-status tree-empty', style: { paddingLeft: childIndent } },
              '(empty)',
            ),
          )
        }
      }

      return h('li', { class: 'tree-item' }, [row, ...children])
    }
  },
})

export default {
  components: { TreeNodeView },
}
</script>

<style scoped>
.file-tree-pane {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--ccw-bg);
  color: var(--ccw-text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  font-size: 13px;
  overflow: hidden;
  position: relative;
}

.tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--ccw-border);
  background: var(--ccw-bg-elevated);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.5px;
  color: var(--ccw-text-muted);
}

.tree-title {
  opacity: 0.85;
}

.tree-refresh {
  background: transparent;
  border: none;
  color: var(--ccw-accent);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  border-radius: 3px;
}

.tree-refresh:hover:not(:disabled) {
  background: var(--ccw-hover);
  color: var(--ccw-text);
}

.tree-refresh:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tree-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  transition: box-shadow 120ms ease;
}

.tree-body.is-drop-root {
  box-shadow: inset 0 0 0 2px var(--ccw-teal);
}

.tree-list {
  list-style: none;
  margin: 0;
  padding: 4px 0;
}

.tree-list :deep(.tree-item) {
  list-style: none;
}

.tree-list :deep(.tree-row:hover) {
  background: var(--ccw-hover);
}

.tree-list :deep(.tree-row.is-active) {
  background: var(--ccw-active);
  color: var(--ccw-text);
}

.tree-list :deep(.tree-row.is-drop-target) {
  outline: 1px dashed var(--ccw-teal);
  outline-offset: -2px;
}

.tree-list :deep(.tree-status) {
  font-size: 12px;
  color: var(--ccw-text-dim);
  font-style: italic;
  padding: 4px 10px;
}

.tree-list :deep(.tree-error) {
  color: var(--ccw-red);
}

.tree-list :deep(.tree-empty) {
  opacity: 0.6;
}

.tree-context-menu {
  position: fixed;
  z-index: 1000;
  background: var(--ccw-bg-elevated);
  border: 1px solid var(--ccw-border);
  border-radius: 4px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.4);
  padding: 4px 0;
  min-width: 140px;
  display: flex;
  flex-direction: column;
}

.ctx-item {
  background: transparent;
  border: none;
  color: var(--ccw-text);
  text-align: left;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
}

.ctx-item:hover {
  background: var(--ccw-active);
}

.ctx-item.ctx-danger {
  color: var(--ccw-red);
}

.ctx-item.ctx-danger:hover {
  background: rgba(247, 118, 142, 0.18);
}
</style>
