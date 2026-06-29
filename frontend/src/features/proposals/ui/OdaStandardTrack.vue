<template>
  <div class="oda-track">
    <h4 class="oda-track__title">{{ t('proposals.oda.title') }}</h4>

    <!-- 1) 표준 정합성 분해(intent) -->
    <section class="oda-sec">
      <div class="oda-sec__head">
        <span class="oda-sec__name">1. {{ t('proposals.oda.alignmentTitle') }}</span>
        <button class="btn btn--primary btn--sm" :disabled="running" @click="run('intent')">
          {{ running && phase === 'intent' ? t('proposals.oda.running') : t('proposals.oda.runIntent') }}
        </button>
      </div>
      <div v-if="alignment" class="oda-align">
        <div class="oda-align__row"><b>{{ t('proposals.oda.useCases') }}:</b>
          <span v-for="(u, i) in alignment.useCases || []" :key="'uc' + i" class="chip">{{ u.id }}</span>
          <span v-if="!alignment.useCases?.length" class="muted">—</span>
        </div>
        <div class="oda-align__row"><b>{{ t('proposals.oda.sidEntities') }}:</b>
          <span v-for="(s, i) in alignment.sidEntities || []" :key="'sid' + i" class="chip">{{ s.name }}</span>
          <span v-if="!alignment.sidEntities?.length" class="muted">—</span>
        </div>
        <div class="oda-align__row"><b>{{ t('proposals.oda.tmfApis') }}:</b>
          <span v-for="(a, i) in alignment.tmfApis || []" :key="'tmf' + i" class="chip">{{ a.id }} {{ a.version }}</span>
          <span v-if="!alignment.tmfApis?.length" class="muted">—</span>
        </div>
        <div class="oda-align__row"><b>{{ t('proposals.oda.componentBlock') }}:</b>
          <span class="chip chip--block">{{ alignment.componentBlock || '—' }}</span>
        </div>
      </div>
    </section>

    <!-- 2) 적합성 게이트 -->
    <section class="oda-sec">
      <div class="oda-sec__head">
        <span class="oda-sec__name">2. {{ t('proposals.oda.conformanceTitle') }}</span>
        <span :class="['gate-badge', 'gate-badge--' + gateResult.toLowerCase()]">{{ gateLabel }}</span>
      </div>

      <div v-if="conformance">
        <div class="oda-sub">{{ t('proposals.oda.classification') }}</div>
        <table class="oda-tbl" v-if="conformance.items?.length">
          <tbody>
            <tr v-for="(it, i) in conformance.items" :key="'it' + i">
              <td>{{ it.element }}</td>
              <td><span :class="['cls', 'cls--' + (it.classification || '').toLowerCase()]">{{ it.classification }}</span></td>
              <td class="muted">{{ it.mechanism || '' }}</td>
            </tr>
          </tbody>
        </table>

        <div v-if="conformance.violations?.length" class="oda-violations">
          <div class="oda-sub oda-sub--danger">{{ t('proposals.oda.violations') }}</div>
          <ul>
            <li v-for="(v, i) in conformance.violations" :key="'v' + i">
              <b>{{ v.element || v.rule }}</b> — {{ v.detail || v.rule }}
            </li>
          </ul>
        </div>

        <!-- FAIL → 면제 -->
        <div v-if="gateResult === 'FAIL'" class="oda-waive">
          <input v-model="waiveReason" :placeholder="t('proposals.oda.waiveReason')" class="oda-waive__input" />
          <button class="btn btn--danger btn--sm" :disabled="!waiveReason.trim() || waiving" @click="doWaive">
            {{ t('proposals.oda.waiveConfirm') }}
          </button>
        </div>
      </div>
      <p v-else class="muted">{{ t('proposals.oda.gatePending') }}</p>
    </section>

    <!-- 3) 표준 설계(plan) -->
    <section class="oda-sec">
      <div class="oda-sec__head">
        <span class="oda-sec__name">3. {{ t('proposals.oda.artifactsTitle') }}</span>
        <button class="btn btn--primary btn--sm" :disabled="running || !canProceed" @click="run('plan')"
          :title="canProceed ? '' : t('proposals.oda.gateFail')">
          {{ running && phase === 'plan' ? t('proposals.oda.running') : t('proposals.oda.runPlan') }}
        </button>
      </div>
      <div v-if="artifacts" class="oda-artifacts">
        <span class="chip" :class="{ 'chip--off': !artifacts.dataModel }">{{ t('proposals.oda.dataModel') }}</span>
        <span class="chip" :class="{ 'chip--off': !artifacts.contracts?.length }">{{ t('proposals.oda.contracts') }} ({{ artifacts.contracts?.length || 0 }})</span>
        <span class="chip" :class="{ 'chip--off': !artifacts.architecture }">{{ t('proposals.oda.architecture') }}</span>
        <span class="chip" :class="{ 'chip--off': !artifacts.featureFiles?.length }">{{ t('proposals.oda.featureFiles') }} ({{ artifacts.featureFiles?.length || 0 }})</span>
      </div>
    </section>

    <!-- 진행 로그 -->
    <div v-if="running || store.odaStream.logLines?.length" class="stream-log">
      <div v-for="(line, i) in store.odaStream.logLines" :key="i" class="stream-log__line">{{ line }}</div>
      <div v-if="running && !store.odaStream.logLines?.length" class="stream-log__waiting">…</div>
    </div>
    <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from '../../../app/i18n'
