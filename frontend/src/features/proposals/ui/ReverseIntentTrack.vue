<template>
  <div class="reverse-track">
    <div class="rt-head">
      <h4>{{ t('proposals.reverse.title') }}</h4>
      <button v-if="!rs.active && !rs.done" @click="run" class="btn btn--primary">
        {{ t('proposals.reverse.run') }}
      </button>
      <span v-else-if="rs.active" class="rt-status">
        <span class="spinner spinner--sm" /> {{ rs.phase || t('proposals.reverse.running') }}
      </span>
    </div>

    <p v-if="rs.error" class="rt-error">{{ rs.error }}</p>

    <!-- 데이터 그룹 카드 (US2) -->
    <div v-if="rs.groups.length" class="rt-groups">
      <div class="rt-groups__title">{{ t('proposals.reverse.groups') }} ({{ rs.groups.length }})</div>
      <div v-for="g in rs.groups" :key="g.table" class="rt-card">
        <div class="rt-card__head">
          <span class="rt-card__title">{{ g.title }}</span>
          <span class="rt-badge" :class="'rt-badge--' + g.kind">{{ g.kindLabel }}</span>
          <span class="rt-badge rt-badge--st">{{ g.stereotypeLabel }}</span>
          <span class="rt-card__count">작업 {{ g.opCount }}</span>
        </div>
        <ul class="rt-ops">
          <li v-for="(o, i) in g.ops" :key="i">{{ o.logicalName }}</li>
        </ul>
      </div>
    </div>

    <!-- 실시간 진행 로그 -->
    <div v-if="rs.active && rs.logLines.length" ref="logEl" class="rt-log">
      <div v-for="(l, i) in rs.logLines" :key="i" class="rt-log__line">{{ l }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useI18n } from '../../../app/i18n'
import { useProposalsStore } from '../proposals.store'

const props = defineProps({ proposalId: { type: String, required: true } })
const { t } = useI18n()
const store = useProposalsStore()
const rs = computed(() => store.reverseStream)
const logEl = ref(null)

function run() {
  store.subscribeToReverseIntent(props.proposalId)
}

watch(() => rs.value.logLines?.length, async () => {
  await nextTick()
  if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight
})
</script>

<style scoped>
.reverse-track { padding: 12px; }
.rt-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.rt-head h4 { margin: 0; font-size: 14px; font-weight: 600; color: var(--color-text-bright); }
.rt-status { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--color-text-light); }
.rt-error { color: var(--color-danger); font-size: 13px; }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--primary { background: var(--color-accent); color: #fff; }
.spinner--sm { width: 12px; height: 12px; border: 2px solid var(--color-border); border-top-color: var(--color-accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.rt-groups__title { font-size: 12px; font-weight: 600; color: var(--color-text-light); margin-bottom: 6px; }
.rt-card { border: 1px solid var(--color-border); border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; background: var(--color-bg-secondary); }
.rt-card__head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rt-card__title { font-size: 13px; font-weight: 600; color: var(--color-text-bright); }
.rt-card__count { margin-left: auto; font-size: 11px; color: var(--color-text-light); }
.rt-badge { font-size: 10px; padding: 1px 7px; border-radius: 10px; background: var(--color-bg-tertiary); color: var(--color-text); }
.rt-badge--write { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.rt-badge--read { background: var(--color-bg-tertiary); }
.rt-badge--st { background: transparent; border: 1px solid var(--color-border); color: var(--color-text-light); }
.rt-ops { margin: 8px 0 0; padding-left: 18px; }
.rt-ops li { font-size: 12px; color: var(--color-text); line-height: 1.6; }
.rt-log { background: #0f172a; border-radius: 6px; padding: 10px 12px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #cbd5e1; margin-top: 10px; }
.rt-log__line { padding: 1px 0; white-space: pre-wrap; word-break: break-all; }
</style>
