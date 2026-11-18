<template>
  <!-- D-5 ⑰ ① Accept 요약 — 이 프로포절이 만든 UI 에 와이어프레임을 붙이는 단추.
       LLM 호출이 UI 수만큼 들어서 **자동이 아니라 단추**다. -->
  <div v-if="info && info.total > 0" class="ui-wf">
    <div class="ui-wf__row">
      <span class="ui-wf__label">
        {{ t('proposals.uiWireframes.summary', { n: info.total, missing: info.missing }) }}
      </span>
      <template v-if="running">
        <span class="ui-wf__progress"><span class="spinner" />
          {{ t('proposals.uiWireframes.progress', { done: progress.uisDone, total: progress.uisTotal }) }}
          <i v-if="progress.currentTarget"> · {{ progress.currentTarget }}</i>
        </span>
        <button class="btn btn--sm" @click="stop">{{ t('proposals.common.stop') }}</button>
      </template>
      <template v-else>
        <button v-if="info.missing > 0" class="btn btn--sm btn--primary" @click="start(true)">
          {{ t('proposals.uiWireframes.generate', { n: info.missing }) }}
        </button>
        <button v-else class="btn btn--sm" @click="start(false)">
          {{ t('proposals.uiWireframes.regenerate') }}
        </button>
      </template>
    </div>
    <p v-if="lastSummary" class="ui-wf__done">
      {{ t('proposals.uiWireframes.done', { generated: lastSummary.generated, failures: lastSummary.failures }) }}
    </p>
    <ul v-if="failures.length" class="ui-wf__failures">
      <li v-for="f in failures" :key="f.uiId">{{ f.displayName }} — {{ f.lastErrorKr }}</li>
    </ul>
    <p v-if="error" class="ui-wf__error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useProposalsStore } from '../proposals.store'
import { useI18n } from '../../../app/i18n'

const props = defineProps({ proposalId: { type: String, required: true } })
const store = useProposalsStore()
const { t } = useI18n()

const info = ref(null)
const running = ref(false)
const progress = ref({ uisDone: 0, uisTotal: 0, currentTarget: null })
const failures = ref([])
const lastSummary = ref(null)
const error = ref('')
let closeStream = null

async function load() {
  try { info.value = await store.fetchProposalUis(props.proposalId) } catch { info.value = null }
}

function start(onlyMissing) {
  if (running.value) return
  running.value = true
  failures.value = []
  lastSummary.value = null
  error.value = ''
  progress.value = { uisDone: 0, uisTotal: onlyMissing ? info.value.missing : info.value.total, currentTarget: null }
  closeStream = store.streamProposalUiWireframes(props.proposalId, {
    onlyMissing,
    onEvent: (name, d) => {
      if (name === 'progress') progress.value = d
      else if (name === 'ui_failed') failures.value.push(d)
    },
    onClose: (d) => { running.value = false; lastSummary.value = d?.summary || null; closeStream = null; load() },
    onError: () => { running.value = false; error.value = t('proposals.uiWireframes.dropped'); closeStream = null; load() },
  })
}

// 중지 — 스트림을 닫는다. 진행 중이던 한 건은 서버에서 끝까지 가고, 다음 건은 안 간다.
function stop() {
  if (closeStream) closeStream()
  closeStream = null
  running.value = false
  load()
}

onMounted(load)
onBeforeUnmount(() => { if (closeStream) closeStream() })
</script>

<style scoped>
.ui-wf { margin-top: 14px; padding: 10px 12px; border: 1px solid var(--color-border); border-radius: 8px; text-align: left; font-size: 12px; }
.ui-wf__row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ui-wf__label { font-weight: 600; }
.ui-wf__progress { display: inline-flex; align-items: center; gap: 6px; color: var(--color-text-light); }
.ui-wf__done { margin: 6px 0 0; color: var(--color-text-light); }
.ui-wf__failures { margin: 6px 0 0; padding-left: 18px; color: var(--color-danger); }
.ui-wf__error { margin: 6px 0 0; color: var(--color-danger); }
.btn { padding: 4px 10px; border-radius: 4px; border: 1px solid var(--color-border); background: transparent; color: var(--color-text); cursor: pointer; font-size: 11px; }
.btn--primary { background: var(--color-accent); border-color: var(--color-accent); color: #fff; }
.spinner { width: 10px; height: 10px; border: 2px solid var(--color-border); border-top-color: var(--color-accent); border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
