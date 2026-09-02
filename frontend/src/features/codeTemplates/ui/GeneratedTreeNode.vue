<script setup>
/**
 * 생성 결과 트리의 노드 하나 — 자기 자신을 재귀로 그린다.
 *
 * **런타임 `template:` 문자열로 두면 안 된다.** 이 앱은 Vue 런타임 전용
 * 빌드라 문자열 템플릿을 컴파일하지 못하고, 콘솔에
 * "runtime compilation is not supported" 만 남기고 아무것도 안 그린다.
 * 빌드는 통과하므로 실행해 보기 전까지 드러나지 않는다. SFC 로 두면
 * 컴파일 시점에 처리되고 파일 이름으로 자기 참조가 된다.
 */
defineOptions({ name: 'GeneratedTreeNode' })

defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  activePath: { type: String, default: '' },
  isOpen: { type: Function, required: true },
})

defineEmits(['toggle', 'open'])
</script>

<template>
  <div>
    <button
      class="gtn"
      :class="{ 'is-dir': node.dir, 'is-active': !node.dir && node.path === activePath }"
      :style="{ paddingLeft: depth * 12 + 8 + 'px' }"
      :title="node.path"
      @click="node.dir ? $emit('toggle', node) : $emit('open', node.file)"
    >
      <span class="gtn__caret">{{ node.dir ? (isOpen(node) ? '▾' : '▸') : '' }}</span>
      <span class="gtn__name">{{ node.name }}</span>
      <span v-if="node.dir" class="gtn__count">{{ node.children.length }}</span>
    </button>

    <template v-if="node.dir && isOpen(node)">
      <GeneratedTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :depth="depth + 1"
        :active-path="activePath"
        :is-open="isOpen"
        @toggle="$emit('toggle', $event)"
        @open="$emit('open', $event)"
      />
    </template>
  </div>
</template>

<style scoped>
.gtn {
  display: flex; align-items: center; gap: 5px; width: 100%;
  border: 0; background: none; cursor: pointer; text-align: left;
  color: var(--ccw-text-muted); font-size: 12px; line-height: 1.7;
  padding: 1px 8px; font-family: inherit;
}
.gtn:hover { background: var(--ccw-hover); color: var(--ccw-text); }
.gtn.is-active { background: var(--ccw-active); color: var(--ccw-text); }
.gtn.is-dir { color: var(--ccw-text); font-weight: 500; }
.gtn__caret { width: 10px; flex: none; color: var(--ccw-text-dim); }
.gtn__name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gtn__count { margin-left: auto; color: var(--ccw-text-dim); font-size: 11px; }
</style>