import { useProposalsStore } from '../proposals.store'

const props = defineProps({ proposalId: { type: String, required: true } })
const { t } = useI18n()
const store = useProposalsStore()

const running = ref(false)
const phase = ref(null)
const waiveReason = ref('')
const waiving = ref(false)
const errorMsg = ref('')

const proposal = computed(() => store.currentProposal)
// 라이브 스트림 우선, 없으면 저장된 proposal 값.
const alignment = computed(() => store.odaStream.alignment || proposal.value?.odaAlignment || null)
const conformance = computed(() => store.odaStream.conformance || proposal.value?.odaConformance || null)
const artifacts = computed(() => proposal.value?.odaArtifacts || null)

const gateResult = computed(() => {
  const live = store.odaStream.gate?.result
  if (live) return live
  return conformance.value?.gateResult || 'PENDING'
})
const canProceed = computed(() => ['PASS', 'WAIVED'].includes(gateResult.value))
const gateLabel = computed(() => ({
  PASS: t('proposals.oda.gatePass'),
  FAIL: t('proposals.oda.gateFail'),
  WAIVED: t('proposals.oda.gateWaived'),
  PENDING: t('proposals.oda.gatePending'),
}[gateResult.value] || gateResult.value))

async function run(which) {
  running.value = true
  phase.value = which
  errorMsg.value = ''
  try {
    await store.subscribeToOda(props.proposalId, which)
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    running.value = false
  }
}

async function doWaive() {
  waiving.value = true
  errorMsg.value = ''
  try {
    await store.waiveConformance(props.proposalId, waiveReason.value.trim())
    waiveReason.value = ''
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    waiving.value = false
  }
}
</script>

<style scoped>
.oda-track { padding: 4px 2px; }
.oda-track__title { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: var(--color-text-bright); }
.oda-sec { border: 1px solid var(--color-border); border-radius: 6px; padding: 10px 12px; margin-bottom: 10px; }
.oda-sec__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.oda-sec__name { font-size: 13px; font-weight: 600; color: var(--color-text); }
.oda-sub { font-size: 11px; font-weight: 600; color: var(--color-text-light); margin: 8px 0 4px; }
.oda-sub--danger { color: var(--color-danger); }
.oda-align { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.oda-align__row { font-size: 12px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.chip { display: inline-block; padding: 1px 7px; border-radius: 10px; background: var(--color-bg-tertiary); font-size: 11px; color: var(--color-text); }
.chip--block { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.chip--off { opacity: 0.4; }
.muted { color: var(--color-text-light); font-size: 11px; }
.oda-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.oda-tbl td { padding: 3px 6px; border-bottom: 1px solid var(--color-border); }
.cls { font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px; }
.cls--reuse { background: #dcfce7; color: #166534; }
.cls--extend { background: #fef9c3; color: #854d0e; }
.cls--new { background: #fee2e2; color: #991b1b; }
.gate-badge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; }
.gate-badge--pass { background: #dcfce7; color: #166534; }
.gate-badge--fail { background: #fee2e2; color: #991b1b; }
.gate-badge--waived { background: #fef9c3; color: #854d0e; }
.gate-badge--pending { background: var(--color-bg-tertiary); color: var(--color-text-light); }
.oda-violations ul { margin: 2px 0 0; padding-left: 16px; font-size: 12px; }
.oda-waive { display: flex; gap: 6px; margin-top: 8px; }
.oda-waive__input { flex: 1; border: 1px solid var(--color-border); border-radius: 4px; padding: 4px 8px; font-size: 12px; background: var(--color-bg-secondary); color: var(--color-text); }
.oda-artifacts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.btn { padding: 5px 12px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--sm { padding: 3px 10px; font-size: 12px; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--primary:disabled { opacity: 0.5; cursor: default; }
.btn--danger { background: var(--color-danger); color: #fff; }
.btn--danger:disabled { opacity: 0.5; cursor: default; }
.stream-log { background: #0f172a; border-radius: 6px; padding: 8px 10px; max-height: 180px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #cbd5e1; margin-top: 8px; }
.stream-log__line { padding: 1px 0; white-space: pre-wrap; word-break: break-all; }
.stream-log__waiting { color: #64748b; }
.error-msg { color: var(--color-danger); font-size: 12px; margin-top: 6px; }
</style>
