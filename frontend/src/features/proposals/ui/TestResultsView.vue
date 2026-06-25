<template>
  <div class="test-results">
    <!-- 검증 실행/재검증/중지 바 -->
    <div class="validate-bar">
      <template v-if="validating">
        <span class="validating-badge"><span class="spinner spinner--xs" />{{ t('proposals.tests.validating') }}</span>
        <button @click="stop" class="btn btn--outline btn--sm">{{ t('proposals.common.stop') }}</button>
      </template>
      <button v-else @click="rerun" class="btn btn--outline btn--sm">{{ t('proposals.tests.rerun') }}</button>
      <span class="validate-hint">{{ t('proposals.tests.validateHint') }}</span>
    </div>

    <!-- 실행 로그 (runner narration·tool 사용 실시간) -->
    <pre v-if="logText" class="validate-log">{{ logText }}</pre>
    <p v-if="validationError" class="error-msg">{{ validationError }}</p>

    <div v-if="loading" class="test-loading">{{ t('proposals.tests.loadingResults') }}</div>

    <div v-else-if="validating && !store.testResults" class="test-running">
      <span class="spinner spinner--sm" />
      {{ t('proposals.tests.runningValidation') }}
      <br><span class="muted">{{ t('proposals.tests.runningMuted') }}</span>
    </div>

    <div v-else-if="!store.testResults" class="test-empty">
      <p>{{ t('proposals.tests.noResults') }} <strong>"{{ t('proposals.tests.rerun') }}"</strong>{{ t('proposals.tests.noResultsPost') }}</p>
    </div>

    <div v-else>
      <!-- Summary -->
      <div class="test-summary">
        <div class="summary-item summary-item--total">
          <span class="summary-num">{{ store.testResults.totalScenarios }}</span>
          <span class="summary-label">{{ t('proposals.tests.summaryTotal') }}</span>
        </div>
        <div class="summary-item summary-item--pass">
          <span class="summary-num">{{ store.testResults.passed }}</span>
          <span class="summary-label">PASS</span>
        </div>
        <div class="summary-item summary-item--fail">
          <span class="summary-num">{{ store.testResults.failed }}</span>
          <span class="summary-label">FAIL</span>
        </div>
        <div class="summary-item summary-item--skip">
          <span class="summary-num">{{ store.testResults.skipped }}</span>
          <span class="summary-label">SKIP</span>
        </div>
        <div class="pass-rate">{{ t('proposals.tests.passRate') }}: <strong>{{ passRate }}%</strong></div>
      </div>

      <!-- Items -->
      <div class="test-items">
        <div
          v-for="item in store.testResults.items"
          :key="item.scenarioId"
          :class="['test-item', `test-item--${item.result.toLowerCase()}`]"
        >
          <div class="test-item__header">
            <span :class="['result-badge', `result-badge--${item.result.toLowerCase()}`]">{{ item.result }}</span>
            <span v-if="item.category" :class="['cat-badge', `cat-badge--${item.category}`]">
              {{ item.category === 'structural' ? t('proposals.tests.categoryStructural') : t('proposals.tests.categoryAcceptance') }}
            </span>
            <span class="test-item__story">{{ item.storyTitle }}</span>
            <span class="test-item__id">{{ item.scenarioId }}</span>
          </div>
          <p class="test-item__scenario">{{ item.scenario }}</p>
          <p v-if="item.reason" class="test-item__reason">{{ item.reason }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useProposalsStore } from '../proposals.store'
import { useI18n } from '../../../app/i18n'

const props = defineProps({ proposalId: { type: String, required: true } })
const store = useProposalsStore()
const { t } = useI18n()
const loading = ref(false)

// 검증 진행 상태·로그는 store.validationStream(싱글톤)에서 가져온다 → 탭을 전환해도
// (이 컴포넌트가 언마운트돼도) 검증은 계속 진행되고, 다시 들어오면 로그가 그대로 보인다.
const validating = computed(() => store.validationStream.active)
const logText = computed(() => (store.validationStream.logLines || []).join('\n'))
const validationError = computed(() => store.validationStream.error)

const passRate = computed(() => {
  const r = store.testResults
  if (!r || r.totalScenarios === 0) return 0
  return Math.round((r.passed / r.totalScenarios) * 100)
})

