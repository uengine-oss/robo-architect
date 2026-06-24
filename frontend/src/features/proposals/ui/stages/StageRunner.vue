<template>
  <div class="stage-runner">
    <div class="stage-runner__head">
      <strong class="stage-runner__name">{{ stageLabel }}</strong>
      <!-- 카드 시각화 ↔ Markdown 보기 토글 -->
      <div v-if="artifact" class="stage-runner__seg">
        <button class="stage-runner__seg-btn" :class="{ 'is-on': viewPref.mode === 'card' }" @click="viewPref.mode = 'card'">카드</button>
        <button class="stage-runner__seg-btn" :class="{ 'is-on': viewPref.mode === 'markdown' }" @click="viewPref.mode = 'markdown'">Markdown</button>
      </div>
      <span v-if="store.stagedStream.active" class="muted"><span class="spinner spinner--sm" /> 실행 중…</span>
      <button v-else class="btn btn--ghost btn--xs" @click="run()" :disabled="busy">↻ 다시 실행</button>
    </div>

    <!-- 실행 중: 실시간 narration 로그를 펼쳐서 표시 -->
    <div v-if="store.stagedStream.active" class="stage-runner__live">
      <div class="stage-runner__live-head"><span class="spinner spinner--sm" /> {{ stageLabel }} 분석 중…</div>
      <pre ref="logEl" class="stage-runner__log">{{ logText || '대기 중…' }}</pre>
    </div>

    <!-- 실행 완료 후: 로그는 접이식으로 보관 -->
    <details v-else-if="logText" class="stage-runner__logwrap">
      <summary>분석 로그</summary>
      <pre class="stage-runner__log">{{ logText }}</pre>
    </details>

    <template v-if="artifact">
      <!-- 단계별 시각화(카드) 또는 Markdown 보기 -->
      <component v-if="viewPref.mode === 'card'" :is="vizComponent" v-model="artifact" />
      <StageMarkdownView v-else :stage="stage" :artifact="artifact" />

      <!-- 충돌 해소(전략 메모리, FR-019) -->
      <div v-if="conflicts.length" class="stage-runner__conflicts">
        <h5>{{ t('proposals.staged.conflictTitle') }}</h5>
        <div v-for="(c, i) in conflicts" :key="i" class="conflict">
          <div class="conflict__desc">
            <code>{{ c.field }}</code>{{ c.bcId ? ` @ ${c.bcId}` : '' }}:
            <b>{{ c.memoryValue }}</b> → <b>{{ c.proposalValue }}</b>
          </div>
          <div class="conflict__actions">
            <label><input type="radio" :name="`c${i}`" value="AMEND_MEMORY" v-model="c._res" /> {{ t('proposals.staged.amendMemory') }}</label>
            <label><input type="radio" :name="`c${i}`" value="JUSTIFY_LOCAL" v-model="c._res" /> {{ t('proposals.staged.justifyLocal') }}</label>
            <input v-if="c._res === 'JUSTIFY_LOCAL'" v-model="c._just" class="conflict__just" placeholder="사유" />
          </div>
        </div>
      </div>

      <!-- 피드백 → 재생성 -->
      <div class="stage-runner__feedback">
        <input v-model="feedbackText" class="stage-runner__fb-input" :placeholder="t('proposals.staged.feedbackPlaceholder')" @keyup.enter="regenerate" :disabled="busy" />
        <button class="btn btn--secondary btn--xs" :disabled="!feedbackText.trim() || busy" @click="regenerate">↻ 피드백 반영</button>
      </div>

      <!-- 고급: 원시 JSON 폴백 -->
      <details class="stage-runner__advanced">
        <summary>고급 (JSON 직접 편집)</summary>
        <textarea v-model="advancedJson" rows="8" class="stage-runner__json" spellcheck="false"></textarea>
        <button class="btn btn--ghost btn--xs" @click="applyJson">JSON 적용</button>
        <span v-if="jsonError" class="error-msg">{{ jsonError }}</span>
      </details>

      <div class="stage-runner__actions">
        <button class="btn btn--primary" :disabled="busy" @click="confirm">{{ t('proposals.staged.confirmStage') }}</button>
        <button class="btn btn--secondary" :disabled="busy || stage === 'DISCOVER'" @click="skip">{{ t('proposals.staged.skipStage') }}</button>
      </div>
    </template>

    <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useI18n } from '../../../../app/i18n'
