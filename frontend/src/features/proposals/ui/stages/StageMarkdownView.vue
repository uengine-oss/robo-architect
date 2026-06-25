<template>
  <div class="smv" v-html="html"></div>
</template>

<script setup>
import { computed } from 'vue'
import { artifactToMarkdown, renderMarkdown } from './stageMarkdown'

const props = defineProps({
  stage: { type: String, required: true },
  artifact: { type: Object, default: () => ({}) },
})

const html = computed(() => renderMarkdown(artifactToMarkdown(props.stage, props.artifact)))
</script>

<style scoped>
.smv { font-size: 12px; color: var(--color-text); line-height: 1.55; }
.smv :deep(h1) { font-size: 15px; color: var(--color-text-bright); margin: 0 0 8px; }
.smv :deep(h2) { font-size: 13px; color: var(--color-text-bright); margin: 14px 0 6px; border-bottom: 1px solid var(--color-border); padding-bottom: 3px; }
.smv :deep(h3), .smv :deep(h4), .smv :deep(h5) { font-size: 12px; color: var(--color-text-bright); margin: 10px 0 4px; }
.smv :deep(p) { margin: 4px 0; }
.smv :deep(ul) { margin: 4px 0; padding-left: 18px; }
.smv :deep(li) { margin: 1px 0; }
.smv :deep(blockquote) { margin: 6px 0; padding: 4px 10px; border-left: 3px solid var(--color-accent); color: var(--color-text-light); }
.smv :deep(code) { background: var(--color-bg-secondary); border-radius: 3px; padding: 1px 4px; font-size: 11px; }
.smv :deep(strong) { color: var(--color-text-bright); }
.smv :deep(.smv__tbl) { width: 100%; border-collapse: collapse; font-size: 11px; margin: 6px 0; }
.smv :deep(.smv__tbl th), .smv :deep(.smv__tbl td) { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--color-border); vertical-align: top; }
.smv :deep(.smv__tbl th) { color: var(--color-text-light); font-weight: 600; }
.smv :deep(.smv__empty) { color: var(--color-text-light); font-style: italic; }
</style>
