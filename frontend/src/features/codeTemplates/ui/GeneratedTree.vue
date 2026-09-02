<script setup>
/** 생성 결과 탐색기 — 메모리 트리를 접었다 폈다 한다. */
import { computed, ref, watch } from 'vue'
import { buildTree, collapseChains } from '../tree.js'

const props = defineProps({
  files: { type: Array, default: () => [] },
  activePath: { type: String, default: '' },
})
const emit = defineEmits(['open'])

const expanded = ref(new Set())

const tree = computed(() => collapseChains(buildTree(props.files)))

// 새로 생성하면 최상위(=BC)는 펼쳐 둔다. 닫힌 트리만 보이면 무엇이 나왔는지
// 알 수 없다.
watch(
  tree,
  (t) => {
    const next = new Set()
    for (const n of t) if (n.dir) next.add(n.path)
    expanded.value = next
  },
  { immediate: true },
)

function toggle(node) {
  const next = new Set(expanded.value)
  if (next.has(node.path)) next.delete(node.path)
  else next.add(node.path)
  expanded.value = next
}

const isOpen = (node) => expanded.value.has(node.path)
</script>

<template>
  <div class="gt">
    <TreeNode
      v-for="n in tree"
      :key="n.path"
      :node="n"
      :depth="0"
      :active-path="activePath"
      :is-open="isOpen"
      @toggle="toggle"
      @open="emit('open', $event)"
    />
  </div>
</template>

<script>
// 재귀 컴포넌트. 자바 생성물은 깊어서 평평하게 못 그린다.
const TreeNode = {
  name: 'TreeNode',
  props: {
    node: { type: Object, required: true },
    depth: { type: Number, default: 0 },
    activePath: { type: String, default: '' },
    isOpen: { type: Function, required: true },
  },
  emits: ['toggle', 'open'],
  template: `
    <div>
      <button
        class="gt__row"
        :class="{ 'is-dir': node.dir, 'is-active': !node.dir && node.path === activePath }"
        :style="{ paddingLeft: (depth * 12 + 6) + 'px' }"
        :title="node.path"
        @click="node.dir ? $emit('toggle', node) : $emit('open', node.file)"
      >
        <span class="gt__caret">{{ node.dir ? (isOpen(node) ? '▾' : '▸') : '' }}</span>
        <span class="gt__name">{{ node.name }}</span>
        <span v-if="node.dir" class="gt__count">{{ node.children.length }}</span>
      </button>
      <template v-if="node.dir && isOpen(node)">
        <TreeNode
          v-for="c in node.children"
          :key="c.path"
          :node="c"
          :depth="depth + 1"
          :active-path="activePath"
          :is-open="isOpen"
          @toggle="$emit('toggle', $event)"
          @open="$emit('open', $event)"
        />
      </template>
    </div>
  `,
}
export default { components: { TreeNode } }
</script>

<style scoped>
.gt { font-size: 12px; }
.gt__row {
  display: flex; align-items: center; gap: 4px; width: 100%;
  border: 0; background: none; color: inherit; cursor: pointer;
  padding: 2px 6px; text-align: left; line-height: 1.6;
}
.gt__row:hover { background: rgba(128, 128, 128, 0.12); }
.gt__row.is-active { background: rgba(66, 133, 244, 0.2); }
.gt__row.is-dir .gt__name { font-weight: 600; }
.gt__caret { width: 10px; flex: none; opacity: 0.6; }
.gt__name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gt__count { margin-left: auto; opacity: 0.4; font-size: 11px; }
</style>
