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
              v-if="canOpenLive(entry)"
              :proposalId="proposalId"
              :nodeId="entry.nodeId"
              :nodeLabel="entry.nodeLabel"
              :nodeTitle="entry.nodeTitle"
            />
            <button v-else class="diff-preview-btn" @click="previewEntry = entry">Diff 미리보기</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="previewEntry" class="diff-modal">
      <div class="diff-modal__panel">
        <div class="diff-modal__head">
          <strong>{{ previewEntry.nodeTitle || previewEntry.nodeId || '신규 항목' }}</strong>
          <button class="diff-modal__close" @click="previewEntry = null">×</button>
        </div>
        <p class="diff-modal__hint">아직 live Neo4j node id가 없는 신규 diff 항목입니다. Accept 후 실제 뷰어에서 열 수 있습니다.</p>
        <pre class="diff-modal__body">{{ JSON.stringify(previewEntry, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import OpenInViewerLink from './OpenInViewerLink.vue'
import { useI18n } from '../../../app/i18n'

const { t } = useI18n()

const props = defineProps({
  impactMap: { type: Array, default: () => [] },
  // 040 — 있으면 행마다 '열기'(미리보기 뷰어) 진입점을 표시.
  proposalId: { type: String, default: null },
})
const previewEntry = ref(null)

const sortOrder = { HIGH: 0, MEDIUM: 1, LOW: 2, NONE: 3 }
const sortedEntries = computed(() =>
  [...(props.impactMap || [])].sort((a, b) =>
    (sortOrder[a.conflictLevel] ?? 9) - (sortOrder[b.conflictLevel] ?? 9)
  )
)

function canOpenLive(entry) {
  const id = String(entry?.nodeId || '')
  return !!id && !id.includes(':') && id !== '—'
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
.diff-preview-btn { font-size: 11px; padding: 2px 7px; border-radius: 4px; border: 1px solid var(--color-border); background: var(--color-bg-secondary); color: var(--color-accent); cursor: pointer; white-space: nowrap; }
.diff-modal { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.45); }
.diff-modal__panel { width: min(760px, 92vw); max-height: 82vh; overflow: hidden; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: 10px; box-shadow: 0 12px 40px rgba(0,0,0,0.35); }
.diff-modal__head { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; border-bottom: 1px solid var(--color-border); color: var(--color-text-bright); }
.diff-modal__close { border: none; background: transparent; color: var(--color-text); font-size: 18px; cursor: pointer; }
.diff-modal__hint { margin: 10px 14px; font-size: 12px; color: var(--color-text-light); }
.diff-modal__body { margin: 0; padding: 12px 14px; max-height: 58vh; overflow: auto; background: #0f172a; color: #cbd5e1; font-size: 11px; line-height: 1.5; }
</style>