import { useProposalsStore } from '../../proposals.store'
import DiscoverViz from './DiscoverViz.vue'
import DecomposeViz from './DecomposeViz.vue'
import StrategizeViz from './StrategizeViz.vue'
import ConnectViz from './ConnectViz.vue'
import DefineViz from './DefineViz.vue'
import TacticalViz from './TacticalViz.vue'
import StageMarkdownView from './StageMarkdownView.vue'
import { stageViewPref } from './stageMarkdown'

const props = defineProps({
  proposalId: { type: String, required: true },
  stage: { type: String, required: true },
  autorun: { type: Boolean, default: true },
})
const emit = defineEmits(['confirmed', 'skipped'])
const { t } = useI18n()
const store = useProposalsStore()

const VIZ = { DISCOVER: DiscoverViz, DECOMPOSE: DecomposeViz, STRATEGIZE: StrategizeViz, CONNECT: ConnectViz, DEFINE: DefineViz, TACTICAL: TacticalViz }
const LABELS = { DISCOVER: 'Discover — 이벤트 발굴', DECOMPOSE: 'Decompose — 서브도메인', STRATEGIZE: 'Strategize — Core/Supporting/Generic', CONNECT: 'Connect — 컨텍스트 연동', DEFINE: 'Define — Bounded Context', TACTICAL: 'Tactical — Aggregate 설계' }

const viewPref = stageViewPref
const vizComponent = computed(() => VIZ[props.stage])
const stageLabel = computed(() => LABELS[props.stage] || props.stage)
const logText = computed(() => (store.stagedStream.logLines || []).join('\n'))

const artifact = ref(null)
const conflicts = ref([])
const feedbackText = ref('')
const advancedJson = ref('')
const jsonError = ref('')
const errorMsg = ref('')
const busy = ref(false)
const logEl = ref(null)

// 실행 중 로그가 늘어나면 맨 아래로 자동 스크롤.
watch(() => store.stagedStream.logLines?.length, async () => {
  await nextTick()
  if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight
})

// 산출물 편집을 스토어 초안으로 보존(탭 전환·언마운트에도 유지).
watch(artifact, (v) => { if (v) store.setStageDraft(props.proposalId, props.stage, v) }, { deep: true })

onMounted(() => {
  // 1) 이미 생성된 초안이 있으면 스킬 재실행 없이 복원(탭 전환·검토 중 보존).
  const draft = store.getStageDraft(props.proposalId, props.stage)
  if (draft) {
    artifact.value = draft
    advancedJson.value = JSON.stringify(draft, null, 2)
    return
  }
  // 2) 초안은 없지만 동일 단계 실행이 진행 중이면, 재시작하지 말고 그 실행에 다시 붙는다.
  //    (subscribeToStage 가 in-flight 실행을 재사용하므로 run() 이 새로 시작하지 않는다.)
  if (props.autorun) run()
})

async function run(feedback = null) {
  artifact.value = null
  conflicts.value = []
  errorMsg.value = ''
  try {
    const res = await store.subscribeToStage(props.proposalId, props.stage, feedback)
    artifact.value = res.artifact || { stage: props.stage }
    advancedJson.value = JSON.stringify(artifact.value, null, 2)
    conflicts.value = (res.conflicts || []).map(c => ({ ...c, _res: 'AMEND_MEMORY', _just: '' }))
  } catch (e) { errorMsg.value = e.message }
}

function regenerate() {
  if (!feedbackText.value.trim()) return
  const fb = feedbackText.value.trim()
  feedbackText.value = ''
  run(fb)
}

