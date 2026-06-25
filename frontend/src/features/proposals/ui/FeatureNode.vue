<template>
  <div class="diff-entry diff-entry--feature">
    <div
      class="entry-header"
      :class="{ 'entry-header--clickable': hasUS }"
      @click="hasUS && toggle(keyOf(feature.node))"
    >
      <span v-if="hasUS" class="caret" :class="{ 'caret--open': isOpen(keyOf(feature.node)) }">▶</span>
      <span class="entry-title">{{ feature.node.entityTitle }}</span>
      <span class="type-chip">{{ t('proposals.term.feature') }}</span>
      <span :class="opClass(feature.node.op)">{{ feature.node.op }}</span>
    </div>
  </div>
  <div v-if="hasUS && isOpen(keyOf(feature.node))" class="children">
    <div v-for="us in feature.userStories" :key="keyOf(us)" class="diff-entry diff-entry--us">
      <StrategicEntry :entry="us" :op-class="opClass" :type-label="t('proposals.term.userStory')" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StrategicEntry from './StrategicEntry.vue'
import { useI18n } from '../../../app/i18n'

const { t } = useI18n()

const props = defineProps({
  feature: { type: Object, required: true }, // { node, userStories }
  opClass: { type: Function, required: true },
  isOpen: { type: Function, required: true },
  toggle: { type: Function, required: true },
  keyOf: { type: Function, required: true },
})

const hasUS = computed(() => props.feature.userStories?.length > 0)
</script>

<style scoped>
.diff-entry { background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; }
.diff-entry--feature { background: var(--color-bg-secondary); }
.diff-entry--us { background: var(--color-bg-secondary); }
.children { margin-left: 10px; padding-left: 12px; border-left: 2px solid var(--color-border); margin-top: 6px; }
.entry-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.entry-header--clickable { cursor: pointer; user-select: none; }
.caret { font-size: 9px; color: var(--color-text-light); display: inline-block; transition: transform 0.15s ease; }
.caret--open { transform: rotate(90deg); }
.entry-title { font-weight: 500; color: var(--color-text); }
.type-chip { font-size: 10px; font-weight: 600; padding: 1px 7px; border-radius: 9999px; border: 1px solid var(--color-border); color: var(--color-text-light); background: transparent; white-space: nowrap; }
.op-badge { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; text-transform: uppercase; }
.op-badge--create { background: var(--status-green-bg); color: var(--status-green-fg); }
.op-badge--modify { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.op-badge--delete { background: var(--status-red-bg); color: var(--status-red-fg); }
</style>
