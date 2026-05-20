<script setup>
import { ref, watch, reactive } from 'vue'
import { fetchTree } from '../workspace.api.js'

const props = defineProps({
  root: { type: String, required: true },
  activePath: { type: String, default: null },
})

const emit = defineEmits(['open', 'externalCheck'])

const rootChildren = ref([])
const expanded = reactive(new Map())   // path -> { children, loading, error }
const loadingRoot = ref(false)
const rootError = ref(null)
const refreshing = ref(false)

async function loadDir(path) {
  if (!props.root) return
  if (path === '') {
    loadingRoot.value = true
    rootError.value = null
    try {
      const r = await fetchTree(props.root, '')
      rootChildren.value = r.children
    } catch (e) {
      rootError.value = e.body?.detail || e.message
      rootChildren.value = []
    } finally {
      loadingRoot.value = false
    }
  } else {
    const slot = expanded.get(path) || { children: null, loading: false, error: null }
    slot.loading = true
    slot.error = null
    expanded.set(path, slot)
    try {
      const r = await fetchTree(props.root, path)
      slot.children = r.children
      slot.error = null
    } catch (e) {
      slot.error = e.body?.detail || e.message
      slot.children = []
    } finally {
      slot.loading = false
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

async function refresh() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const expandedPaths = Array.from(expanded.keys())
    await Promise.all([loadDir(''), ...expandedPaths.map((p) => loadDir(p))])
  } finally {
    refreshing.value = false
    emit('externalCheck')
  }
}

// Reload from scratch when the root changes.
watch(
  () => props.root,
  (r) => {
    if (r) {
      rootChildren.value = []
      expanded.clear()
      loadDir('')
    }
  },
  { immediate: true },
)

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

    <div class="tree-body">
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
          :depth="0"
        />
      </ul>
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
      style: { ...ICON_BOX_STYLE, color: '#7aa2f7' },
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
          color: '#7aa2f7',
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
      style: { ...ICON_BOX_STYLE, color: '#565f89', fontSize: '14px', lineHeight: 1 },
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
    depth: { type: Number, default: 0 },
  },
  setup(props) {
    return () => {
      const isDir = props.node.type === 'directory'
      const open = isDir && props.isExpanded(props.path)
      const slot = props.expanded.get(props.path)
      const isActive = !isDir && props.activePath === props.path

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
          ],
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
          },
          onClick: () => {
            if (isDir) props.toggleExpand(props.path)
            else props.onFileClick(props.path)
          },
        },
        [
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
                color: '#565f89',
              },
            },
            isDir ? [chevronIcon(open)] : [],
          ),
          isDir ? folderIcon(open) : fileIconFor(props.node.name),
          h(
            'span',
            {
              class: 'tree-name',
              style: { overflow: 'hidden', textOverflow: 'ellipsis' },
            },
            props.node.name,
          ),
        ],
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
  background: #1a1b26;
  color: #c0caf5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  font-size: 13px;
  overflow: hidden;
}

.tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid #2f3242;
  background: #15161e;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.5px;
  color: #a9b1d6;
}

.tree-title {
  opacity: 0.85;
}

.tree-refresh {
  background: transparent;
  border: none;
  color: #7aa2f7;
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  border-radius: 3px;
}

.tree-refresh:hover:not(:disabled) {
  background: rgba(122, 162, 247, 0.12);
  color: #c0caf5;
}

.tree-refresh:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tree-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
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
  background: rgba(122, 162, 247, 0.10);
}

.tree-list :deep(.tree-row.is-active) {
  background: rgba(122, 162, 247, 0.22);
  color: #ffffff;
}

.tree-list :deep(.tree-status) {
  font-size: 12px;
  color: #565f89;
  font-style: italic;
  padding: 4px 10px;
}

.tree-list :deep(.tree-error) {
  color: #f7768e;
}

.tree-list :deep(.tree-empty) {
  opacity: 0.6;
}
</style>
