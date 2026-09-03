<template>
  <section class="psb" data-test-id="proposal-storyboard">
    <div class="psb__head">
      <div class="psb__title-wrap">
        <span class="psb__icon">🎬</span>
        <div>
          <div class="psb__title">{{ t('proposals.storyboard.title') }}</div>
          <div class="psb__subtitle">{{ t('proposals.storyboard.subtitle') }}</div>
        </div>
      </div>
      <div class="psb__actions">
        <span v-if="isRunning" class="psb__progress" data-test-id="storyboard-progress">
          <span class="psb__spinner" />
          {{ t('proposals.storyboard.generating') }}
          <b>{{ t('proposals.storyboard.progress', { done: sb?.done ?? 0, total: sb?.total ?? 0 }) }}</b>
        </span>
        <button
          class="btn btn--secondary btn--sm"
          :disabled="isRunning || !canGenerate"
          data-test-id="storyboard-generate"
          @click="generate(true)"
        >{{ hasFrames ? t('proposals.storyboard.regenerate') : t('proposals.storyboard.generate') }}</button>
      </div>
    </div>

    <div v-if="!canGenerate && !hasFrames" class="psb__empty">
      {{ intentPending ? t('proposals.storyboard.waitingIntent') : t('proposals.storyboard.empty') }}
    </div>

    <div v-for="j in journeys" :key="j.id" class="psb__journey" :data-test-id="`storyboard-journey-${j.id}`">
      <div class="psb__journey-head">
        <span class="psb__journey-name">🧭 {{ j.name }}</span>
        <span v-if="j.description" class="psb__journey-desc">{{ j.description }}</span>
      </div>
      <div class="psb__flow">
        <template v-for="(st, si) in j.steps" :key="st.id">
          <div v-if="si > 0" class="psb__arrow" aria-hidden="true">
            <svg width="28" height="16" viewBox="0 0 28 16"><path d="M0 8h22M18 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
          </div>
          <div
            v-if="st.kind === 'gateway'"
            class="psb__gateway"
            :title="st.description"
            data-test-id="storyboard-gateway"
          >◇ {{ st.name }}<span class="psb__gateway-tag">{{ t('proposals.storyboard.gateway') }}</span></div>
          <div
            v-else
            class="psb__card"
            :class="{ 'psb__card--failed': st.status === 'failed', 'psb__card--pending': st.status === 'pending' }"
            :data-test-id="`storyboard-step-${st.id}`"
            :data-status="st.status"
          >
            <div class="psb__card-head">
              <span class="psb__step-no">{{ screenIndex(j, si) }}</span>
              <span class="psb__step-name" :title="st.name">{{ st.name }}</span>
              <button
                v-if="st.status === 'done' && st.sceneGraph"
                class="psb__edit"
                :title="t('proposals.storyboard.edit')"
                data-test-id="storyboard-edit"
                @click="openEditor(st)"
              >✎</button>
            </div>
            <div class="psb__frame">
              <FramePreview
                v-if="st.status === 'done' && st.sceneGraph && st.frameId"
                :scene-data="st.sceneGraph"
                :frame-id="st.frameId"
                :width="FRAME_W"
                :height="FRAME_H"
              />
              <div v-else-if="st.status === 'failed'" class="psb__frame-state psb__frame-state--failed">
                {{ t('proposals.storyboard.failed') }}<small v-if="st.error">{{ st.error }}</small>
              </div>
              <div v-else class="psb__frame-state">
                <span class="psb__spinner" />{{ t('proposals.storyboard.pending') }}
              </div>
            </div>
            <div v-if="st.summary" class="psb__summary" :title="st.summary">{{ st.summary }}</div>
          </div>
        </template>
      </div>
    </div>

    <!-- 편집 모달: open-pencil FrameEditor -->
    <div v-if="editing" class="psb__overlay" @click.self="closeEditor">
      <div class="psb__modal" data-test-id="storyboard-editor">
        <div class="psb__modal-head">
          <span>{{ t('proposals.storyboard.editTitle', { name: editing.name }) }}</span>
          <span v-if="savedFlash" class="psb__saved">{{ t('proposals.storyboard.saved') }}</span>
          <button class="btn btn--secondary btn--sm" @click="closeEditor">{{ t('proposals.storyboard.close') }}</button>
        </div>
        <div class="psb__modal-body">
          <FrameEditor
            :key="editing.id"
            :scene-data="editing.sceneGraph"
            :frame-id="editing.frameId"
            :on-save="saveEdited"
          />
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from '../../../app/i18n'
import { useProposalsStore } from '../proposals.store'