function applyJson() {
  jsonError.value = ''
  try { artifact.value = JSON.parse(advancedJson.value) }
  catch { jsonError.value = 'JSON 형식 오류' }
}

async function confirm() {
  busy.value = true
  errorMsg.value = ''
  const resolutions = conflicts.value.map(c => ({ bcId: c.bcId, field: c.field, resolution: c._res, justification: c._just || null }))
  try {
    await store.confirmStage(props.proposalId, props.stage, artifact.value, resolutions)
    emit('confirmed', props.stage)
  } catch (e) {
    if (e.reason === 'unresolved_conflicts') {
      conflicts.value = (e.conflicts || []).map(c => ({ ...c, _res: 'AMEND_MEMORY', _just: '' }))
      errorMsg.value = t('proposals.staged.conflictTitle')
    } else { errorMsg.value = e.message }
  } finally { busy.value = false }
}

async function skip() {
  busy.value = true
  try { await store.skipStage(props.proposalId, props.stage); emit('skipped', props.stage) }
  catch (e) { errorMsg.value = e.message } finally { busy.value = false }
}
</script>

<style scoped>
.stage-runner { padding: 4px 0; }
.stage-runner__head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.stage-runner__name { font-size: 14px; color: var(--color-text-bright); }
.stage-runner__seg { display: inline-flex; border: 1px solid var(--color-border); border-radius: 5px; overflow: hidden; }
.stage-runner__seg-btn { padding: 2px 9px; font-size: 11px; background: transparent; color: var(--color-text-light); border: none; cursor: pointer; }
.stage-runner__seg-btn.is-on { background: var(--color-accent); color: #fff; }
.muted { color: var(--color-text-light); font-size: 12px; }
.stage-runner__logwrap summary { font-size: 11px; color: var(--color-text-light); cursor: pointer; }
.stage-runner__log { background: #0f172a; color: #cbd5e1; font-size: 11px; padding: 8px; border-radius: 6px; max-height: 220px; overflow-y: auto; white-space: pre-wrap; line-height: 1.5; }
.stage-runner__live { margin: 6px 0 4px; }
.stage-runner__live-head { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--color-text-light); margin-bottom: 6px; }
.stage-runner__conflicts { margin-top: 10px; border: 1px solid var(--color-danger); border-radius: 6px; padding: 8px; }
.stage-runner__conflicts h5 { margin: 0 0 6px; font-size: 13px; color: var(--color-danger); }
.conflict { font-size: 12px; padding: 4px 0; }
.conflict__actions { display: flex; align-items: center; gap: 12px; margin-top: 3px; }
.conflict__just { flex: 1; font-size: 12px; padding: 2px 6px; border: 1px solid var(--color-border); border-radius: 4px; }
.stage-runner__feedback { display: flex; gap: 6px; margin-top: 10px; }
.stage-runner__fb-input { flex: 1; font-size: 12px; padding: 5px 8px; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-bg-secondary); color: var(--color-text); }
.stage-runner__advanced { margin-top: 8px; }
.stage-runner__advanced summary { font-size: 11px; color: var(--color-text-light); cursor: pointer; }
.stage-runner__json { width: 100%; box-sizing: border-box; font-family: monospace; font-size: 11px; background: var(--color-bg-secondary); color: var(--color-text); border: 1px solid var(--color-border); border-radius: 6px; padding: 8px; }
.stage-runner__actions { margin-top: 12px; display: flex; gap: 8px; }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--xs { padding: 3px 8px; font-size: 11px; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--primary:disabled { opacity: 0.5; cursor: default; }
.btn--secondary { background: var(--color-bg-tertiary); color: var(--color-text); }
.btn--ghost { background: transparent; border: 1px solid var(--color-border); color: var(--color-text); }
.spinner { width: 14px; height: 14px; border: 2px solid var(--color-border); border-top-color: var(--color-accent); border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block; }
.spinner--sm { width: 10px; height: 10px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
