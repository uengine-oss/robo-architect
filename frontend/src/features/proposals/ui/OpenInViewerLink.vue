<template>
  <button
    class="open-in-viewer"
    :class="{ 'open-in-viewer--disabled': disabled }"
    :disabled="disabled || busy"
    :title="disabled ? reason : t('proposals.openViewer.openInViewer', { viewer: viewerLabel })"
    @click.stop="onClick"
  >
    <span class="oiv-icon">{{ busy ? '…' : '↗' }}</span>
    <span class="oiv-text">{{ disabled ? t('proposals.openViewer.openDisabled') : t('proposals.openViewer.open') }}</span>
  </button>
</template>

<script setup>
import { ref, computed } from 'vue'
import { openPreview, LABEL_TO_VIEWER, VIEWER_TO_TAB } from '../proposalPreview'
import { useI18n } from '../../../app/i18n'

const { t } = useI18n()

const props = defineProps({
  proposalId: { type: String, required: true },
  nodeId: { type: String, default: null },
  nodeLabel: { type: String, default: '' },
  nodeTitle: { type: String, default: '' },
})

const busy = ref(false)
const failedReason = ref(null)

// 프런트 1차 추정으로 미매핑 라벨이면 즉시 비활성(끊긴 링크 금지, FR-010).
const mappedViewer = computed(() => LABEL_TO_VIEWER[props.nodeLabel] || null)
const disabled = computed(() => !mappedViewer.value || !!failedReason.value)
const viewerLabel = computed(() => VIEWER_TO_TAB[mappedViewer.value] || '')
const reason = computed(() =>
  failedReason.value || (!mappedViewer.value ? t('proposals.openViewer.noMapping', { label: props.nodeLabel }) : ''))

async function onClick() {
  if (disabled.value || busy.value) return
  busy.value = true
  try {
    const res = await openPreview(props.proposalId, {
      nodeId: props.nodeId, nodeLabel: props.nodeLabel, nodeTitle: props.nodeTitle,
    })
    if (res && res.renderable === false) failedReason.value = res.reason || t('proposals.openViewer.previewUnavailable')
  } catch (e) {
    failedReason.value = e?.message || t('proposals.openViewer.openFailed')
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.open-in-viewer {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; padding: 2px 7px; border-radius: 4px;
  border: 1px solid var(--color-border); background: var(--color-bg-secondary);
  color: var(--color-accent, #2563eb); cursor: pointer; white-space: nowrap;
}
.open-in-viewer:hover:not(:disabled) { background: var(--color-bg-tertiary); }
.open-in-viewer--disabled { color: var(--color-text-light); cursor: not-allowed; opacity: 0.6; }
.oiv-icon { font-weight: 700; }
</style>