// open-pencil federation (source-level alias, see vite.config.js)
const FramePreview = defineAsyncComponent(() => import('open-pencil-fed/FramePreview.vue'))
const FrameEditor = defineAsyncComponent(() => import('open-pencil-fed/FrameEditor.vue'))

const FRAME_W = 220
const FRAME_H = 400

const props = defineProps({
  proposalId: { type: String, required: true },
  /** 스토리보드 자동 생성 조건 판단용 — Intent 결과 유무 */
  hasIntent: { type: Boolean, default: false },
  intentPending: { type: Boolean, default: false },
})

const { t } = useI18n()
const store = useProposalsStore()

const sb = ref(null)
const editing = ref(null)
const savedFlash = ref(false)
let pollTimer = null
let autoRequested = false

const isRunning = computed(() => !!sb.value && (sb.value.running || sb.value.status === 'running'))
const journeys = computed(() => sb.value?.journeys || [])
const hasFrames = computed(() => journeys.value.some(j => (j.steps || []).some(s => s.status === 'done')))
const canGenerate = computed(() => props.hasIntent)

function screenIndex(j, si) {
  let n = 0
  for (let i = 0; i <= si; i++) if (j.steps[i].kind !== 'gateway') n++
  return n
}

async function load() {
  try {
    sb.value = await store.fetchStoryboard(props.proposalId, { scenes: true })
  } catch (e) {
    console.warn('[storyboard] load failed', e)
  }
  schedulePoll()
  maybeAutoGenerate()
}

function schedulePoll() {
  clearTimeout(pollTimer)
  if (isRunning.value) pollTimer = setTimeout(load, 2500)
}

async function maybeAutoGenerate() {
  // 초안(Intent 결과)이 있는데 스토리보드가 아직 없으면 한 번 자동으로 생성한다.
  if (autoRequested || !canGenerate.value || isRunning.value) return
  const status = sb.value?.status
  if (!status || status === 'none') {
    autoRequested = true
    await generate(false)
  }
}

async function generate(force) {
  try {
    await store.generateStoryboard(props.proposalId, { force })
    sb.value = { ...(sb.value || {}), status: 'running', running: true, done: 0, total: sb.value?.total ?? 0, journeys: force ? [] : journeys.value }
    schedulePoll()
  } catch (e) {
    console.warn('[storyboard] generate failed', e)
  }
}

function openEditor(st) {
  editing.value = st
  savedFlash.value = false
}
function closeEditor() { editing.value = null }

async function saveEdited(data) {
  if (!editing.value) return
  try {
    await store.updateStoryboardStep(props.proposalId, editing.value.id, data)
    editing.value.sceneGraph = data
    savedFlash.value = true
    setTimeout(() => { savedFlash.value = false }, 1500)
    await load()
  } catch (e) {
    console.warn('[storyboard] save failed', e)
  }
}

onMounted(load)
onBeforeUnmount(() => clearTimeout(pollTimer))
watch(() => props.proposalId, () => { autoRequested = false; sb.value = null; load() })
watch(() => props.hasIntent, (v) => { if (v) maybeAutoGenerate() })
// Intent 재생성이 끝나면 백엔드가 storyboard 를 새로 만든다 → 폴링 재개
watch(() => store.intentStream?.active, (active, was) => { if (was && !active) setTimeout(load, 1500) })
</script>