function statusOf() {
  return store.currentProposal?.id === props.proposalId ? store.currentProposal.status : null
}

function startValidation() {
  store.subscribeToValidation(props.proposalId).catch(() => { /* 에러는 validationStream.error로 표시 */ })
}

function rerun() { startValidation() }
function stop() { store.stopValidation() }

onMounted(async () => {
  loading.value = true
  const r = await store.fetchTestResults(props.proposalId)
  loading.value = false
  if (validating.value) return                    // 이미 검증 진행 중(다른 탭에서 시작) → 로그 표시
  if (r) return                                    // 이미 결과 있음
  if (statusOf() !== 'TESTING') return             // 구현 완료(TESTING) 이후에만 검증
  startValidation()                                // 첫 진입 → 자동 검증 실행(스트리밍)
})
</script>

<style scoped>
.test-results { font-size: 13px; }
.test-loading, .test-empty { color: var(--color-text-light); padding: 12px 0; }
.test-running { display: flex; align-items: flex-start; gap: 8px; color: var(--color-text); padding: 12px; background: var(--color-bg-secondary); border-radius: 8px; line-height: 1.6; }
.test-running .muted { color: var(--color-text-light); font-size: 12px; }
.validate-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.validating-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--color-accent); }
.validate-hint { font-size: 12px; color: var(--color-text-light); }
.validate-log { font-size: 11px; line-height: 1.5; color: var(--color-text-light); background: var(--color-bg-tertiary); border-radius: 6px; padding: 8px 10px; margin: 0 0 12px; max-height: 220px; overflow: auto; white-space: pre-wrap; word-break: break-word; }
.btn { padding: 5px 12px; border-radius: 4px; border: none; cursor: pointer; font-size: 12px; }
.btn--outline { background: transparent; border: 1px solid var(--color-border); color: var(--color-text); display: inline-flex; align-items: center; gap: 6px; }
.btn--sm { padding: 4px 10px; font-size: 11px; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.test-summary { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding: 12px; background: var(--color-bg-secondary); border-radius: 8px; flex-wrap: wrap; }
.summary-item { text-align: center; }
.summary-num { display: block; font-size: 20px; font-weight: 700; }
.summary-label { font-size: 11px; color: var(--color-text-light); text-transform: uppercase; }
.summary-item--pass .summary-num { color: var(--color-success); }
.summary-item--fail .summary-num { color: var(--color-danger); }
.summary-item--skip .summary-num { color: var(--color-warning); }
.pass-rate { margin-left: auto; font-size: 14px; color: var(--color-text); }
.test-items { display: flex; flex-direction: column; gap: 8px; }
.test-item { border: 1px solid var(--color-border); border-radius: 6px; padding: 10px 12px; }
.test-item--pass { border-left: 3px solid var(--color-success); }
.test-item--fail { border-left: 3px solid var(--color-danger); }
.test-item--skipped { border-left: 3px solid var(--color-warning); }
.test-item__header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.result-badge { font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 3px; }
.result-badge--pass { background: var(--status-green-bg); color: var(--status-green-fg); }
.result-badge--fail { background: var(--status-red-bg); color: var(--status-red-fg); }
.result-badge--skipped { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.cat-badge { font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px; }
.cat-badge--structural { background: var(--status-blue-bg, #e7f0ff); color: var(--status-blue-fg, #2563eb); }
.cat-badge--acceptance { background: var(--status-neutral-bg); color: var(--status-neutral-fg); }
.test-item__story { font-weight: 500; flex: 1; }
.test-item__id { font-family: monospace; font-size: 11px; color: var(--color-text-light); }
.test-item__scenario { margin: 0; color: var(--color-text); font-size: 13px; }
.test-item__reason { margin: 4px 0 0; color: var(--color-danger); font-size: 12px; font-style: italic; }
.error-msg { color: var(--color-danger); font-size: 12px; margin: 0 0 12px; }
.spinner { width: 14px; height: 14px; border: 2px solid var(--color-border); border-top-color: var(--color-accent); border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block; }
.spinner--sm { width: 14px; height: 14px; flex-shrink: 0; margin-top: 2px; }
.spinner--xs { width: 10px; height: 10px; border-width: 2px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
