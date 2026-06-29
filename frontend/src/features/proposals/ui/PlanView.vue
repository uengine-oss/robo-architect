<template>
  <div class="plan-view">
    <div class="plan-header">
      <h4 class="plan-header__title">{{ t('proposals.plan.headerTitle') }} <span class="badge badge--orange">{{ t('proposals.plan.headerBadge') }}</span></h4>
      <div class="plan-header__actions">
        <button v-if="!stream.active" @click="run" class="btn btn--primary">
          {{ hasPlan ? t('proposals.plan.btnRegenerate') : t('proposals.plan.btnGenerate') }}
        </button>
        <button v-else @click="store.stopPlan()" class="btn btn--secondary">{{ t('proposals.common.stop') }}</button>
      </div>
    </div>

    <!-- Constitution 미설정 게이트 — Design 측 표준 헌장 다이얼로그(ConstitutionEditor)를
         앱 이벤트로 열어 인터뷰를 진행한다. 별도 인터뷰 UI 를 중복 구현하지 않는다. (FR-010 / 041 revised) -->
    <div v-if="stream.constitutionRequired" class="plan-callout plan-callout--block">
      <div class="plan-callout__head">
        📜 <strong>{{ t('proposals.plan.cstModalTitle') }}</strong>
        <p v-html="t('proposals.plan.cstModalIntro')"></p>
      </div>
      <div>
        <button class="btn btn--primary" @click="openConstitutionDialog">{{ t('proposals.constitution.startInterview') }}</button>
      </div>
    </div>

    <div v-if="stream.active && !stream.tactical" class="plan-waiting">
      {{ t('proposals.plan.waitingTactical') }}
    </div>

    <!-- 진행 로그 (Intent 단계와 동일한 실시간 narration) -->
    <div v-if="stream.active || stream.logLines?.length" class="stream-log">
      <div
        v-for="(line, i) in stream.logLines"
        :key="i"
        :class="['stream-log__line', logLineClass(line)]"
      >{{ line }}</div>
      <div v-if="stream.active && !stream.logLines?.length" class="stream-log__waiting">
        {{ t('proposals.plan.waitingAnalysis') }}
      </div>
    </div>

    <!-- 아키텍처 결정 (US3) -->
    <section v-if="architecture.length" class="plan-section">
      <h5 class="plan-section__title">{{ t('proposals.plan.sectionArchitecture') }}</h5>
      <div v-for="(dec, i) in architecture" :key="dec.aspect || i" class="arch-card">
        <div class="arch-card__head">
          <span class="arch-aspect">{{ aspectLabel(dec.aspect) }}</span>
          <span v-if="isMonolithNA(dec)" class="badge badge--neutral">{{ t('proposals.plan.naMonolith') }}</span>
          <span v-if="dec.constitutionRef" class="arch-ref" :title="t('proposals.plan.constitutionRefTooltip')">↳ {{ dec.constitutionRef }}</span>
          <span v-else class="badge badge--amber" :title="t('proposals.plan.constitutionGapTooltip')">{{ t('proposals.plan.constitutionGap') }}</span>
        </div>
        <div class="arch-card__decision">{{ dec.decision || (isMonolithNA(dec) ? t('proposals.plan.monolithNA') : '—') }}</div>
        <div v-if="dec.rationale" class="arch-card__rationale">{{ dec.rationale }}</div>
      </div>
    </section>

    <!-- Constitution 공백 콜아웃 (FR-013 / SC-003) -->
    <div v-if="constitutionGaps.length" class="plan-callout plan-callout--gap">
      <strong>{{ t('proposals.plan.constitutionGap') }}</strong>
      <p>{{ t('proposals.plan.constitutionGapBody') }}</p>
      <ul class="gap-list">
        <li v-for="(g, i) in constitutionGaps" :key="i">{{ aspectLabel(g) }}</li>
      </ul>
    </div>

    <!-- 041 — 컨텍스트 간 연동 (다수 BC / 마이크로서비스) -->
    <section v-if="integrations.length || messagingChannel" class="plan-section">
      <h5 class="plan-section__title">{{ t('proposals.plan.sectionIntegration') }}</h5>
      <div v-if="messagingChannel" class="plan-channel">
        {{ t('proposals.plan.messagingChannel') }}: <strong>{{ messagingChannel }}</strong>
        <span class="plan-channel__hint">(이벤트 드리븐 pub/sub 기본)</span>
      </div>
      <div v-for="(ic, i) in integrations" :key="i" class="integ-card">
        <span class="integ-flow">{{ ic.fromContext }} → {{ ic.toContext }}</span>
        <span :class="['integ-kind', `integ-kind--${(ic.kind||'EVENT').toLowerCase()}`]">{{ kindLabel(ic.kind) }}</span>
        <span class="integ-msg">{{ ic.message }}</span>
        <span v-if="ic.sync" class="badge badge--amber">{{ t('proposals.plan.syncLabel') }}</span>
        <span v-else class="badge badge--neutral">{{ t('proposals.plan.asyncLabel') }}</span>
        <div v-if="ic.rationale" class="integ-rationale">{{ ic.rationale }}</div>
      </div>
    </section>

    <!-- 041 — 서비스별 개발 환경 (멀티레포 대비, 범위 제한) -->
    <section v-if="devEnvs.length" class="plan-section">
      <h5 class="plan-section__title">{{ t('proposals.plan.sectionDevEnv') }}</h5>
      <div v-for="(de, i) in devEnvs" :key="i" class="dev-card">
        <div class="dev-card__head">
          <span class="dev-service">{{ de.service }}</span>
          <span v-if="de.runtime" class="dev-runtime">{{ de.runtime }}</span>
          <span v-if="de.dockerBaseImage" class="badge badge--neutral mono">{{ de.dockerBaseImage }}</span>
        </div>
        <div v-if="(de.dependencies||[]).length" class="dev-deps">
          {{ t('proposals.plan.dependsLabel') }}: <span v-for="(d, di) in de.dependencies" :key="di" class="dev-dep">{{ d }}</span>
        </div>
        <div v-if="de.scopeNote" class="dev-scope">↳ {{ de.scopeNote }}</div>
      </div>
    </section>

    <!-- Tactical Diff -->
    <section v-if="tactical && tactical.length" class="plan-section">
      <h5 class="plan-section__title">{{ t('proposals.term.tacticalDesign') }}</h5>
      <div v-for="(item, i) in tactical" :key="item.nodeId || item.entityTitle || item.nodeTitle || i" class="diff-entry">
        <div class="diff-entry__header">
          <span :class="opClass(item.changeType || item.op)">{{ item.changeType || item.op }}</span>
          <span class="diff-entry__label">{{ item.nodeLabel || item.entityType }}</span>
          <span class="diff-entry__title">{{ item.nodeTitle || item.entityTitle }}</span>
          <span v-if="item.impactLevel" :class="['impact-badge', `impact-badge--${(item.impactLevel || 'LOW').toLowerCase()}`]">{{ item.impactLevel }}</span>
          <OpenInViewerLink
            v-if="proposalId && canOpenCandidate(item)"
            :proposalId="proposalId"
            :nodeId="item.nodeId"
            :nodeLabel="item.nodeLabel || item.entityType"
            :nodeTitle="item.nodeTitle || item.entityTitle"
          />
        </div>
      </div>
    </section>

    <!-- 임팩트 분석 -->
    <section v-if="impactItems.length" class="plan-section">
      <h5 class="plan-section__title">{{ t('proposals.plan.sectionImpact') }}</h5>
      <ImpactMapView :impactMap="impactItems" :proposalId="proposalId" />
    </section>

    <!-- 전술 요약 -->
    <div v-if="tacticalSummary" class="plan-summary">{{ tacticalSummary }}</div>

    <!-- 확정 -->
    <div class="plan-actions" v-if="stream.done || hasPlan">
      <button @click="confirm" :disabled="confirming || !canConfirm" class="btn btn--primary">
        {{ confirming ? t('proposals.plan.confirming') : t('proposals.plan.btnConfirm') }}
      </button>
      <span v-if="confirmed" class="plan-confirmed">{{ t('proposals.plan.confirmedMsg') }}</span>
    </div>

    <p v-if="stream.error" class="error-msg">{{ stream.error }}</p>
    <p v-if="confirmError" class="error-msg">{{ confirmError }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from '../../../app/i18n'
import { useProposalsStore } from '../proposals.store'
import OpenInViewerLink from './OpenInViewerLink.vue'
import ImpactMapView from './ImpactMapView.vue'

const { t } = useI18n()

const props = defineProps({
  proposalId: { type: String, required: true },
  // Constitution 의 architectureStyle — 'MONOLITH' 면 ingress/mesh 결정을 N/A 로 표기.
  architectureStyle: { type: String, default: null },
})
const emit = defineEmits(['need-constitution', 'confirmed'])

const store = useProposalsStore()
const confirming = ref(false)
const confirmed = ref(false)
const confirmError = ref('')

const stream = computed(() => store.planStream)
const plan = computed(() => store.plan)

// 다섯 가지 필수 아키텍처 영역 라벨.
const ASPECT_KEYS = {
  DEPLOYMENT_ENV: 'proposals.plan.aspectDeploymentEnv',
  INGRESS: 'proposals.plan.aspectIngress',
  SERVICE_MESH_FRAMEWORK: 'proposals.plan.aspectServiceMeshFramework',
  FRONTEND: 'proposals.plan.aspectFrontend',
  REPO_MAPPING: 'proposals.plan.aspectRepoMapping',
}
// 모놀리식이면 N/A 로 표기할 영역.
const MONOLITH_NA_ASPECTS = ['INGRESS', 'SERVICE_MESH_FRAMEWORK']

function aspectLabel(a) { return ASPECT_KEYS[a] ? t(ASPECT_KEYS[a]) : a }
function isMonolithNA(dec) {
  return props.architectureStyle === 'MONOLITH'
    && MONOLITH_NA_ASPECTS.includes(dec.aspect)
    && (!dec.decision || /n\/?a|monolith|해당\s*없음/i.test(dec.decision))
}

// 스트림 우선, 없으면 저장된 plan.
const architecture = computed(() =>
  stream.value.architecture?.length ? stream.value.architecture : (plan.value?.architectureDecisions || []))
const constitutionGaps = computed(() =>
  stream.value.constitutionGaps?.length ? stream.value.constitutionGaps : (plan.value?.constitutionGaps || []))
const tactical = computed(() =>
  stream.value.tactical || store.currentProposal?.tacticalDiff || store.currentProposal?.planDraft?.tacticalDiff || [])
const impactItems = computed(() => {
  const src = stream.value.impact ?? store.currentProposal?.impactMap ?? store.currentProposal?.planDraft?.impactMap
  return Array.isArray(src) ? src : (src?.items || [])
})
const tacticalSummary = computed(() => plan.value?.tacticalSummary || '')
// 041 — 컨텍스트 간 연동 / 메시징 채널 / 서비스별 개발환경 (마이크로서비스 다수 BC).
const integrations = computed(() => plan.value?.interContextIntegrations || [])
const messagingChannel = computed(() => plan.value?.messagingChannel || '')
const devEnvs = computed(() => plan.value?.serviceDevEnvironments || [])
const KIND_KEYS = { EVENT: 'proposals.plan.kindEvent', COMMAND: 'proposals.plan.kindCommand', QUERY: 'proposals.plan.kindQuery' }
function kindLabel(k) { return KIND_KEYS[k] ? t(KIND_KEYS[k]) : (k || t('proposals.plan.kindEvent')) }
function canOpenCandidate(item) {
  return !!(item?.nodeId || item?.nodeTitle || item?.entityTitle)
}
const hasPlan = computed(() => !!plan.value && (architecture.value.length || (tactical.value && tactical.value.length)))
const canConfirm = computed(() => architecture.value.length > 0 || (tactical.value && tactical.value.length > 0))

onMounted(() => {
  store.getPlan(props.proposalId)
  window.addEventListener('robo:constitution-saved', _onConstitutionSaved)
})
onBeforeUnmount(() => window.removeEventListener('robo:constitution-saved', _onConstitutionSaved))

async function run() {
  confirmed.value = false
  confirmError.value = ''
  try {
    await store.runPlan(props.proposalId)
  } catch (e) {
    if (e?.reason === 'constitution_required') {
      // store 가 stream.constitutionRequired 를 세팅 → 게이트 콜아웃 노출.
      // 표준 헌장 다이얼로그(Design 측)를 곧장 인터뷰 모드로 연다.
      emit('need-constitution')
      openConstitutionDialog()
    }
  }
}

// Design 측 표준 헌장 다이얼로그를 인터뷰 모드로 연다(App.vue 가 모달을 띄운다).
// proposalId 를 함께 넘겨 Claude Code 가 이 제안을 먼저 분석하도록 한다.
function openConstitutionDialog() {
  window.dispatchEvent(new CustomEvent('robo:open-constitution', {
    detail: { scope: 'PROJECT', interview: true, proposalId: props.proposalId },
  }))
}

// 헌장이 저장/생성되면(robo:constitution-saved) 게이트를 풀고 Plan 을 자동 재시도한다.
async function _onConstitutionSaved() {
  if (!stream.value.constitutionRequired) return
  stream.value.constitutionRequired = false
  await store.getConstitution(props.proposalId)
  await run()
}

async function confirm() {
  confirmError.value = ''
  confirming.value = true
  try {
    await store.confirmPlan(props.proposalId)
    confirmed.value = true
    emit('confirmed')
  } catch (e) {
    confirmError.value = e.message
  } finally {
    confirming.value = false
  }
}

function opClass(op) {
  const map = { CREATE: 'op-badge op-badge--create', MODIFY: 'op-badge op-badge--modify', DELETE: 'op-badge op-badge--delete' }
  return map[op] || 'op-badge'
}

// 진행 로그 라인 강조 — Intent 단계(ProposalDetail)와 동일 규칙.
function logLineClass(line) {
  if (line.startsWith('[tool]')) return 'stream-log__line--tool'
  if (/^\[.+\]/.test(line)) return 'stream-log__line--tag'
  if (line.startsWith('{') || line.startsWith('"') || line === '}' || line === ']') return 'stream-log__line--json'
  return ''
}
</script>

<style scoped>
.plan-view { font-size: 13px; }
.plan-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.plan-header__title { font-size: 14px; font-weight: 600; margin: 0; display: flex; align-items: center; gap: 6px; color: var(--color-text-bright); }
.plan-header__actions { display: flex; gap: 6px; }
.plan-waiting { color: var(--color-text-light); font-style: italic; padding: 8px 0; }
.stream-log { margin: 4px 0 16px; background: #0f172a; border-radius: 6px; padding: 10px 12px; max-height: 240px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #cbd5e1; }
.stream-log__line { padding: 1px 0; white-space: pre-wrap; word-break: break-all; line-height: 1.5; }
.stream-log__line--tag { color: #86efac; font-weight: 600; }
.stream-log__line--tool { color: #7dd3fc; }
.stream-log__line--json { color: #64748b; font-size: 10px; }
.stream-log__waiting { color: #64748b; }
.plan-section { margin-bottom: 18px; }
.plan-section__title { font-size: 12px; font-weight: 600; color: var(--color-text-light); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }
.arch-card { border: 1px solid var(--color-border); border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; background: var(--color-bg-secondary); }
.arch-card__head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.arch-aspect { font-weight: 600; color: var(--color-text-bright); }
.arch-ref { font-size: 11px; color: var(--color-text-light); }
.arch-card__decision { margin-top: 4px; color: var(--color-text); }
.arch-card__rationale { margin-top: 4px; font-size: 12px; color: var(--color-text-light); }
.plan-callout { border: 1px solid var(--color-border); border-radius: 6px; padding: 10px 12px; margin-bottom: 16px; font-size: 13px; }
.plan-callout--gap { background: var(--status-amber-bg); color: var(--status-amber-fg); border-color: transparent; }
.plan-callout--gap p { margin: 4px 0; }
.plan-callout--block { background: var(--status-blue-bg); color: var(--status-blue-fg); border-color: transparent; display: flex; flex-direction: column; gap: 10px; }
.plan-callout__head { line-height: 1.5; }
.plan-callout__interview { background: var(--color-bg); color: var(--color-text); border: 1px solid var(--color-border); border-radius: 6px; padding: 12px; }
.gap-list { margin: 4px 0 0 16px; padding: 0; }
.diff-entry { background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; }
.diff-entry__header { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.diff-entry__label { font-size: 11px; color: var(--color-text-light); background: var(--color-bg-tertiary); padding: 1px 5px; border-radius: 3px; }
.diff-entry__title { font-weight: 500; color: var(--color-text); }
.op-badge { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; text-transform: uppercase; }
.op-badge--create { background: var(--status-green-bg); color: var(--status-green-fg); }
.op-badge--modify { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.op-badge--delete { background: var(--status-red-bg); color: var(--status-red-fg); }
.impact-badge { font-size: 10px; font-weight: 600; padding: 1px 5px; border-radius: 3px; margin-left: auto; }
.impact-badge--high { background: var(--status-red-bg); color: var(--status-red-fg); }
.impact-badge--medium { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.impact-badge--low { background: var(--status-green-bg); color: var(--status-green-fg); }
.impact-badge--none { background: var(--status-neutral-bg); color: var(--status-neutral-fg); }
.plan-summary { margin: 8px 0 16px; padding: 10px 12px; border-left: 3px solid var(--color-accent); background: var(--color-bg-secondary); color: var(--color-text); font-size: 12px; line-height: 1.5; }
.plan-actions { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--color-border); display: flex; align-items: center; gap: 10px; }
.plan-confirmed { color: var(--color-success); font-size: 12px; font-weight: 600; }
.plan-channel { margin-bottom: 8px; color: var(--color-text); }
.plan-channel__hint { font-size: 11px; color: var(--color-text-light); margin-left: 4px; }
.integ-card { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; background: var(--color-bg-secondary); }
.integ-flow { font-weight: 600; color: var(--color-text-bright); }
.integ-kind { font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 3px; text-transform: uppercase; }
.integ-kind--event { background: var(--status-green-bg); color: var(--status-green-fg); }
.integ-kind--command { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.integ-kind--query { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.integ-msg { font-family: monospace; font-size: 12px; color: var(--color-text); }
.integ-rationale { flex-basis: 100%; font-size: 12px; color: var(--color-text-light); }
.dev-card { border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; background: var(--color-bg-secondary); }
.dev-card__head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dev-service { font-weight: 600; color: var(--color-text-bright); }
.dev-runtime { font-size: 12px; color: var(--color-text-light); }
.dev-deps { margin-top: 4px; font-size: 12px; color: var(--color-text); }
.dev-dep { display: inline-block; background: var(--color-bg-tertiary); border-radius: 3px; padding: 1px 6px; margin-right: 4px; font-family: monospace; font-size: 11px; }
.dev-scope { margin-top: 4px; font-size: 12px; color: var(--color-text-light); }
.mono { font-family: monospace; }
.badge { font-size: 11px; padding: 2px 6px; border-radius: 9999px; }
.badge--blue { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.badge--orange { background: var(--status-orange-bg); color: var(--status-orange-fg); }
.badge--amber { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.badge--neutral { background: var(--status-neutral-bg); color: var(--status-neutral-fg); }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--sm { padding: 4px 10px; font-size: 12px; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--primary:disabled { opacity: 0.5; cursor: default; }
.btn--secondary { background: var(--color-bg-tertiary); color: var(--color-text); }
.error-msg { color: var(--color-danger); font-size: 12px; margin-top: 6px; }
</style>
