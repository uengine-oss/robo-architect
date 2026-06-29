<template>
  <div class="impact-map">
    <div v-if="!impactMap?.length" class="impact-map__empty">{{ t('proposals.impactMap.empty') }}</div>
    <table v-else class="impact-table">
      <thead>
        <tr>
          <th>{{ t('proposals.impactMap.colNodeId') }}</th>
          <th>{{ t('proposals.impactMap.colType') }}</th>
          <th>{{ t('proposals.impactMap.colName') }}</th>
          <th>{{ t('proposals.impactMap.colConflict') }}</th>
          <th>{{ t('proposals.impactMap.colReason') }}</th>
          <th v-if="proposalId"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="entry in sortedEntries" :key="entry.nodeId || entry.nodeTitle">
          <td class="mono">{{ entry.nodeId || '—' }}</td>
          <td><span class="node-label">{{ entry.nodeLabel }}</span></td>
          <td>{{ entry.nodeTitle }}</td>
          <td>
            <span :class="['conflict-badge', `conflict-badge--${(entry.conflictLevel || 'NONE').toLowerCase()}`]">
              {{ entry.conflictLevel || 'NONE' }}
            </span>
          </td>
          <td class="reason-cell">{{ entry.reason }}</td>
          <td v-if="proposalId" class="open-cell">
            <OpenInViewerLink
              v-if="canOpenCandidate(entry)"
              :proposalId="proposalId"
              :nodeId="entry.nodeId"
              :nodeLabel="entry.nodeLabel"
              :nodeTitle="entry.nodeTitle"
            />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import OpenInViewerLink from './OpenInViewerLink.vue'
import { useI18n } from '../../../app/i18n'

const { t } = useI18n()

const props = defineProps({
  impactMap: { type: Array, default: () => [] },
  // 040 — 있으면 행마다 '열기'(미리보기 뷰어) 진입점을 표시.
  proposalId: { type: String, default: null },
})

const sortOrder = { HIGH: 0, MEDIUM: 1, LOW: 2, NONE: 3 }
const sortedEntries = computed(() =>
  [...(props.impactMap || [])].sort((a, b) =>
    (sortOrder[a.conflictLevel] ?? 9) - (sortOrder[b.conflictLevel] ?? 9)
  )
)

function canOpenCandidate(entry) {
  return !!(entry?.nodeId || entry?.nodeTitle)
}
</script>

<style scoped>
.impact-map { font-size: 13px; }
.impact-map__empty { color: var(--color-text-light); font-style: italic; padding: 12px 0; }
.impact-table { width: 100%; border-collapse: collapse; }
.impact-table th { text-align: left; font-size: 11px; font-weight: 600; color: var(--color-text-light); text-transform: uppercase; padding: 6px 10px; border-bottom: 2px solid var(--color-border); }
.impact-table td { padding: 8px 10px; border-bottom: 1px solid var(--color-border); vertical-align: top; }
.mono { font-family: monospace; font-size: 12px; color: var(--color-text); }
.node-label { background: var(--color-bg-tertiary); color: var(--color-text); font-size: 11px; padding: 1px 5px; border-radius: 3px; }
.conflict-badge { font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; }
.conflict-badge--high { background: var(--status-red-bg); color: var(--status-red-fg); }
.conflict-badge--medium { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.conflict-badge--low { background: var(--status-green-bg); color: var(--status-green-fg); }
.conflict-badge--none { background: var(--status-neutral-bg); color: var(--status-neutral-fg); }
.reason-cell { color: var(--color-text-light); max-width: 280px; }
</style>
