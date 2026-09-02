<script setup>
/** 생성 결과 탐색기 — 메모리 트리를 접었다 폈다 한다. */
import { computed, ref, watch } from 'vue'
import { buildTree, collapseChains } from '../tree.js'
import GeneratedTreeNode from './GeneratedTreeNode.vue'

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
    <GeneratedTreeNode
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

<style scoped>
.gt { padding: 4px 0; }
</style>