<style scoped>
.psb { border: 1px solid color-mix(in srgb, #e8590c 35%, var(--color-border)); border-radius: 10px; background: var(--color-surface, #fff); margin-bottom: 14px; overflow: hidden; }
.psb__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; background: color-mix(in srgb, #e8590c 8%, var(--color-surface, #fff)); border-bottom: 1px solid var(--color-border); }
.psb__title-wrap { display: flex; align-items: center; gap: 10px; }
.psb__icon { font-size: 1.2rem; }
.psb__title { font-size: 0.82rem; font-weight: 700; color: var(--color-text); }
.psb__subtitle { font-size: 0.68rem; color: var(--color-text-light); }
.psb__actions { display: flex; align-items: center; gap: 10px; }
.psb__progress { display: inline-flex; align-items: center; gap: 6px; font-size: 0.7rem; color: #c2410c; }
.psb__spinner { width: 12px; height: 12px; border: 2px solid color-mix(in srgb, #e8590c 30%, transparent); border-top-color: #e8590c; border-radius: 50%; animation: psb-spin 0.8s linear infinite; display: inline-block; }
@keyframes psb-spin { to { transform: rotate(360deg); } }
.psb__empty { padding: 18px; font-size: 0.74rem; color: var(--color-text-light); text-align: center; }
.psb__journey { padding: 10px 12px; border-bottom: 1px solid var(--color-border); }
.psb__journey:last-of-type { border-bottom: none; }
.psb__journey-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
.psb__journey-name { font-size: 0.76rem; font-weight: 600; color: var(--color-text); }
.psb__journey-desc { font-size: 0.68rem; color: var(--color-text-light); }
.psb__flow { display: flex; align-items: center; gap: 6px; overflow-x: auto; padding: 4px 2px 8px; }
.psb__arrow { color: var(--color-text-light); flex-shrink: 0; display: flex; }
.psb__card { flex-shrink: 0; width: 236px; border: 1px solid var(--color-border); border-radius: 10px; background: var(--color-bg, #fafafa); box-shadow: 0 1px 2px rgba(0,0,0,.06); }
.psb__card--failed { border-color: #f03e3e; }
.psb__card--pending { opacity: .85; }
.psb__card-head { display: flex; align-items: center; gap: 6px; padding: 6px 8px; border-bottom: 1px solid var(--color-border); }
.psb__step-no { width: 18px; height: 18px; border-radius: 50%; background: #e8590c; color: #fff; font-size: 0.66rem; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.psb__step-name { flex: 1; font-size: 0.72rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--color-text); }
.psb__edit { border: none; background: transparent; cursor: pointer; font-size: 0.8rem; color: var(--color-text-light); }
.psb__edit:hover { color: #e8590c; }
.psb__frame { padding: 8px; display: flex; justify-content: center; }
.psb__frame-state { width: 220px; height: 400px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; font-size: 0.7rem; color: var(--color-text-light); background: repeating-linear-gradient(45deg, transparent 0 8px, rgba(0,0,0,.03) 8px 16px); border-radius: 6px; }
.psb__frame-state--failed { color: #c92a2a; }
.psb__frame-state small { font-size: 0.62rem; max-width: 200px; text-align: center; word-break: break-all; }
.psb__summary { font-size: 0.64rem; color: var(--color-text-light); padding: 0 8px 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.psb__gateway { flex-shrink: 0; padding: 6px 10px; border: 1px dashed #1098ad; border-radius: 8px; font-size: 0.7rem; color: #0b7285; background: color-mix(in srgb, #1098ad 6%, transparent); max-width: 160px; }
.psb__gateway-tag { margin-left: 6px; font-size: 0.6rem; opacity: .7; }
.psb__overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.psb__modal { width: min(1100px, 94vw); height: min(780px, 90vh); background: #1e1e1e; color: #e0e0e0; border-radius: 10px; display: flex; flex-direction: column; overflow: hidden; }
.psb__modal-head { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-bottom: 1px solid #333; font-size: 0.78rem; }
.psb__modal-head > span:first-child { flex: 1; }
.psb__saved { color: #51cf66; font-size: 0.7rem; }
.psb__modal-body { flex: 1; min-height: 0; }
</style>
